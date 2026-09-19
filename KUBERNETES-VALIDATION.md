# Kubernetes validation

- **Name:** Vibhuti Bhatnagar
- **Roll no:** 24BCS10288
- **Email:** vibhuti.24bcs10288@sst.scaler.com
- **Date:** 20 September 2026 (Asia/Kolkata; logs use UTC)

This report covers the new Kubernetes sections. Existing Docker screenshots and transcripts
are retained from the earlier assignment; they are not claimed as newly captured.

**Result: all six live sections passed.** The manifests, application checks and relative
Markdown links also passed validation. Earlier failures and their corrections are recorded below.

## Environment and commands

The dedicated `vibhuti-devops` kind cluster uses Kubernetes v1.35.0, containerd, kindnet and
CoreDNS. The tools used were kind v0.33.0, kubectl v1.36.1 and Docker 29.7.2 on macOS ARM64.
The kind binary's SHA-256 was checked against its publisher's release checksum. The kubeconfig
is stored in ignored `.lab/kubeconfig`; the normal kubeconfig is not needed by these scripts.

From the repository root, after creating the cluster as described in
[Kubernetes Fundamentals](kubernetes-fundamentals/README.md):

```bash
python3 -m venv .lab/venv
.lab/venv/bin/pip install -r scripts/requirements.txt
.lab/venv/bin/python scripts/validate-kubernetes.py
bash scripts/validate-server.sh
bash scripts/run-kubernetes-labs.sh
```

## Static and API validation

The [Python validator](scripts/validate-kubernetes.py) checks 51 Kubernetes objects across
37 API manifest files. It checks label syntax, namespaces, workload selectors, Service target
ports, Ingress backends, ConfigMap/Secret references and StatefulSet discovery. It executes
the actual Python API source stored in the ConfigMap and checks its three success routes,
three 404 routes, configuration values, token presence/absence and absence of token disclosure.
Relative Markdown file links are checked across the repository.

[Strict server validation](evidence/kubernetes/server-validation.txt) submits each manifest
individually with `--dry-run=server --validate=strict`. The kind tool configuration is excluded
because it is not a Kubernetes API object. The two versions of a Deployment are alternatives,
so the complete directory is never recursively applied as one lab.

The reference frontend contained a label value with spaces. It was corrected to `frontend-v1`;
the validator now catches that class of error. [Reference details](REFERENCES.md).

## Live execution

The [runner](scripts/run-kubernetes-labs.py) records commands and output, checks response content,
and stops on an unexpected failure. Failure examples deliberately create Pending, Failed,
CrashLoopBackOff and ImagePullBackOff conditions; those are successful exercises when observed.
The evidence index below links the captured results.

See [all raw execution logs](evidence/kubernetes/README.md).

| Section | Observed result |
| --- | --- |
| Fundamentals | Node Ready, healthy CoreDNS, namespace, default ServiceAccount and ready client. |
| Core objects | Three replacement Pod identities; v1 → v2 → v1 HTTP responses; DaemonSet ready; standalone Pod stayed deleted. |
| Strategies | Blue → green response and endpoints; four canary endpoints and mixed responses; Recreate v2 and controller events. |
| Lifecycle | All twelve examples passed, including liveness restart, startup without restart, init/sidecar logs and SIGTERM cleanup. |
| Services | A/CNAME queries, ClusterIP and host NodePort HTTP, StatefulSet discovery, empty endpoints and selector recovery. |
| Ingress/configuration | Frontend and three API routes, Secret presence without disclosure, coursework → staging after restart, and both TLS hosts verified against the generated certificate. |

The [initial lifecycle attempt](evidence/kubernetes/04-lifecycle-initial-attempt.txt) timed out
while looking only for the sampled `CrashLoopBackOff` waiting reason. Read-only inspection
confirmed actual backoff events and restarts. The runner now accepts that waiting reason or
BackOff events for the exact Pod UID together with a positive restart count. It also handles
the corresponding image-pull event/state transition. The initial failed attempt is retained.

The [initial DNS attempt](evidence/kubernetes/05-services-initial-attempt.txt) also records a
BusyBox behavior: a short-name query returned the correct Service address but exited nonzero
for other search-suffix candidates. The runner now queries absolute names with explicit A
or CNAME record types. Separate HTTP requests continue to verify short-name resolution.
An [intermediate Service run](evidence/kubernetes/05-services-empty-endpoints-attempt.txt)
found that an empty EndpointSlice can serialize `endpoints` as `null`; the runner now treats
that as an empty list when verifying the deliberately broken selector.

The TLS checks initially returned 404 because Traefik needs TLS-router annotations in addition
to `spec.tls`. The optional manifest was corrected and applied during the captured run; both
HTTPS requests then passed certificate verification. Those failed attempts remain in the
Ingress transcript, and the final manifest passed a further strict server dry-run.

After collecting the evidence, the dedicated kind cluster was removed to release resources.
Use the fundamentals setup commands to reproduce the work. The runner itself retains its
cluster until the documented cleanup command is run.

## Scope and limitations

- A single-node local cluster demonstrates reconciliation, routing and configuration behavior;
  it does not establish multi-node availability or production performance.
- Canary Pod counts describe endpoint proportions, not a guaranteed request percentage.
- Recreate events and the v2 response are checked; continuous availability is not measured.
- The optional LoadBalancer object is accepted, but no external load balancer is installed.
  Its pending external IP is documented; external LoadBalancer traffic is not claimed.
- Transcripts contain actual command output. They are not browser or Terminal screenshots.
- Disposable Secret values, private keys and kubeconfig contents are not committed. HTTP
  responses report only whether the demonstration token is present.
