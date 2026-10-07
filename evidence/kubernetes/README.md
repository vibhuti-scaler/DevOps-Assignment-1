# Kubernetes execution evidence

**Vibhuti Bhatnagar · 24BCS10288 · vibhuti.24bcs10288@sst.scaler.com**

These are actual command transcripts from this repository's dedicated local kind cluster.
Sections 01-06 were captured on 20 September 2026 and sections 07-16 on 7 October 2026
(Asia/Kolkata). UTC timestamps appear at the start of the session files.
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
| [Storage](07-storage.txt) | emptyDir shared between containers, hostPath read on the node, static PV/PVC binding and survival, and `WaitForFirstConsumer` dynamic provisioning. |
| [HPA and probes](08-hpa-probes.txt) | A full scale-out and scale-in under load, and the startup, readiness and liveness probes each failing in their own way. |
| [Production web app](09-webapp-mini-project.txt) | The Session 13 mini project: a 500Mi claim, data surviving Pod deletion, and autoscaling between 2 and 5. |
| [Troubleshooting](10-troubleshooting.txt) | CrashLoopBackOff, ErrImagePull, ImagePullBackOff, Pending, OOMKilled, CreateContainerConfigError, and a Service with no endpoints. |
| [Triage mini project](11-triage-mini-project.txt) | The Session 14 brief: a broken image reference and a broken Service selector, each diagnosed before being changed. |
| [Helm](12-helm.txt) | lint, template, install, upgrade, a deliberately broken upgrade, rollback, repositories, uninstall. |
| [GitOps](13-gitops.txt) | Argo CD syncing from Git, then undoing an out-of-band scale and a deleted Service. |
| [Final project](14-final-project.txt) | The Session 21 deployment: Secret, probes, read-only root filesystem, PVC persistence, Ingress, metrics and autoscaling. |
| [Final monitoring](15-final-monitoring.txt) | In-cluster Prometheus discovering the application Pods and reading their own metrics. |
| [Final troubleshooting](16-final-troubleshooting.txt) | Five faults injected into the running deployment, each diagnosed and repaired. |

See [validation scope](../../KUBERNETES-VALIDATION.md) and
[setup/reproduction instructions](../../kubernetes-fundamentals/README.md).
The runner retains the cluster for inspection; remove only that cluster with the documented
kind cleanup command when finished.
