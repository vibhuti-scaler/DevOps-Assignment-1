#!/usr/bin/env python3
"""Run real labs only on the dedicated local kind cluster; save command transcripts."""
import argparse
import datetime
import json
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
CONTEXT = "kind-vibhuti-devops"
K = ["kubectl", "--kubeconfig", str(ROOT / ".lab/kubeconfig"),
     "--context", CONTEXT, "-n", "devops-homework"]
LOG = None


def emit(text):
    print(text, flush=True)
    if LOG:
        LOG.write(text + "\n")
        LOG.flush()


def run(*args, check=True, timeout=240, show=True):
    if show:
        emit("\n$ " + shlex.join(args))
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=timeout)
    if show and result.stdout:
        emit(result.stdout.rstrip())
    if check and result.returncode:
        raise RuntimeError(f"Command exited {result.returncode}: {shlex.join(args)}")
    return result.stdout


def k(*args, **kwargs):
    return run(*K, *args, **kwargs)


def apply(*files):
    args = [arg for name in files for arg in ("-f", name)]
    k("apply", *args)


def rollout(name):
    k("rollout", "status", name, "--timeout=180s")


def wait_pod(name):
    k("wait", "--for=condition=Ready", "pod/" + name, "--timeout=180s")


def retry(label, action, predicate=lambda value: True, attempts=30):
    for attempt in range(attempts):
        try:
            value = action()
            if predicate(value):
                emit("PASS: " + label)
                return value
        except (RuntimeError, subprocess.TimeoutExpired) as error:
            emit(str(error))
        if attempt + 1 < attempts:
            time.sleep(2)
    raise RuntimeError("Timed out: " + label)


def http(url, expected):
    return retry("HTTP contains " + expected,
                 lambda: k("exec", "dns-client", "--", "wget", "-T", "5", "-qO-", url),
                 lambda body: expected in body)


def obj(kind, name):
    return json.loads(k("get", kind, name, "-o", "json", show=False))


def endpoints(name):
    data = json.loads(k("get", "endpointslices", "-l",
                        "kubernetes.io/service-name=" + name, "-o", "json", show=False))
    return [e for item in data["items"] for e in (item.get("endpoints") or [])
            if e.get("conditions", {}).get("ready", False)]


def backoff_observed(name, reason):
    pod = obj("pod", name)
    statuses = pod["status"].get("containerStatuses", [])
    if any(c.get("state", {}).get("waiting", {}).get("reason") == reason for c in statuses):
        return True
    # A quick crash may be sampled as Terminated between kubelet status updates.
    # BackOff events belong to this exact Pod UID, not an earlier run with the same name.
    events = json.loads(k("get", "events", "--field-selector",
                          "involvedObject.uid=" + pod["metadata"]["uid"], "-o", "json", show=False))
    has_event = any(e.get("reason") == "BackOff" for e in events["items"])
    if reason == "CrashLoopBackOff":
        return has_event and any(c.get("restartCount", 0) > 0 for c in statuses)
    return has_event and any(c.get("state", {}).get("waiting", {}).get("reason") == "ErrImagePull" for c in statuses)


def fundamentals():
    run("docker", "inspect", "vibhuti-devops-control-plane", "--format", "{{.Config.Image}}")
    k("cluster-info")
    k("version")
    k("wait", "--for=condition=Ready", "nodes", "--all", "--timeout=180s")
    k("get", "nodes", "-o", "wide")
    k("-n", "kube-system", "rollout", "status", "deployment/coredns", "--timeout=180s")
    k("-n", "kube-system", "get", "pods", "-o", "wide")
    apply("kubernetes-fundamentals/namespace.yaml")
    retry("default ServiceAccount created", lambda: k("get", "serviceaccount", "default"))
    apply("kubernetes-services/client.yaml")
    wait_pod("dns-client")
    k("get", "namespace", "devops-homework")


