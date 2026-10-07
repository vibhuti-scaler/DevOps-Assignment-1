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


def endpoints(name, namespace=None):
    scope = ["-n", namespace] if namespace else []
    data = json.loads(k(*scope, "get", "endpointslices", "-l",
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


def storage():
    base = "kubernetes-storage-hpa-probes/"
    apply("kubernetes-fundamentals/namespace.yaml")
    # emptyDir: one volume, two containers, and nothing left after the Pod.
    apply(base + "01-volumes/emptydir-pod.yaml")
    wait_pod("emptydir-demo")
    retry("reader container sees the writer's lines in the shared emptyDir",
          lambda: k("exec", "emptydir-demo", "-c", "reader", "--", "cat", "/shared/notes.txt"),
          lambda body: body.count("written by") >= 2)
    k("delete", "pod", "emptydir-demo", "--wait=true")
    # hostPath: the file is written into the node's own filesystem.
    apply(base + "01-volumes/hostpath-pod.yaml")
    wait_pod("hostpath-demo")
    retry("hostPath file is readable on the node itself",
          lambda: run("docker", "exec", "vibhuti-devops-control-plane",
                      "cat", "/var/lib/devops-homework/hostpath-demo/marker.txt"),
          lambda body: "written by hostpath-demo" in body)
    k("delete", "pod", "hostpath-demo", "--wait=true")
    run("docker", "exec", "vibhuti-devops-control-plane",
        "cat", "/var/lib/devops-homework/hostpath-demo/marker.txt")
    # Static binding: the PersistentVolume is written by hand, not provisioned.
    apply(base + "02-persistent-storage/pv.yaml", base + "02-persistent-storage/pvc.yaml")
    retry("static PVC bound to the hand-written PV",
          lambda: obj("persistentvolumeclaim", "static-pvc"),
          lambda claim: claim["status"]["phase"] == "Bound" and claim["spec"]["volumeName"] == "static-pv")
    k("get", "pv", "static-pv")
    k("get", "pvc", "static-pvc")
    apply(base + "02-persistent-storage/pod.yaml")
    wait_pod("static-pv-writer")
    k("exec", "static-pv-writer", "--", "cat", "/data/student.txt")
    k("delete", "pod", "static-pv-writer", "--wait=true")
    apply(base + "02-persistent-storage/pod.yaml")
    wait_pod("static-pv-writer")
    retry("file written by the deleted Pod survived on the PersistentVolume",
          lambda: k("exec", "static-pv-writer", "--", "cat", "/data/student.txt"),
          lambda body: "24BCS10288" in body)
    # Dynamic provisioning through the default StorageClass.
    k("get", "storageclass")
    apply(base + "03-storageclass/dynamic-pvc.yaml")
    retry("dynamic PVC waits for a consumer before a volume is provisioned",
          lambda: obj("persistentvolumeclaim", "dynamic-pvc"),
          lambda claim: claim["status"]["phase"] == "Pending")
    k("describe", "pvc", "dynamic-pvc")
    apply(base + "03-storageclass/dynamic-pod.yaml")
    wait_pod("dynamic-pv-writer")
    volume = retry("StorageClass provisioned a PersistentVolume on first use",
                   lambda: obj("persistentvolumeclaim", "dynamic-pvc"),
                   lambda claim: claim["status"]["phase"] == "Bound")["spec"]["volumeName"]
    k("get", "pv", volume, "-o", "wide")
    k("exec", "dynamic-pv-writer", "--", "cat", "/data/proof.txt")
    k("get", "pv,pvc")
    k("delete", "pod", "static-pv-writer", "dynamic-pv-writer", "--wait=true")
    k("delete", "pvc", "static-pvc", "dynamic-pvc")
    k("delete", "pv", "static-pv", "--ignore-not-found")


def hpa_probes():
    base = "kubernetes-storage-hpa-probes/"
    apply("kubernetes-fundamentals/namespace.yaml")
    k("-n", "kube-system", "rollout", "status", "deployment/metrics-server", "--timeout=180s")
    retry("metrics API answers for nodes", lambda: k("top", "nodes"), lambda body: "CPU(cores)" in body)
    apply(base + "04-hpa/deployment.yaml", base + "04-hpa/service.yaml", base + "04-hpa/hpa.yaml")
    rollout("deployment/hpa-demo")
    retry("HPA has a real CPU reading rather than <unknown>",
          lambda: obj("horizontalpodautoscaler", "hpa-demo"),
          lambda h: (h.get("status", {}).get("currentMetrics") or [{}])[0]
                    .get("resource", {}).get("current", {}).get("averageUtilization") is not None,
          attempts=60)
    k("get", "hpa", "hpa-demo")
    k("top", "pods", "-l", "app=hpa-demo")
    apply(base + "04-hpa/load-generator.yaml")
    rollout("deployment/load-generator")
    retry("HPA scaled out under load", lambda: (k("get", "hpa", "hpa-demo"),
                                                obj("horizontalpodautoscaler", "hpa-demo"))[1],
          lambda h: (h["status"].get("currentReplicas") or 0) > 1, attempts=90)
    k("get", "pods", "-l", "app=hpa-demo")
    k("top", "pods", "-l", "app=hpa-demo")
    k("describe", "hpa", "hpa-demo")
    k("delete", "deployment", "load-generator", "--wait=true")
    retry("HPA scaled back in once the load stopped",
          lambda: (k("get", "hpa", "hpa-demo"), obj("horizontalpodautoscaler", "hpa-demo"))[1],
          lambda h: h["status"].get("currentReplicas") == 1, attempts=150)
    k("get", "pods", "-l", "app=hpa-demo")
    k("delete", "-f", base + "04-hpa/hpa.yaml", "-f", base + "04-hpa/service.yaml",
      "-f", base + "04-hpa/deployment.yaml")
    # Startup probe: liveness stays suspended while the slow boot finishes.
    apply(base + "05-probes/startup.yaml")
    retry("startup probe keeps the Pod unready while it boots",
          lambda: obj("pod", "probe-startup"),
          lambda p: p["status"]["containerStatuses"][0]["started"] is False, attempts=20)
    k("get", "pod", "probe-startup")
    wait_pod("probe-startup")
    k("get", "pod", "probe-startup")
    retry("container never restarted during the 20s boot",
          lambda: obj("pod", "probe-startup"),
          lambda p: p["status"]["containerStatuses"][0]["restartCount"] == 0)
    # Readiness probe: Running, but removed from the Service endpoints.
    apply(base + "05-probes/readiness.yaml", base + "05-probes/readiness-service.yaml")
    retry("Pod is Running yet never Ready because readiness fails",
          lambda: obj("pod", "probe-readiness"),
          lambda p: p["status"]["phase"] == "Running" and
                    not any(c["type"] == "Ready" and c["status"] == "True" for c in p["status"]["conditions"]),
          attempts=45)
    k("get", "pod", "probe-readiness")
    retry("Service has no ready endpoint for the unready Pod",
          lambda: endpoints("probe-readiness"), lambda eps: eps == [])
    k("get", "endpointslices", "-l", "kubernetes.io/service-name=probe-readiness")
    k("describe", "pod", "probe-readiness")
    # Liveness probe: a failing check restarts the container in place.
    apply(base + "05-probes/liveness.yaml")
    wait_pod("probe-liveness")
    retry("failing liveness probe restarted the container",
          lambda: obj("pod", "probe-liveness"),
          lambda p: p["status"]["containerStatuses"][0]["restartCount"] >= 1, attempts=60)
    k("get", "pod", "probe-liveness")
    k("describe", "pod", "probe-liveness")
    k("delete", "pod", "probe-startup", "probe-readiness", "probe-liveness", "--wait=true")
    k("delete", "service", "probe-readiness")


def webapp():
    base = "kubernetes-storage-hpa-probes/mini-project/"
    ns = ["-n", "production-webapp"]
    apply(base + "namespace.yaml")
    k(*ns, "apply", "-f", base + "pvc.yaml")
    k(*ns, "get", "pvc", "web-data")
    k(*ns, "apply", "-f", base + "deployment.yaml", "-f", base + "service.yaml",
      "-f", base + "hpa.yaml")
    k(*ns, "rollout", "status", "deployment/web-app", "--timeout=240s")
    retry("500Mi claim bound once the first Pod consumed it",
          lambda: json.loads(k(*ns, "get", "pvc", "web-data", "-o", "json", show=False)),
          lambda claim: claim["status"]["phase"] == "Bound")
    k(*ns, "get", "pvc,pv,pods,svc,hpa")
    # Storage survives the Pod it was written from.
    first = json.loads(k(*ns, "get", "pods", "-l", "app=web-app", "-o", "json", show=False))["items"][0]["metadata"]["name"]
    k(*ns, "exec", first, "--", "sh", "-c",
      "echo 'Student: Vibhuti Bhatnagar 24BCS10288' > /data/student.txt")
    k(*ns, "exec", first, "--", "cat", "/data/student.txt")
    k(*ns, "delete", "pod", first, "--wait=true")
    k(*ns, "rollout", "status", "deployment/web-app", "--timeout=240s")
    replacement = retry("a replacement Pod is scheduled",
                        lambda: [p["metadata"]["name"] for p in json.loads(
                            k(*ns, "get", "pods", "-l", "app=web-app",
                              "--field-selector=status.phase=Running", "-o", "json", show=False))["items"]
                            if p["metadata"]["name"] != first],
                        lambda names: bool(names))[0]
    retry("the file written by the deleted Pod is still on the volume",
          lambda: k(*ns, "exec", replacement, "--", "cat", "/data/student.txt"),
          lambda body: "24BCS10288" in body)
    # The Service answers, which also proves readiness gating let the Pods in.
    k(*ns, "get", "endpointslices", "-l", "kubernetes.io/service-name=web-service")
    apply("kubernetes-services/client.yaml")
    retry("Service answers over ClusterIP",
          lambda: k("exec", "dns-client", "--", "wget", "-T", "5", "-qO-",
                    "http://web-service.production-webapp.svc.cluster.local"),
          lambda body: "Welcome to nginx" in body, attempts=45)
    # Autoscaling under load.
    k(*ns, "get", "hpa", "web-app-hpa")
    k(*ns, "apply", "-f", base + "load-generator.yaml")
    k(*ns, "rollout", "status", "deployment/load-generator", "--timeout=240s")
    retry("HPA scaled the web app beyond its two baseline replicas",
          lambda: (k(*ns, "get", "hpa", "web-app-hpa"),
                   json.loads(k(*ns, "get", "hpa", "web-app-hpa", "-o", "json", show=False)))[1],
          lambda h: (h["status"].get("currentReplicas") or 0) > 2, attempts=90)
    k(*ns, "top", "pods")
    k(*ns, "get", "pods")
    k(*ns, "describe", "hpa", "web-app-hpa")
    k(*ns, "delete", "deployment", "load-generator", "--wait=true")
    retry("HPA returned to the two-replica floor",
          lambda: (k(*ns, "get", "hpa", "web-app-hpa"),
                   json.loads(k(*ns, "get", "hpa", "web-app-hpa", "-o", "json", show=False)))[1],
          lambda h: h["status"].get("currentReplicas") == 2, attempts=150)
    k(*ns, "get", "pods")
    k(*ns, "get", "all,pvc")


def waiting_reason(name):
    statuses = obj("pod", name)["status"].get("containerStatuses", [])
    return (statuses[0].get("state", {}).get("waiting", {}).get("reason") if statuses else None)


def terminated_reason(name):
    statuses = obj("pod", name)["status"].get("containerStatuses", [])
    if not statuses:
        return None
    state = statuses[0].get("state", {}).get("terminated") or \
        statuses[0].get("lastState", {}).get("terminated") or {}
    return state.get("reason")


def troubleshooting():
    base = "kubernetes-troubleshooting/"
    apply("kubernetes-fundamentals/namespace.yaml")

    # Task 1: the commands themselves, on a healthy Pod.
    apply(base + "01-commands/demo-pod.yaml")
    wait_pod("triage-demo")
    k("get", "pods")
    k("get", "pod", "triage-demo", "-o", "wide")
    k("get", "pod", "triage-demo", "--show-labels")
    k("describe", "pod", "triage-demo")
    k("logs", "triage-demo", "--tail=5")
    k("exec", "triage-demo", "--", "sh", "-c", "wget -qO- http://127.0.0.1 | head -4")
    k("events", "--for", "pod/triage-demo")
    k("explain", "pod.spec.containers.resources")
    # The metrics pipeline needs one scrape interval before a new Pod appears.
    retry("kubectl top reports this Pod",
          lambda: k("top", "pod", "triage-demo", check=False),
          lambda body: "CPU(cores)" in body, attempts=45)
    k("delete", "pod", "triage-demo", "--wait=true")

    # Task 2a: CrashLoopBackOff - the container keeps exiting non-zero.
    apply(base + "02-crashloopbackoff/broken-pod.yaml")
    retry("observed CrashLoopBackOff", lambda: backoff_observed("crashloop-broken", "CrashLoopBackOff"),
          attempts=60)
    k("get", "pod", "crashloop-broken")
    k("describe", "pod", "crashloop-broken")
    # While the container is in backoff the current log is unavailable, so the
    # previous attempt is what shows the actual error.
    # While the container is in backoff the current log may be unavailable, so
    # both the current and the previous attempt are asked for.
    retry("logs show why the container exited",
          lambda: k("logs", "crashloop-broken", check=False) +
                  k("logs", "crashloop-broken", "--previous", check=False),
          lambda body: "config.ini" in body, attempts=30)
    apply(base + "02-crashloopbackoff/fixed-pod.yaml")
    wait_pod("crashloop-fixed")
    k("logs", "crashloop-fixed")
    k("get", "pods", "-l", "app=crashloop-demo")
    k("delete", "pod", "crashloop-broken", "crashloop-fixed", "--wait=true")
    k("delete", "configmap", "crashloop-config")

    # Task 2b: ErrImagePull, then ImagePullBackOff once the kubelet backs off.
    apply(base + "03-imagepullbackoff/broken-pod.yaml")
    retry("observed ErrImagePull", lambda: waiting_reason("imagepull-broken"),
          lambda reason: reason in ("ErrImagePull", "ImagePullBackOff"), attempts=60)
    retry("observed ImagePullBackOff", lambda: backoff_observed("imagepull-broken", "ImagePullBackOff"),
          attempts=60)
    k("get", "pod", "imagepull-broken")
    k("describe", "pod", "imagepull-broken")
    apply(base + "03-imagepullbackoff/fixed-pod.yaml")
    wait_pod("imagepull-fixed")
    k("get", "pods", "-l", "app=imagepull-demo")
    k("delete", "pod", "imagepull-broken", "imagepull-fixed", "--wait=true")

    # Task 2c: Pending - the scheduler cannot satisfy the request.
    apply(base + "04-pending/broken-pod.yaml")
    retry("observed Pending with an Unschedulable condition",
          lambda: obj("pod", "pending-broken"),
          lambda p: p["status"]["phase"] == "Pending" and
                    any(c.get("reason") == "Unschedulable" for c in p["status"].get("conditions", [])),
          attempts=60)
    k("get", "pod", "pending-broken", "-o", "wide")
    k("describe", "pod", "pending-broken")
    k("get", "nodes", "-o", "custom-columns=NODE:.metadata.name,CPU:.status.allocatable.cpu,MEM:.status.allocatable.memory")
    apply(base + "04-pending/fixed-pod.yaml")
    wait_pod("pending-fixed")
    k("get", "pods", "-l", "app=pending-demo", "-o", "wide")
    k("delete", "pod", "pending-broken", "pending-fixed", "--wait=true")

    # Task 2d: OOMKilled - the limit is lower than the working set.
    apply(base + "06-oomkilled/broken-pod.yaml")
    retry("observed OOMKilled", lambda: terminated_reason("oom-broken"),
          lambda reason: reason == "OOMKilled", attempts=60)
    k("get", "pod", "oom-broken")
    k("describe", "pod", "oom-broken")
    apply(base + "06-oomkilled/fixed-pod.yaml")
    wait_pod("oom-fixed")
    k("logs", "oom-fixed")
    k("delete", "pod", "oom-broken", "oom-fixed", "--wait=true")

    # Task 2e: a configuration reference that does not resolve.
    apply(base + "07-config-error/broken-pod.yaml")
    retry("observed CreateContainerConfigError", lambda: waiting_reason("config-broken"),
          lambda reason: reason == "CreateContainerConfigError", attempts=60)
    k("get", "pod", "config-broken")
    k("describe", "pod", "config-broken")
    apply(base + "07-config-error/fixed.yaml")
    wait_pod("config-fixed")
    k("exec", "config-fixed", "--", "printenv", "APP_MODE")
    k("delete", "pod", "config-broken", "config-fixed", "--wait=true")
    k("delete", "configmap", "missing-config")

    # Task 2f: Service connectivity and DNS.
    apply(base + "05-service-dns/deployment.yaml", base + "05-service-dns/broken-service.yaml",
          base + "05-service-dns/dns-test-pod.yaml")
    rollout("deployment/dns-demo")
    wait_pod("dns-probe")
    retry("Service with the wrong selector has no endpoints",
          lambda: endpoints("dns-demo"), lambda eps: eps == [])
    k("get", "endpointslices", "-l", "kubernetes.io/service-name=dns-demo")
    k("describe", "service", "dns-demo")
    k("get", "pods", "-l", "app=dns-demo", "--show-labels")
    # DNS itself is healthy: the name resolves, there is simply nothing behind it.
    k("exec", "dns-probe", "--", "nslookup", "dns-demo.devops-homework.svc.cluster.local")
    k("exec", "dns-probe", "--", "sh", "-c",
      "wget -T 3 -qO- http://dns-demo || echo 'request failed: Service has no backend'", check=False)
    apply(base + "05-service-dns/service.yaml")
    retry("corrected selector produced ready endpoints",
          lambda: endpoints("dns-demo"), lambda eps: len(eps) == 2)
    k("get", "endpointslices", "-l", "kubernetes.io/service-name=dns-demo")
    retry("Service answers after the selector was corrected",
          lambda: k("exec", "dns-probe", "--", "wget", "-T", "5", "-qO-", "http://dns-demo"),
          lambda body: "Welcome to nginx" in body)
    # A name that does not exist fails at DNS, not at the connection.
    k("exec", "dns-probe", "--", "sh", "-c",
      "nslookup no-such-service.devops-homework.svc.cluster.local || echo 'NXDOMAIN: the Service name is wrong'",
      check=False)
    k("-n", "kube-system", "get", "pods", "-l", "k8s-app=kube-dns", "-o", "wide")
    k("delete", "-f", base + "05-service-dns/service.yaml", "-f", base + "05-service-dns/deployment.yaml",
      "-f", base + "05-service-dns/dns-test-pod.yaml")


def triage_project():
    base = "kubernetes-troubleshooting/mini-project/"
    apply("kubernetes-fundamentals/namespace.yaml")
    # 1-4: deploy, observe, confirm the Service reaches the Pods.
    apply(base + "deployment.yaml", base + "service.yaml")
    rollout("deployment/troubleshooting-app")
    k("get", "pods", "-o", "wide")
    k("get", "service", "troubleshooting-service")
    pod = json.loads(k("get", "pods", "-l", "app=troubleshooting-app", "-o", "json",
                       show=False))["items"][0]["metadata"]["name"]
    k("describe", "pod", pod)
    k("logs", pod, "--tail=5")
    k("exec", pod, "--", "sh", "-c", "wget -qO- http://127.0.0.1 | head -4")
    retry("Service has both Pod addresses as endpoints",
          lambda: endpoints("troubleshooting-service"), lambda eps: len(eps) == 2)
    k("get", "endpointslices", "-l", "kubernetes.io/service-name=troubleshooting-service")
    # 5-7: the broken Pod, diagnosed before the YAML is touched.
    apply(base + "broken-pod.yaml")
    retry("broken Pod reached an image-pull failure",
          lambda: waiting_reason("project-broken-pod"),
          lambda reason: reason in ("ErrImagePull", "ImagePullBackOff"), attempts=60)
    k("get", "pod", "project-broken-pod")
    k("describe", "pod", "project-broken-pod")
    k("events", "--for", "pod/project-broken-pod")
    k("delete", "pod", "project-broken-pod", "--wait=true")
    # 8-9: the selector challenge.
    apply(base + "broken-service.yaml")
    retry("broken selector emptied the endpoints",
          lambda: endpoints("troubleshooting-service"), lambda eps: eps == [])
    k("get", "endpointslices", "-l", "kubernetes.io/service-name=troubleshooting-service")
    k("get", "pods", "--show-labels")
    k("describe", "service", "troubleshooting-service")
    apply(base + "service.yaml")
    retry("endpoints returned after the selector was corrected",
          lambda: endpoints("troubleshooting-service"), lambda eps: len(eps) == 2)
    k("get", "endpointslices", "-l", "kubernetes.io/service-name=troubleshooting-service")
    apply("kubernetes-services/client.yaml")
    wait_pod("dns-client")
    retry("Service answers again end to end",
          lambda: k("exec", "dns-client", "--", "wget", "-T", "5", "-qO-",
                    "http://troubleshooting-service"),
          lambda body: "Welcome to nginx" in body)
    k("get", "all")
    k("delete", "-f", base + "service.yaml", "-f", base + "deployment.yaml")


HELM_ENV = {"HELM_REPOSITORY_CONFIG": str(ROOT / ".lab/helm/repositories.yaml"),
            "HELM_REPOSITORY_CACHE": str(ROOT / ".lab/helm/cache"),
            "HELM_CACHE_HOME": str(ROOT / ".lab/helm/cache"),
            "HELM_CONFIG_HOME": str(ROOT / ".lab/helm/config"),
            "HELM_DATA_HOME": str(ROOT / ".lab/helm/data")}


def helm(*args, check=True, timeout=300):
    """Run helm against the lab cluster only, with its state kept in .lab/."""
    command = [str(ROOT / ".lab/bin/helm"), *args,
               "--kubeconfig", str(ROOT / ".lab/kubeconfig"),
               "--kube-context", CONTEXT]
    emit("\n$ helm " + shlex.join(args))
    environment = dict(os.environ, **HELM_ENV)
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=timeout, env=environment)
    if result.stdout:
        emit(result.stdout.rstrip())
    if check and result.returncode:
        raise RuntimeError(f"Command exited {result.returncode}: helm {shlex.join(args)}")
    return result.stdout


def release_revision(name):
    data = json.loads(helm("list", "-n", "devops-homework", "-o", "json"))
    for release in data:
        if release["name"] == name:
            return int(release["revision"])
    return None


def helm_lab():
    chart = "helm/notes-chart"
    release = "notes-dev"
    ns = ["-n", "devops-homework"]
    Path(HELM_ENV["HELM_REPOSITORY_CONFIG"]).parent.mkdir(parents=True, exist_ok=True)
    apply("kubernetes-fundamentals/namespace.yaml")
    helm("version")
    helm("uninstall", release, *ns, "--ignore-not-found")

    # Authoring: lint and render before anything reaches the cluster.
    helm("lint", chart)
    helm("lint", chart, "-f", chart + "/values-prod.yaml")
    helm("template", release, chart)

    # helm install
    helm("install", release, chart, *ns, "--wait", "--timeout", "5m")
    helm("list", *ns)
    helm("status", release, *ns)
    helm("get", "values", release, *ns)
    helm("get", "manifest", release, *ns)
    k("get", "deployment,svc,configmap", "-l", "app.kubernetes.io/instance=" + release)
    retry("one replica in the development release",
          lambda: obj("deployment", release + "-notes-chart"),
          lambda d: d["status"].get("readyReplicas") == 1)
    apply("kubernetes-services/client.yaml")
    wait_pod("dns-client")
    retry("the rendered page reports the development release",
          lambda: k("exec", "dns-client", "--", "wget", "-T", "5", "-qO-",
                    "http://" + release + "-notes-chart"),
          lambda body: "development" in body and "revision: 1" in body)

    # helm upgrade onto the production values file
    helm("upgrade", release, chart, *ns, "-f", chart + "/values-prod.yaml", "--wait", "--timeout", "5m")
    helm("history", release, *ns)
    k("get", "pods", "-l", "app.kubernetes.io/instance=" + release)
    retry("three replicas after the production upgrade",
          lambda: obj("deployment", release + "-notes-chart"),
          lambda d: d["status"].get("readyReplicas") == 3)
    retry("the rendered page reports the production release at revision 2",
          lambda: k("exec", "dns-client", "--", "wget", "-T", "5", "-qO-",
                    "http://" + release + "-notes-chart"),
          lambda body: "production" in body and "revision: 2" in body)

    # A bad upgrade: the tag does not exist, so the new Pods never start.
    helm("upgrade", release, chart, *ns, "-f", chart + "/values-prod.yaml",
         "--set", "image.tag=broken-tag-does-not-exist")
    retry("the bad revision leaves a Pod unable to pull its image",
          lambda: json.loads(k("get", "pods", "-l", "app.kubernetes.io/instance=" + release,
                               "-o", "json", show=False)),
          lambda data: any(c.get("state", {}).get("waiting", {}).get("reason")
                           in ("ErrImagePull", "ImagePullBackOff")
                           for pod in data["items"]
                           for c in pod["status"].get("containerStatuses", [])),
          attempts=60)
    k("get", "pods", "-l", "app.kubernetes.io/instance=" + release)
    helm("history", release, *ns)

    # Rollback to the last good revision.
    helm("rollback", release, "2", *ns, "--wait", "--timeout", "5m")
    helm("history", release, *ns)
    helm("status", release, *ns)
    retry("rollback restored three healthy replicas",
          lambda: obj("deployment", release + "-notes-chart"),
          lambda d: d["status"].get("readyReplicas") == 3 and d["status"].get("unavailableReplicas") is None,
          attempts=60)
    k("get", "pods", "-l", "app.kubernetes.io/instance=" + release)
    retry("the page is served again after the rollback",
          lambda: k("exec", "dns-client", "--", "wget", "-T", "5", "-qO-",
                    "http://" + release + "-notes-chart"),
          lambda body: "production" in body)

    # Repositories and search.
    helm("repo", "add", "ingress-nginx", "https://kubernetes.github.io/ingress-nginx")
    helm("repo", "list")
    helm("repo", "update")
    helm("search", "repo", "ingress-nginx", "--versions", "--max-col-width", "60")
    helm("search", "hub", "nginx", "--max-col-width", "60", check=False)

    # helm uninstall
    helm("uninstall", release, *ns)
    k("get", "deployment,svc,configmap", "-l", "app.kubernetes.io/instance=" + release)
    helm("list", *ns)


def gitops():
    ns = ["-n", "argocd"]
    k("create", "namespace", "argocd", check=False)
    k(*ns, "apply", "-f",
      "https://raw.githubusercontent.com/argoproj/argo-cd/v2.13.3/manifests/install.yaml")
    # The UI extras are not needed for a reconciliation demo and this is a
    # single-node laptop cluster, so they are scaled to zero.
    for extra in ("argocd-dex-server", "argocd-notifications-controller", "argocd-applicationset-controller"):
        k(*ns, "scale", "deployment", extra, "--replicas=0", check=False)
    k(*ns, "rollout", "status", "deployment/argocd-repo-server", "--timeout=300s")
    k(*ns, "rollout", "status", "statefulset/argocd-application-controller", "--timeout=300s")
    k(*ns, "get", "pods")

    # The Application is the GitOps contract: a Git revision, a path, and a
    # destination. Nothing is applied to the cluster by hand after this point.
    k(*ns, "apply", "-f", "monitoring-observability-gitops/gitops/guestbook-application.yaml")
    k(*ns, "get", "application", "guestbook", "-o", "wide")
    retry("Argo CD synced the application from Git",
          lambda: json.loads(k(*ns, "get", "application", "guestbook", "-o", "json", show=False)),
          lambda app: app.get("status", {}).get("sync", {}).get("status") == "Synced" and
                      app.get("status", {}).get("health", {}).get("status") == "Healthy",
          attempts=90)
    k(*ns, "get", "application", "guestbook", "-o", "wide")
    k("-n", "guestbook", "get", "all")
    k(*ns, "get", "application", "guestbook",
      "-o", "jsonpath={range .status.resources[*]}{.kind}/{.name} -> {.status}{\"\\n\"}{end}")

    # Continuous reconciliation: change the cluster by hand and watch Argo CD
    # put it back, because Git is the source of truth, not kubectl.
    k("-n", "guestbook", "scale", "deployment/guestbook-ui", "--replicas=5")
    k("-n", "guestbook", "get", "deployment/guestbook-ui")
    retry("Argo CD reverted the hand-made change back to the Git revision",
          lambda: (k("-n", "guestbook", "get", "deployment/guestbook-ui"),
                   json.loads(k("-n", "guestbook", "get", "deployment/guestbook-ui",
                                "-o", "json", show=False)))[1],
          lambda d: d["spec"]["replicas"] == 1, attempts=90)
    k(*ns, "get", "application", "guestbook", "-o", "wide")

    # Self-heal also covers deletion of a managed resource.
    k("-n", "guestbook", "delete", "service", "guestbook-ui")
    retry("Argo CD recreated the Service it manages",
          lambda: k("-n", "guestbook", "get", "service", "guestbook-ui", check=False),
          lambda body: "guestbook-ui" in body and "NotFound" not in body, attempts=90)
    k("-n", "guestbook", "get", "service", "guestbook-ui")
    k(*ns, "get", "application", "guestbook", "-o", "wide")
    k(*ns, "get", "events", "--field-selector", "involvedObject.name=guestbook", check=False)


FINAL = "final-devops-project/"


def kn(namespace, *args, **kwargs):
    """kubectl against an explicit namespace, overriding the runner default."""
    return k("-n", namespace, *args, **kwargs)


def ingress_controller():
    """Install ingress-nginx once; kind needs the node label it selects on."""
    k("label", "node", "vibhuti-devops-control-plane", "ingress-ready=true",
      "--overwrite")
    kn("ingress-nginx", "apply", "-f",
       "https://raw.githubusercontent.com/kubernetes/ingress-nginx/"
       "controller-v1.12.0/deploy/static/provider/kind/deploy.yaml")
    kn("ingress-nginx", "rollout", "status", "deployment/ingress-nginx-controller",
       "--timeout=300s")
    # The controller's validating webhook has its own Service, and it starts
    # answering a little after the Deployment reports rolled out. Creating an
    # Ingress before then fails with a connection refused from the API server.
    retry("the ingress-nginx admission webhook is answering",
          lambda: endpoints("ingress-nginx-controller-admission", "ingress-nginx"),
          lambda eps: bool(eps), attempts=60)
    kn("ingress-nginx", "get", "pods")


def final_project():
    ns = "notes"
    base = FINAL + "kubernetes/"
    run(str(ROOT / ".lab/bin/kind"), "--name", "vibhuti-devops", "load", "docker-image",
        "notes-app:local")
    ingress_controller()

    kn("notes", "apply", "-f", base + "00-namespace.yaml")
    # The token is generated here and never written to a file in the repository.
    kn(ns, "delete", "secret", "notes-secret", "--ignore-not-found")
    token = secrets.token_hex(24)
    k("-n", ns, "create", "secret", "generic", "notes-secret",
      "--from-literal=API_TOKEN=" + token, show=False)
    emit("\n$ kubectl -n notes create secret generic notes-secret --from-literal=API_TOKEN=<generated>")
    emit("secret/notes-secret created")
    kn(ns, "get", "secret", "notes-secret")

    kn(ns, "apply", "-f", base + "01-configmap.yaml", "-f", base + "03-pvc.yaml",
       "-f", base + "04-deployment.yaml", "-f", base + "05-service.yaml",
       "-f", base + "06-ingress.yaml", "-f", base + "07-hpa.yaml")
    # A Pod reads a Secret when it starts. Replacing the Secret afterwards does
    # not restart anything, so a re-run would leave the old token in the
    # running containers; the restart makes the new value take effect.
    kn(ns, "rollout", "restart", "deployment/notes")
    kn(ns, "rollout", "status", "deployment/notes", "--timeout=300s")
    kn(ns, "get", "pods,svc,ingress,hpa,pvc", "-o", "wide")
    retry("the 1Gi claim is bound",
          lambda: json.loads(kn(ns, "get", "pvc", "notes-data", "-o", "json", show=False)),
          lambda claim: claim["status"]["phase"] == "Bound")

    # The container runs unprivileged on a read-only root filesystem.
    # A rollout can report finished while the replaced Pods are still
    # terminating, so pick one that is actually Ready.
    # A rollout can report finished while the Pods it replaced are still
    # Ready and terminating, and exec into one of those is killed mid-command.
    # Only Pods with no deletion timestamp are candidates.
    pod = retry("a Ready Pod that is not being terminated",
                lambda: [item["metadata"]["name"] for item in json.loads(
                    kn(ns, "get", "pods", "-l", "app=notes",
                       "--field-selector=status.phase=Running", "-o", "json",
                       show=False))["items"]
                    if not item["metadata"].get("deletionTimestamp")
                    and all(c["status"] == "True" for c in item["status"]["conditions"]
                            if c["type"] == "Ready")],
                lambda names: bool(names))[0]
    retry("the container runs as the unprivileged user from the image",
          lambda: kn(ns, "exec", pod, "--", "id", check=False),
          lambda body: "uid=10001" in body, attempts=20)
    kn(ns, "exec", pod, "--", "sh", "-c",
       "touch /srv/should-fail 2>&1 || echo 'read-only root filesystem: write refused'",
       check=False)
    kn(ns, "exec", pod, "--", "sh", "-c", "touch /data/writable && echo '/data is writable'")

    # Probes, metrics and the Secret, through the Service.
    apply("kubernetes-services/client.yaml")
    wait_pod("dns-client")
    url = "http://notes.notes.svc.cluster.local"
    retry("the readiness endpoint reports the volume is usable",
          lambda: k("exec", "dns-client", "--", "wget", "-T", "5", "-qO-", url + "/readyz"),
          lambda body: '"status": "ready"' in body or '"status":"ready"' in body, attempts=45)
    k("exec", "dns-client", "--", "wget", "-T", "5", "-qO-", url + "/healthz")
    retry("the Secret reached the container: an unauthenticated write is refused",
          lambda: k("exec", "dns-client", "--", "sh", "-c",
                    "wget -T 5 -qO- --post-data='{\"title\":\"no token\"}' "
                    "--header='Content-Type: application/json' " + url + "/api/notes "
                    "2>&1 || echo 'rejected: 401 unauthorised'"),
          lambda body: "401" in body or "rejected" in body)
    # The token is not echoed into the transcript.
    emit("\n$ kubectl -n devops-homework exec dns-client -- wget -qO- "
         "--post-data='{\"title\": \"deployed to kubernetes\"}' "
         "--header='X-API-Token: <generated>' " + url + "/api/notes")
    emit(retry("an authenticated write is accepted",
               lambda: k("exec", "dns-client", "--", "sh", "-c",
                         "wget -T 5 -qO- "
                         "--post-data='{\"title\":\"deployed to kubernetes\",\"body\":\"session 21\"}' "
                         "--header='Content-Type: application/json' "
                         "--header='X-API-Token: " + token + "' " + url + "/api/notes",
                         show=False, check=False),
               lambda body: "deployed to kubernetes" in body, attempts=30).strip())
    retry("the note is readable back through the API",
          lambda: k("exec", "dns-client", "--", "wget", "-T", "5", "-qO-", url + "/api/notes"),
          lambda body: "deployed to kubernetes" in body)

    # The volume outlives the Pod that wrote to it.
    kn(ns, "delete", "pod", pod, "--wait=true")
    kn(ns, "rollout", "status", "deployment/notes", "--timeout=300s")
    retry("the note written before the Pod was deleted is still served",
          lambda: k("exec", "dns-client", "--", "wget", "-T", "5", "-qO-", url + "/api/notes"),
          lambda body: "deployed to kubernetes" in body, attempts=45)

    # Ingress routing, through the controller rather than the Service.
    with (ROOT / ".lab/port-forward.log").open("w") as log:
        forward = subprocess.Popen([*K, "-n", "ingress-nginx", "port-forward",
                                    "service/ingress-nginx-controller", "18080:80"],
                                   stdout=log, stderr=subprocess.STDOUT)
        try:
            retry("the Ingress routes notes.devops.test to the Service",
                  lambda: run("curl", "--fail", "--silent", "--show-error", "--max-time", "5",
                              "-H", "Host: notes.devops.test", "http://127.0.0.1:18080/"),
                  lambda body: "deployed to kubernetes" in body, attempts=45)
            run("curl", "--fail", "--silent", "--show-error", "--max-time", "5",
                "-H", "Host: notes.devops.test", "http://127.0.0.1:18080/healthz")
            metrics = retry("the application exports Prometheus metrics",
                            lambda: run("curl", "--fail", "--silent", "--max-time", "5",
                                        "-H", "Host: notes.devops.test",
                                        "http://127.0.0.1:18080/metrics", show=False),
                            lambda body: "notes_stored_total" in body)
            emit("\n$ curl -H 'Host: notes.devops.test' http://127.0.0.1:18080/metrics | grep notes_")
            emit("\n".join(line for line in metrics.splitlines()
                           if line.startswith(("notes_stored_total", "notes_storage_writable"))))
        finally:
            forward.terminate()
            forward.wait(timeout=15)

    # Autoscaling.
    kn(ns, "get", "hpa", "notes")
    retry("the HPA reads CPU rather than <unknown>",
          lambda: json.loads(kn(ns, "get", "hpa", "notes", "-o", "json", show=False)),
          lambda h: (h.get("status", {}).get("currentMetrics") or [{}])[0]
                    .get("resource", {}).get("current", {}).get("averageUtilization") is not None,
          attempts=60)
    k("-n", ns, "apply", "-f", FINAL + "kubernetes/load-generator.yaml")
    kn(ns, "rollout", "status", "deployment/notes-load", "--timeout=240s")
    retry("the HPA scaled the application out under load",
          lambda: (kn(ns, "get", "hpa", "notes"),
                   json.loads(kn(ns, "get", "hpa", "notes", "-o", "json", show=False)))[1],
          lambda h: (h["status"].get("currentReplicas") or 0) > 2, attempts=90)
    kn(ns, "top", "pods", "-l", "app=notes")
    kn(ns, "delete", "deployment", "notes-load", "--wait=true")
    retry("the HPA returned to its two-replica floor",
          lambda: (kn(ns, "get", "hpa", "notes"),
                   json.loads(kn(ns, "get", "hpa", "notes", "-o", "json", show=False)))[1],
          lambda h: h["status"].get("currentReplicas") == 2, attempts=150)

    # NetworkPolicy, applied last so the before and after are both visible.
    kn(ns, "apply", "-f", base + "08-networkpolicy.yaml")
    kn(ns, "get", "networkpolicies")
    kn(ns, "describe", "networkpolicy", "notes-allow")
    kn(ns, "get", "all,pvc,ingress,hpa,networkpolicy")


def final_monitoring():
    ns = "notes"
    kn("monitoring", "apply", "-f", FINAL + "monitoring/prometheus-k8s.yaml")
    kn("monitoring", "rollout", "status", "deployment/prometheus", "--timeout=300s")
    kn("monitoring", "get", "pods,svc")
    # The default-deny NetworkPolicy in the notes namespace allows the
    # monitoring namespace in by label; this is also a test of that rule.
    kn(ns, "get", "networkpolicies")
    with (ROOT / ".lab/port-forward.log").open("w") as log:
        forward = subprocess.Popen([*K, "-n", "monitoring", "port-forward",
                                    "service/prometheus", "19090:9090"],
                                   stdout=log, stderr=subprocess.STDOUT)
        try:
            def query(expression):
                return json.loads(run("curl", "--fail", "--silent", "--max-time", "10",
                                      "--get", "http://127.0.0.1:19090/api/v1/query",
                                      "--data-urlencode", "query=" + expression, show=False))

            retry("Prometheus is ready inside the cluster",
                  lambda: run("curl", "--fail", "--silent", "--max-time", "10",
                              "http://127.0.0.1:19090/-/ready", show=False),
                  lambda body: "Ready" in body, attempts=60)
            targets = retry("service discovery found the Notes Pods",
                            lambda: json.loads(run("curl", "--fail", "--silent", "--max-time", "10",
                                                   "http://127.0.0.1:19090/api/v1/targets?state=active",
                                                   show=False)),
                            lambda data: len([t for t in data["data"]["activeTargets"]
                                              if t["labels"].get("namespace") == "notes"
                                              and t["health"] == "up"]) >= 2,
                            attempts=60)
            emit("\n$ curl http://127.0.0.1:19090/api/v1/targets")
            for target in targets["data"]["activeTargets"]:
                emit("%s\t%s\t%s" % (target["labels"].get("job"), target["scrapeUrl"], target["health"]))
            emit("\n$ promql notes_stored_total")
            for series in query("notes_stored_total")["data"]["result"]:
                emit("pod %s stored notes: %s" % (series["metric"].get("pod"), series["value"][1]))
            emit("\n$ promql notes_storage_writable")
            for series in query("notes_storage_writable")["data"]["result"]:
                emit("pod %s storage writable: %s" % (series["metric"].get("pod"), series["value"][1]))
            emit("\n$ promql sum by (endpoint) (notes_http_requests_total)")
            for series in query("sum by (endpoint) (notes_http_requests_total)")["data"]["result"]:
                emit("%s\t%s requests" % (series["metric"].get("endpoint"), series["value"][1]))
            emit("\n$ promql count(up == 1)")
            emit("targets up: " + query("count(up == 1)")["data"]["result"][0]["value"][1])
            rules = json.loads(run("curl", "--fail", "--silent", "--max-time", "10",
                                   "http://127.0.0.1:19090/api/v1/rules", show=False))
            emit("\n$ curl http://127.0.0.1:19090/api/v1/rules")
            for group in rules["data"]["groups"]:
                for rule in group["rules"]:
                    emit("%s/%s: %s" % (group["name"], rule["name"], rule.get("state", "-")))
            emit("\nPASS: the alert rules are loaded and none is firing")
        finally:
            forward.terminate()
            forward.wait(timeout=15)


def final_troubleshooting():
    ns = "notes"
    base = FINAL + "kubernetes/"
    faults = FINAL + "troubleshooting/faults/"

    def restore_deployment():
        kn(ns, "apply", "-f", base + "04-deployment.yaml")
        kn(ns, "rollout", "status", "deployment/notes", "--timeout=300s")

    def fault_pods():
        return json.loads(kn(ns, "get", "pods", "-l", "app=notes", "-o", "json", show=False))["items"]

    def waiting_pods(*reasons):
        return [pod["metadata"]["name"] for pod in fault_pods()
                if any(c.get("state", {}).get("waiting", {}).get("reason") in reasons
                       for c in pod["status"].get("containerStatuses", []))]

    def oom_pods():
        names = []
        for pod in fault_pods():
            for c in pod["status"].get("containerStatuses", []):
                terminated = (c.get("lastState", {}).get("terminated")
                              or c.get("state", {}).get("terminated") or {})
                if (terminated.get("reason") == "OOMKilled"
                        or c.get("state", {}).get("waiting", {}).get("reason") == "CrashLoopBackOff"):
                    names.append(pod["metadata"]["name"])
                    break
        return names

    # Fault 1: an image tag that does not exist.
    emit("\n=== Fault 1: the Deployment points at an image tag that does not exist ===")
    kn(ns, "patch", "deployment", "notes", "--type=strategic",
       "--patch-file", faults + "01-wrong-image-tag.yaml")
    broken = retry("new Pods cannot pull the image",
                   lambda: waiting_pods("ErrImagePull", "ImagePullBackOff"),
                   lambda names: bool(names), attempts=60)[0]
    kn(ns, "get", "pods", "-l", "app=notes")
    kn(ns, "rollout", "status", "deployment/notes", "--timeout=20s", check=False)
    kn(ns, "get", "deployment", "notes")
    kn(ns, "describe", "pod", broken)
    # The old ReplicaSet is still serving: maxUnavailable is 0, so a failed
    # rollout is not an outage.
    retry("the running version still answers while the rollout is stuck",
          lambda: k("exec", "dns-client", "--", "wget", "-T", "5", "-qO-",
                    "http://notes.notes.svc.cluster.local/healthz"),
          lambda body: '"status": "ok"' in body or '"status":"ok"' in body)
    kn(ns, "rollout", "undo", "deployment/notes")
    kn(ns, "rollout", "status", "deployment/notes", "--timeout=300s")
    kn(ns, "get", "pods", "-l", "app=notes")

    # Fault 2: the Service selector no longer matches the Pods.
    emit("\n=== Fault 2: the Service selector no longer matches the Pod labels ===")
    kn(ns, "apply", "-f", faults + "02-wrong-service-selector.yaml")
    retry("the Service lost every endpoint",
          lambda: endpoints("notes", ns), lambda eps: eps == [])
    kn(ns, "get", "endpointslices", "-l", "kubernetes.io/service-name=notes")
    kn(ns, "get", "pods", "--show-labels", "-l", "app=notes")
    kn(ns, "describe", "service", "notes")
    k("exec", "dns-client", "--", "sh", "-c",
      "nslookup notes.notes.svc.cluster.local >/dev/null 2>&1 && echo 'DNS still resolves the name'",
      check=False)
    k("exec", "dns-client", "--", "sh", "-c",
      "wget -T 3 -qO- http://notes.notes.svc.cluster.local/healthz || "
      "echo 'connection refused: the Service has no backend'", check=False)
    kn(ns, "apply", "-f", base + "05-service.yaml")
    retry("endpoints returned once the selector matched again",
          lambda: endpoints("notes", ns), lambda eps: len(eps) >= 2)
    kn(ns, "get", "endpointslices", "-l", "kubernetes.io/service-name=notes")

    # Fault 3: a Secret key that does not exist.
    emit("\n=== Fault 3: the Deployment references a Secret key that does not exist ===")
    kn(ns, "patch", "deployment", "notes", "--type=strategic",
       "--patch-file", faults + "03-missing-secret-key.yaml")
    broken = retry("the new Pod cannot be built from its configuration",
                   lambda: waiting_pods("CreateContainerConfigError"),
                   lambda names: bool(names), attempts=60)[0]
    kn(ns, "get", "pods", "-l", "app=notes")
    kn(ns, "describe", "pod", broken)
    kn(ns, "get", "secret", "notes-secret", "-o", "jsonpath={.data}")
    kn(ns, "rollout", "undo", "deployment/notes")
    kn(ns, "rollout", "status", "deployment/notes", "--timeout=300s")

    # Fault 4: a readiness probe pointed at a path the app does not serve.
    emit("\n=== Fault 4: the readiness probe points at a path the application does not serve ===")
    kn(ns, "patch", "deployment", "notes", "--type=strategic",
       "--patch-file", faults + "04-probe-on-wrong-path.yaml")
    unready = retry("a Pod is Running but never becomes Ready",
                    lambda: [pod["metadata"]["name"] for pod in fault_pods()
                             if pod["status"]["phase"] == "Running"
                             and not pod["metadata"].get("deletionTimestamp")
                             and not any(c["type"] == "Ready" and c["status"] == "True"
                                         for c in pod["status"]["conditions"])],
                    lambda names: bool(names), attempts=90)[0]
    kn(ns, "get", "pods", "-l", "app=notes")
    kn(ns, "describe", "pod", unready)
    # Running, zero restarts, and absent from the Service endpoints.
    emit("\nThe unready Pod's address is not in the Service's EndpointSlice:")
    kn(ns, "get", "endpointslices", "-l", "kubernetes.io/service-name=notes", "-o", "wide")
    kn(ns, "rollout", "undo", "deployment/notes")
    kn(ns, "rollout", "status", "deployment/notes", "--timeout=300s")

    # Fault 5: a memory limit below what the process needs.
    emit("\n=== Fault 5: the memory limit is below what the process needs to start ===")
    kn(ns, "patch", "deployment", "notes", "--type=strategic",
       "--patch-file", faults + "05-memory-limit-too-low.yaml")
    broken = retry("the container is killed by the kernel for exceeding its limit",
                   oom_pods, lambda names: bool(names), attempts=90)[0]
    kn(ns, "get", "pods", "-l", "app=notes")
    kn(ns, "describe", "pod", broken)
    kn(ns, "rollout", "undo", "deployment/notes")
    restore_deployment()

    emit("\n=== Everything restored ===")
    kn(ns, "get", "pods,svc,endpointslices,hpa", "-o", "wide")
    retry("the application serves normally again",
          lambda: k("exec", "dns-client", "--", "wget", "-T", "5", "-qO-",
                    "http://notes.notes.svc.cluster.local/api/notes"),
          lambda body: "deployed to kubernetes" in body, attempts=45)
    kn(ns, "rollout", "history", "deployment/notes")


SECTIONS = {"01-fundamentals": fundamentals, "02-core": core, "03-strategies": strategies,
            "04-lifecycle": lifecycle, "05-services": services, "06-ingress": ingress,
            "07-storage": storage, "08-hpa-probes": hpa_probes,
            "09-webapp-mini-project": webapp,
            "10-troubleshooting": troubleshooting,
            "11-triage-mini-project": triage_project,
            "12-helm": helm_lab, "13-gitops": gitops,
            "14-final-project": final_project,
            "15-final-monitoring": final_monitoring,
            "16-final-troubleshooting": final_troubleshooting}


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
