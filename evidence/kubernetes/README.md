# Kubernetes execution evidence

**Vibhuti Bhatnagar · 24BCS10288 · vibhuti.24bcs10288@sst.scaler.com**

These are actual command transcripts from this repository's dedicated local kind cluster on
20 September 2026 (Asia/Kolkata). UTC timestamps appear at the start of the session files.
They were captured by [the lab runner](../../scripts/run-kubernetes-labs.py), not copied from
the reference repository. Expected failures in lifecycle exercises and temporary retry errors
remain visible in the output. Trailing spaces were removed for clean Git diffs; the
command output and results are otherwise preserved.

| Evidence | What to inspect |
| --- | --- |
| [Fundamentals](01-fundamentals.txt) | Server version, Ready node, CoreDNS, namespace, ServiceAccount and client Pod. |
| [Core objects](02-core.txt) | New ReplicaSet Pod identities, v1/v2/rollback responses, DaemonSet and standalone Pod deletion. |
| [Release strategies](03-strategies.txt) | Blue/green endpoints and responses, canary endpoints/requests, Recreate events and v2. |
| [Lifecycle](04-lifecycle.txt) | Twelve lifecycle and probe exercises, failure reasons, init/sidecar logs and graceful termination. |
| [Initial lifecycle attempt](04-lifecycle-initial-attempt.txt) | Original timeout from sampling only the changing waiting reason, before event-based detection was added. |
| [Services](05-services.txt) | DNS, ClusterIP, host-to-NodePort traffic, headless names and broken-selector recovery. |
| [Initial DNS attempt](05-services-initial-attempt.txt) | BusyBox short-name lookup returning the right address alongside failed search-suffix candidates. |
| [Empty EndpointSlice attempt](05-services-empty-endpoints-attempt.txt) | Intermediate parser failure for `endpoints: null`, corrected before the final run. |
| [Ingress and configuration](06-ingress.txt) | Frontend/API routes, Secret presence, environment before/after restart and verified TLS. |
| [Server validation](server-validation.txt) | Strict API dry-runs of every API manifest. |
| [Local validation](local-validation.txt) | Manifest relationships, label syntax, API behavior and Markdown links. |

See [validation scope](../../KUBERNETES-VALIDATION.md) and
[setup/reproduction instructions](../../kubernetes-fundamentals/README.md).
The runner retains the cluster for inspection; remove only that cluster with the documented
kind cleanup command when finished.