def core():
    base = "kubernetes-core-objects/"
    apply(*(base + file for file in ("pod.yaml", "replicaset.yaml", "deployment-v1.yaml", "service.yaml")))
    wait_pod("standalone-web")
    rollout("deployment/core-web")
    k("scale", "replicaset/replica-web", "--replicas=3")
    k("wait", "--for=jsonpath={.status.readyReplicas}=3", "replicaset/replica-web", "--timeout=180s")
    before = json.loads(k("get", "pods", "-l", "app=replica-web", "-o", "json", show=False))
    before_ids = {p["metadata"]["uid"] for p in before["items"]}
    k("get", "pods", "-l", "app=replica-web", "-o", "wide")
    k("delete", "pods", "-l", "app=replica-web")
    k("wait", "--for=jsonpath={.status.readyReplicas}=3", "replicaset/replica-web", "--timeout=180s")
    after = json.loads(k("get", "pods", "-l", "app=replica-web", "-o", "json", show=False))
    assert len(after["items"]) == 3 and before_ids.isdisjoint(p["metadata"]["uid"] for p in after["items"])
    emit("PASS: ReplicaSet replaced all three deleted Pods with new identities")
    k("get", "pods", "-l", "app=replica-web", "-o", "wide")
    http("http://core-web", "Hello from v1")
    apply(base + "deployment-v2.yaml")
    rollout("deployment/core-web")
    http("http://core-web", "Hello from v2")
    k("rollout", "undo", "deployment/core-web")
    rollout("deployment/core-web")
    http("http://core-web", "Hello from v1")
    k("rollout", "history", "deployment/core-web")
    apply(base + "daemonset.yaml")
    rollout("daemonset/node-agent")
    k("get", "pods,replicasets,deployments,daemonsets", "-o", "wide")
    k("delete", "pod", "standalone-web")
    assert not k("get", "pod", "standalone-web", "--ignore-not-found", "-o", "name").strip()
    emit("PASS: a standalone Pod is not recreated by a controller")


def strategies():
    base = "kubernetes-core-objects/strategies/"
    apply(base + "blue-green.yaml")
    rollout("deployment/web-blue")
    rollout("deployment/web-green")
    http("http://blue-green", "Hello from blue")
    k("get", "endpointslices", "-l", "kubernetes.io/service-name=blue-green", "-o", "wide")
    k("patch", "service", "blue-green", "--type=merge", "-p",
      '{"spec":{"selector":{"app":"blue-green","slot":"green"}}}')
    http("http://blue-green", "Hello from green")
    k("get", "endpointslices", "-l", "kubernetes.io/service-name=blue-green", "-o", "wide")
    apply(base + "canary.yaml")
    rollout("deployment/web-stable")
    rollout("deployment/web-canary")
    retry("canary Service has four ready endpoints", lambda: endpoints("canary-web"), lambda e: len(e) == 4)
    k("get", "pods", "-l", "app=canary-web", "--show-labels")
    k("exec", "dns-client", "--", "sh", "-c",
      "for i in $(seq 1 20); do wget -T 5 -qO- http://canary-web; done")
    apply(base + "recreate-v1.yaml")
    rollout("deployment/recreate-web")
    before = obj("deployment", "recreate-web")
    apply(base + "recreate-v2.yaml")
    rollout("deployment/recreate-web")
    after = obj("deployment", "recreate-web")
    assert before["spec"]["strategy"]["type"] == after["spec"]["strategy"]["type"] == "Recreate"
    assert before["spec"]["template"] != after["spec"]["template"]
    k("exec", "deployment/recreate-web", "--", "wget", "-qO-", "http://127.0.0.1")
    k("describe", "deployment", "recreate-web")
    emit("PASS: Recreate v1 to v2 completed; no continuous availability measurement claimed")


