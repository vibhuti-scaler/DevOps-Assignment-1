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
entries = []
for p in sorted(root.glob("kubernetes-*/*.yaml")) + sorted(
    root.glob("kubernetes-*/*/*.yaml")
):
    if p.name == "kind-config.yaml":
        continue  # kind configuration is not a Kubernetes API object.
    for doc in yaml.safe_load_all(p.read_text()):
        entries.append((p.relative_to(root), doc))
for path, d in entries:
    for metadata in (d.get("metadata", {}), d.get("spec", {}).get("template", {}).get("metadata", {})):
        for key, value in metadata.get("labels", {}).items():
            assert isinstance(value, str) and len(value) <= 63, (path, key, value)
            assert not value or re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?", value), (path, key, value)
    if d["kind"] not in ("Namespace", "ClusterRole", "ClusterRoleBinding", "IngressClass"):
        assert d["metadata"]["namespace"] == "devops-homework", path
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
services = {d["metadata"]["name"]: d for _, d in entries if d["kind"] == "Service"}
configs = {d["metadata"]["name"]: d for _, d in entries if d["kind"] == "ConfigMap"}
for path, d in entries:
    if d["kind"] == "Service" and d["spec"].get("selector"):
        selected = [
            w
            for w in workloads
            if all(
                w["spec"]["template"]["metadata"]["labels"].get(k) == v
                for k, v in d["spec"]["selector"].items()
            )
        ]
        assert selected, path
        for w in selected:
            ports = [
                p
                for c in w["spec"]["template"]["spec"]["containers"]
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
                assert (ref["name"], ref["key"]) == ("demo-credentials", "DEMO_TOKEN")
    for vol in spec.get("volumes", []):
        if "configMap" in vol:
            assert vol["configMap"]["name"] in configs
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
