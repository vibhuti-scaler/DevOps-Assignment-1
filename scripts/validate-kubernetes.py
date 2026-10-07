"""Validate adapted manifest relationships, label syntax, API behavior and README links."""
import json
import os
import re
import threading
from http.server import HTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import yaml

root = Path(__file__).resolve().parents[1]

# Sessions 9-12 declare metadata.namespace on every object. The later sessions
# are applied with an explicit -n by the runner, so a declared namespace is
# optional there and only checked against the set of namespaces the labs use.
PINNED_NAMESPACE_DIRS = (
    "kubernetes-fundamentals",
    "kubernetes-core-objects",
    "kubernetes-services",
    "kubernetes-ingress-configmaps-secrets",
)
LAB_NAMESPACES = {"devops-homework", "production-webapp", "notes", "monitoring",
                  "argocd", "task-api", "ingress-nginx"}

# Services that are supposed to select nothing: they exist to demonstrate an
# empty EndpointSlice. The check below is inverted for these rather than
# skipped, so a typo that accidentally made one of them work would be caught.
SELECT_NOTHING = {
    "kubernetes-troubleshooting/05-service-dns/broken-service.yaml",
    "kubernetes-troubleshooting/mini-project/broken-service.yaml",
}

# Every directory of Kubernetes manifests in the repository, not only the
# session folders: the CI/CD, DevSecOps and final-project manifests are checked
# by the same rules.
MANIFEST_GLOBS = (
    "kubernetes-*/*.yaml",
    "kubernetes-*/*/*.yaml",
    "cicd-github-actions/kubernetes/*.yaml",
    "devsecops/kubernetes/*.yaml",
    "final-devops-project/kubernetes/*.yaml",
    "final-devops-project/troubleshooting/faults/*.yaml",
)

entries = []
fault_entries = []
for p in sorted({q for pattern in MANIFEST_GLOBS for q in root.glob(pattern)}):
    if p.name == "kind-config.yaml":
        continue  # kind configuration is not a Kubernetes API object.
    if "troubleshooting/faults" in p.as_posix():
        # Strategic-merge patches, not complete objects. They are checked
        # separately below.
        for doc in yaml.safe_load_all(p.read_text()):
            fault_entries.append((p.relative_to(root), doc))
        continue
    for doc in yaml.safe_load_all(p.read_text()):
        entries.append((p.relative_to(root), doc))
for path, d in entries:
    for metadata in (d.get("metadata", {}), d.get("spec", {}).get("template", {}).get("metadata", {})):
        for key, value in metadata.get("labels", {}).items():
            assert isinstance(value, str) and len(value) <= 63, (path, key, value)
            assert not value or re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?", value), (path, key, value)
    if d["kind"] not in ("Namespace", "ClusterRole", "ClusterRoleBinding", "IngressClass"):
        declared = d["metadata"].get("namespace")
        if path.parts[0] in PINNED_NAMESPACE_DIRS:
            assert declared == "devops-homework", path
        else:
            assert declared is None or declared in LAB_NAMESPACES, (path, declared)
    if d["kind"] in ("Deployment", "ReplicaSet", "StatefulSet", "DaemonSet"):
        labels = d["spec"]["template"]["metadata"]["labels"]
        assert all(
            labels.get(k) == v for k, v in d["spec"]["selector"]["matchLabels"].items()
        ), path
workloads = [
    d
    for _, d in entries
    if d["kind"] in ("Deployment", "ReplicaSet", "StatefulSet", "DaemonSet")
]
# A Service can select a bare Pod as well as a workload's template, so both
# label sources feed the selector check below.
selectable = [
    (d["spec"]["template"]["metadata"]["labels"], d["spec"]["template"]["spec"])
    for d in workloads
] + [
    (d["metadata"].get("labels", {}), d["spec"])
    for _, d in entries
    if d["kind"] == "Pod"
]
services = {d["metadata"]["name"]: d for _, d in entries if d["kind"] == "Service"}
configs = {d["metadata"]["name"]: d for _, d in entries if d["kind"] == "ConfigMap"}
for path, d in entries:
    if d["kind"] == "Service" and d["spec"].get("selector"):
        selected = [
            (labels, pod_spec)
            for labels, pod_spec in selectable
            if all(labels.get(k) == v for k, v in d["spec"]["selector"].items())
        ]
        if str(path) in SELECT_NOTHING:
            assert not selected, (path, "this Service is supposed to select nothing")
            continue
        assert selected, path
        for _, pod_spec in selected:
            ports = [
                p
                for c in pod_spec["containers"]
                for p in c.get("ports", [])
            ]
            for p in d["spec"]["ports"]:
                assert any(
                    p["targetPort"] == c["name"]
                    if isinstance(p["targetPort"], str)
                    else p["targetPort"] == c["containerPort"]
                    for c in ports
                ), path
    if d["kind"] == "Ingress":
        for rule in d["spec"]["rules"]:
            for p in rule["http"]["paths"]:
                backend = p["backend"]["service"]
                s = services[backend["name"]]
                assert any(
                    x["port"] == backend["port"]["number"] for x in s["spec"]["ports"]
                ), path