def lifecycle():
    base = Path("kubernetes-core-objects/lifecycle")
    names = ["running", "pending", "succeeded", "failed", "crashloop", "image-error",
             "readiness", "liveness", "startup", "init", "multi", "termination"]
    for file, suffix in zip(sorted(base.glob("*.yaml")), names):
        name = "lifecycle-" + suffix
        emit("\nExercise: " + suffix)
        apply(str(file))
        try:
            if suffix in ("pending", "succeeded", "failed"):
                phase = {"pending": "Pending", "succeeded": "Succeeded", "failed": "Failed"}[suffix]
                k("wait", "--for=jsonpath={.status.phase}=" + phase, "pod/" + name, "--timeout=90s")
                if suffix == "pending":
                    retry("Pod is unschedulable", lambda: obj("pod", name),
                          lambda p: any(c.get("reason") == "Unschedulable" for c in p["status"].get("conditions", [])))
                else:
                    k("logs", name)
            elif suffix in ("crashloop", "image-error"):
                reason = "CrashLoopBackOff" if suffix == "crashloop" else "ImagePullBackOff"
                retry(reason + " waiting state or matching BackOff events",
                      lambda: backoff_observed(name, reason), bool, attempts=60)
                k("get", "events", "--field-selector", "involvedObject.uid=" + obj("pod", name)["metadata"]["uid"])
                if suffix == "crashloop":
                    k("logs", name, "--previous")
            elif suffix == "readiness":
                k("wait", "--for=jsonpath={.status.phase}=Running", "pod/" + name, "--timeout=90s")
                pod = obj("pod", name)
                assert any(c["type"] == "Ready" and c["status"] == "False" for c in pod["status"]["conditions"])
                emit("PASS: Pod is Running but not Ready")
                k("exec", name, "--", "touch", "/tmp/ready")
                wait_pod(name)
            elif suffix == "liveness":
                retry("liveness failure caused a restart", lambda: obj("pod", name),
                      lambda p: any(c.get("restartCount", 0) > 0 for c in p["status"].get("containerStatuses", [])), attempts=60)
            else:
                wait_pod(name)
                if suffix == "startup":
                    assert obj("pod", name)["status"]["containerStatuses"][0]["restartCount"] == 0
                    emit("PASS: startup delay tolerated without a restart")
                elif suffix == "init":
                    assert "init-complete" in k("logs", name, "-c", "app")
                elif suffix == "multi":
                    assert "app-started" in k("logs", name, "-c", "app")
                    assert "sidecar-started" in k("logs", name, "-c", "sidecar")
                elif suffix == "termination":
                    with tempfile.TemporaryFile(mode="w+") as capture:
                        watcher = subprocess.Popen([*K, "logs", "-f", name], stdout=capture, stderr=subprocess.STDOUT, text=True)
                        try:
                            time.sleep(2)
                            k("delete", "pod", name, "--wait=true")
                            watcher.wait(timeout=30)
                        finally:
                            if watcher.poll() is None:
                                watcher.terminate()
                                watcher.wait(timeout=10)
                        capture.seek(0)
                        output = capture.read()
                        emit(output)
                        assert "received-SIGTERM" in output and "cleanup-complete" in output
                    emit("PASS: SIGTERM handler completed graceful cleanup")
                    continue
            k("get", "pod", name, "-o", "wide")
            if suffix in ("pending", "crashloop", "image-error", "liveness"):
                k("describe", "pod", name)
        finally:
            k("delete", "-f", str(file), "--ignore-not-found", "--timeout=60s")


def services():
    base = "kubernetes-services/"
    apply(*(base + f for f in ("deployment.yaml", "clusterip.yaml", "nodeport.yaml", "externalname.yaml", "headless.yaml")))
    rollout("deployment/service-web")
    rollout("statefulset/stateful-web")
    # Absolute names and explicit record types avoid BusyBox reporting unrelated
    # search-suffix NXDOMAIN answers as failure. HTTP below verifies short-name use.
    for name in ("web-clusterip", "external-docs", "web-headless", "stateful-web-0.web-headless"):
        absolute = name + ".devops-homework.svc.cluster.local."
        record = "-type=CNAME" if name == "external-docs" else "-type=A"
        retry("DNS resolves " + absolute,
              lambda absolute=absolute, record=record: k("exec", "dns-client", "--", "nslookup", record, absolute))
    http("http://web-clusterip", "Hello from v1")
    retry("host reaches real NodePort 30081", lambda: run("curl", "--fail", "--silent", "--show-error", "--max-time", "5", "http://127.0.0.1:30081/"), lambda b: "Hello from v1" in b)
    k("get", "services,pods", "-o", "wide")
    k("get", "endpointslices", "-l", "kubernetes.io/service-name=web-clusterip", "-o", "wide")
    k("patch", "service", "web-clusterip", "--type=merge", "-p", '{"spec":{"selector":{"app":"deliberately-missing"}}}')
    try:
        retry("broken selector has no ready endpoints", lambda: endpoints("web-clusterip"), lambda e: len(e) == 0)
        k("get", "endpointslices", "-l", "kubernetes.io/service-name=web-clusterip", "-o", "yaml")
    finally:
        apply(base + "clusterip.yaml")
    http("http://web-clusterip", "Hello from v1")
    apply(base + "optional/loadbalancer.yaml")
    k("get", "service", "web-loadbalancer")
    emit("LoadBalancer external IP requires an implementation; external LoadBalancer traffic is not tested.")
    k("delete", "-f", base + "optional/loadbalancer.yaml")