for d in workloads:
    spec = d["spec"]["template"]["spec"]
    if d["kind"] == "StatefulSet":
        assert services[d["spec"]["serviceName"]]["spec"]["clusterIP"] == "None"
    for c in spec["containers"]:
        for env in c.get("envFrom", []):
            assert env["configMapRef"]["name"] in configs
        for env in c.get("env", []):
            ref = env.get("valueFrom", {}).get("secretKeyRef")
            if ref:
                # Secrets are always created out of band, never committed. These
                # are the only two contracts the manifests may reference.
                assert (ref["name"], ref["key"]) in {
                    ("demo-credentials", "DEMO_TOKEN"),
                    ("notes-secret", "API_TOKEN"),
                }, (ref["name"], ref["key"])
    for vol in spec.get("volumes", []):
        if "configMap" in vol:
            assert vol["configMap"]["name"] in configs
# The injected faults are strategic-merge patches against one Deployment, so
# each one must name that Deployment and change nothing else by accident.
for path, d in fault_entries:
    assert d["metadata"]["name"] in ("notes",), path
    assert d["metadata"]["namespace"] == "notes", path
    assert d["kind"] in ("Deployment", "Service"), path
    if d["kind"] == "Deployment":
        containers = d["spec"]["template"]["spec"]["containers"]
        assert [c["name"] for c in containers] == ["notes"], path

v1 = yaml.safe_load((root / "kubernetes-core-objects/deployment-v1.yaml").read_text())
v2 = yaml.safe_load((root / "kubernetes-core-objects/deployment-v2.yaml").read_text())
assert (
    v1["metadata"] == v2["metadata"]
    and v1["spec"]["selector"] == v2["spec"]["selector"]
)
assert v1["spec"]["template"] != v2["spec"]["template"]
print(
    f"PASS: {len(entries)} Kubernetes objects; labels, namespaces, workload selectors, Service target ports, Ingress backends, ConfigMap references, external Secret contract, StatefulSet service, rollout selectors"
)
source = configs["demo-backend-code"]["data"]["app.py"]
ns = {"__name__": "homework_check"}
exec(compile(source, "backend-code.yaml:app.py", "exec"), ns)  # noqa: S102 - Test the checked-in demo handler.
os.environ.update(
    {
        "ENVIRONMENT": "coursework",
        "LOG_LEVEL": "INFO",
        "DEFAULT_CURRENCY": "INR",
        "DEMO_TOKEN": "public-validation-fixture",
    }
)
server = HTTPServer(("127.0.0.1", 0), ns["Handler"])
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    for path in ("/api", "/api/", "/api/health"):
        with urlopen(f"http://127.0.0.1:{server.server_port}" + path) as response:
            raw = response.read()
            body = json.loads(raw)
            assert body == {
                "service": "DevOps session 12 API",
                "environment": "coursework",
                "log_level": "INFO",
                "currency": "INR",
                "secret_loaded": True,
            }
            assert b"public-validation-fixture" not in raw
    for path in ("/", "/apix", "/api/missing"):
        try:
            urlopen(f"http://127.0.0.1:{server.server_port}" + path)
        except HTTPError as e:
            assert e.code == 404
        else:
            raise AssertionError(path)
    del os.environ["DEMO_TOKEN"]
    with urlopen(f"http://127.0.0.1:{server.server_port}/api/health") as response:
        assert json.load(response)["secret_loaded"] is False
finally:
    server.shutdown()
    server.server_close()
    thread.join()
print(
    "PASS: API three success routes, three 404 routes, configuration values, secret presence/absence, and no secret-value disclosure"
)
# Markdown links are checked without fetching external URLs.
count = 0
for p in root.rglob("*.md"):
    if any(part in (".git", ".lab", "node_modules") for part in p.parts):
        continue
    if not p.exists():
        continue
    for link in re.findall(r"\]\(([^)]+)\)", p.read_text()):
        if "://" in link or link.startswith("#"):
            continue
        target = link.split("#")[0]
        assert (p.parent / target).exists(), (p, link)
        count += 1
print(f"PASS: {count} relative Markdown file links")