def ingress():
    base = "kubernetes-ingress-configmaps-secrets/"
    apply(base + "configmap.yaml", base + "backend-code.yaml", base + "controller.yaml")
    if not k("get", "secret", "demo-credentials", "--ignore-not-found", "-o", "name", show=False).strip():
        with tempfile.TemporaryDirectory(prefix="vibhuti-secret-") as scratch:
            env = Path(scratch) / ".env.secret"
            env.touch(mode=0o600)
            env.write_text("DEMO_TOKEN=" + secrets.token_hex(16) + "\n")
            k("create", "secret", "generic", "demo-credentials", "--from-env-file=" + str(env))
    k("describe", "secret", "demo-credentials")
    apply(base + "frontend.yaml", base + "backend.yaml", base + "ingress.yaml")
    for name in ("demo-frontend", "demo-backend", "lab-ingress"):
        rollout("deployment/" + name)
    # Restart ensures an earlier interrupted config exercise cannot leave stale environment values.
    k("rollout", "restart", "deployment/demo-backend")
    rollout("deployment/demo-backend")
    with (ROOT / ".lab/port-forward.log").open("w") as log:
        forward = subprocess.Popen([*K, "port-forward", "service/lab-ingress", "18084:80", "18443:443"], stdout=log, stderr=subprocess.STDOUT)
        try:
            def request(path, expected):
                return retry("Ingress " + path + " contains " + expected,
                             lambda: run("curl", "--fail", "--silent", "--show-error", "--max-time", "5", "-H", "Host: devops.test", "http://127.0.0.1:18084" + path),
                             lambda body: expected in body)
            request("/", "Hello from DevOps session 12 frontend")
            for path in ("/api", "/api/", "/api/health"):
                body = json.loads(request(path, '"environment": "coursework"'))
                assert body["secret_loaded"] is True and body["currency"] == "INR"
                assert "DEMO_TOKEN" not in body
            k("patch", "configmap", "demo-config", "--type=merge", "-p", '{"data":{"ENVIRONMENT":"staging"}}')
            request("/api/health", '"environment": "coursework"')
            k("rollout", "restart", "deployment/demo-backend")
            rollout("deployment/demo-backend")
            request("/api/health", '"environment": "staging"')
            with tempfile.TemporaryDirectory(prefix="vibhuti-tls-") as scratch:
                key, cert = str(Path(scratch) / "tls.key"), str(Path(scratch) / "tls.crt")
                run("openssl", "req", "-x509", "-nodes", "-newkey", "rsa:2048", "-days", "2", "-keyout", key, "-out", cert, "-subj", "/CN=portal.devops.test", "-addext", "subjectAltName=DNS:portal.devops.test,DNS:api.devops.test", show=False)
                k("delete", "secret", "demo-tls", "--ignore-not-found")
                k("create", "secret", "tls", "demo-tls", "--cert=" + cert, "--key=" + key)
                apply(base + "optional/ingress-tls.yaml")
                for host, path, expected in (("portal.devops.test", "/", "Hello from"), ("api.devops.test", "/api/health", '"secret_loaded": true')):
                    retry("verified TLS certificate for " + host,
                          lambda host=host, path=path: run("curl", "--fail", "--silent", "--show-error", "--max-time", "5", "--noproxy", "*", "--cacert", cert, "--resolve", host + ":18443:127.0.0.1", "https://" + host + ":18443" + path),
                          lambda body, expected=expected: expected in body)
            k("get", "ingress,configmaps,services")
        finally:
            forward.terminate()
            forward.wait(timeout=15)
            apply(base + "configmap.yaml")
            k("rollout", "restart", "deployment/demo-backend")
            rollout("deployment/demo-backend")


SECTIONS = {"01-fundamentals": fundamentals, "02-core": core, "03-strategies": strategies,
            "04-lifecycle": lifecycle, "05-services": services, "06-ingress": ingress}


def main():
    global LOG
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sections", nargs="*", help="Optional section names: " + ", ".join(SECTIONS))
    args = parser.parse_args()
    sections = args.sections or list(SECTIONS)
    if any(s not in SECTIONS for s in sections):
        parser.error("Unknown section")
    if not (ROOT / ".lab/kubeconfig").is_file():
        parser.error("Create the dedicated kind cluster first; see kubernetes-fundamentals/README.md")
    config = json.loads(k("config", "view", "--minify", "-o", "json", show=False))
    server = config["clusters"][0]["cluster"]["server"]
    if not server.startswith("https://127.0.0.1:"):
        parser.error("The lab runner only supports its local kind API server")
    node = obj("node", "vibhuti-devops-control-plane")
    if node["metadata"]["labels"].get("kubernetes.io/hostname") != "vibhuti-devops-control-plane":
        parser.error("Unexpected cluster node")
    output = ROOT / "evidence/kubernetes"
    output.mkdir(parents=True, exist_ok=True)
    for section in sections:
        with (output / (section + ".txt")).open("w") as log:
            LOG = log
            emit("Vibhuti Bhatnagar | 24BCS10288 | vibhuti.24bcs10288@sst.scaler.com")
            emit(datetime.datetime.now(datetime.timezone.utc).isoformat() + " | " + section)
            try:
                SECTIONS[section]()
            except Exception as error:
                emit("FAILED: " + str(error))
                raise
            emit("PASS: " + section + " completed")
            LOG = None


if __name__ == "__main__":
    main()
