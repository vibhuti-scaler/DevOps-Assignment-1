# Kubernetes validation

- **Name:** Vibhuti Bhatnagar
- **Roll no:** 24BCS10288
- **Email:** vibhuti.24bcs10288@sst.scaler.com
- **Dates:** sessions 9-12 on 20 September 2026; sessions 13-21 on 7 October 2026
  (Asia/Kolkata; logs use UTC)

This report covers every section that was executed. Docker screenshots and transcripts from the
earlier assignment are retained and are not claimed as newly captured.

**Result: all sixteen live Kubernetes sections passed**, along with the CI/CD, DevSecOps, Terraform
and monitoring labs. Failures that happened on the way, and their corrections, are recorded below
rather than removed.

## Summary by session

| Session | Lab | Transcript | Result |
| --- | --- | --- | --- |
| 9 | Fundamentals | [01-fundamentals.txt](evidence/kubernetes/01-fundamentals.txt) | pass |
| 10 | Core objects, strategies, lifecycle | [02](evidence/kubernetes/02-core.txt), [03](evidence/kubernetes/03-strategies.txt), [04](evidence/kubernetes/04-lifecycle.txt) | pass |
| 11 | Services and DNS | [05-services.txt](evidence/kubernetes/05-services.txt) | pass |
| 12 | Ingress, ConfigMaps, Secrets | [06-ingress.txt](evidence/kubernetes/06-ingress.txt) | pass |
| 13 | Volumes, PV/PVC, StorageClass | [07-storage.txt](evidence/kubernetes/07-storage.txt) | pass |
| 13 | HPA and probes | [08-hpa-probes.txt](evidence/kubernetes/08-hpa-probes.txt) | pass |
| 13 | Mini project | [09-webapp-mini-project.txt](evidence/kubernetes/09-webapp-mini-project.txt) | pass |
| 14 | Troubleshooting | [10-troubleshooting.txt](evidence/kubernetes/10-troubleshooting.txt) | pass |
| 14 | Triage mini project | [11-triage-mini-project.txt](evidence/kubernetes/11-triage-mini-project.txt) | pass |
| 15 | Helm | [12-helm.txt](evidence/kubernetes/12-helm.txt) | pass |
| 16 | CI/CD with act | [evidence/cicd/](evidence/cicd/README.md) | pass, with one step that cannot run locally |
| 17 | DevSecOps | [evidence/devsecops/](evidence/devsecops/README.md) | blocked, fixed, then passed |
| 18 | Terraform S3 | [18-terraform-s3-demo.txt](evidence/terraform/18-terraform-s3-demo.txt) | pass |
| 19 | Cloud infrastructure | [19-cloud-infrastructure.txt](evidence/terraform/19-cloud-infrastructure.txt) | pass |
| 20 | Monitoring stack | [20-monitoring-stack.txt](evidence/monitoring/20-monitoring-stack.txt) | pass |
| 20 | GitOps with Argo CD | [13-gitops.txt](evidence/kubernetes/13-gitops.txt) | pass |
| 21 | Final project | [14-final-project.txt](evidence/kubernetes/14-final-project.txt) | pass |
| 21 | In-cluster monitoring | [15-final-monitoring.txt](evidence/kubernetes/15-final-monitoring.txt) | pass |
| 21 | Troubleshooting challenge | [16-final-troubleshooting.txt](evidence/kubernetes/16-final-troubleshooting.txt) | pass |
| 21 | Cloud infrastructure | [21-final-project-infrastructure.txt](evidence/terraform/21-final-project-infrastructure.txt) | pass |

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

The [Python validator](scripts/validate-kubernetes.py) checks 113 Kubernetes objects across every
manifest directory in the repository, not only the session folders. It checks label syntax, namespaces, workload selectors, Service target
ports, Ingress backends, ConfigMap/Secret references and StatefulSet discovery. It executes
the actual Python API source stored in the ConfigMap and checks its three success routes,
three 404 routes, configuration values, token presence/absence and absence of token disclosure.
Relative Markdown file links are checked across the repository.

[Strict server validation](evidence/kubernetes/server-validation.txt) submits each of 92 manifest
files individually with `--dry-run=server --validate=strict`, then lints both Helm charts and
submits their rendered output the same way. The kind tool configuration is excluded because it is
not a Kubernetes API object, and the injected-fault files are excluded because they are
strategic-merge patches rather than complete objects — they are checked separately by the Python
validator. The two versions of a Deployment are alternatives, so the complete directory is never
recursively applied as one lab.

Two Services exist specifically to select nothing, so that an empty EndpointSlice can be
demonstrated. The validator inverts the check for those rather than skipping it: a typo that made
one of them accidentally work would fail validation.

One frontend Pod template carried a label value containing spaces, which Kubernetes does not
allow. It was corrected to `frontend-v1` and the validator now catches that class of error.

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

### Sessions 13-21

| Section | Observed result |
| --- | --- |
| Storage | emptyDir shared between two containers, a hostPath file read on the node after the Pod was deleted, a hand-written PV bound to a selector-matched claim with data surviving Pod deletion, and `WaitForFirstConsumer` provisioning a volume on first use. |
| HPA and probes | A full `0% → 594% → 0%` cycle scaling 1 → 5 → 1 with the stabilisation window visible; startup probe suppressing liveness during a 20s boot with zero restarts; readiness failure leaving a Pod Running, unready and out of the EndpointSlice; liveness failure incrementing the restart count. |
| Session 13 mini project | A 500Mi claim bound on first consumption, a file surviving Pod deletion, the Service answering over its ClusterIP name, and the HPA moving 2 → 5 → 2. |
| Troubleshooting | CrashLoopBackOff with the cause only in `logs --previous`, ErrImagePull then ImagePullBackOff, Pending with `Insufficient cpu`, OOMKilled with exit 137, CreateContainerConfigError from a missing ConfigMap, and a Service whose DNS resolves while every connection is refused. |
| Triage mini project | The brief's broken image reference and broken selector, each diagnosed with `describe` and `--show-labels` before any YAML was changed, then repaired and verified end to end. |
| Helm | lint, template, install at revision 1, upgrade to production values at revision 2, a deliberately broken upgrade at revision 3 leaving a Pod in ImagePullBackOff while the old one kept serving, and a rollback recorded as revision 4. |
| GitOps | Argo CD syncing from Git to `Synced`/`Healthy`, then reverting an out-of-band scale from 5 back to 1 and recreating a Service that was deleted by hand. |
| Final project | Secret-gated writes, read-only root filesystem refusing a write to `/srv` while `/data` accepted one, a note surviving Pod deletion, Ingress routing, exported Prometheus metrics, and the HPA moving 2 → 6 → 2. |
| Final monitoring | In-cluster Prometheus discovering both application Pods by annotation and reading their own counters; four alert rules loaded and inactive. |
| Final troubleshooting | Five injected faults, each diagnosed and repaired: a non-existent image tag that did not cause an outage, a selector mismatch, a missing Secret key, a readiness probe on the wrong path that restarted nothing, and a memory limit below the working set. |

### Failures corrected during these runs

| What failed | Why | Correction |
| --- | --- | --- |
| `kubectl top` on a Pod seconds old | The Pod was newer than the last metrics scrape. | The runner retries rather than failing. |
| `logs --previous` on a container in backoff | The previous log is not always retrievable immediately. | Both the current and previous logs are requested, and the check looks for the error text. |
| The first CrashLoopBackOff manifest exited 0 | `cat` failing does not abort a shell without `set -e`, so the container "completed" and was restarted. | The command now exits 1 explicitly, which is what the exercise is about. |
| `exec` into a Pod returned exit 137 | A rollout reports finished while replaced Pods are still Ready and terminating. | Pod selection now excludes anything carrying a deletion timestamp. |
| An authenticated API write returned 401 | Replacing a Secret does not restart the Pods that read it. | The Deployment is restarted explicitly after the Secret is created. |
| The application returned 500 on `/` while every probe passed | `Flask(__name__)` resolves templates inside the package; the Dockerfile copied them beside it. | Templates moved into the package. |
| The load generator could not create a single Pod | The namespace enforces the `restricted` Pod Security Standard and the throwaway Pod had no security context. | The load generator was made compliant. Admission refusing it is the control working. |

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
  responses report only whether the demonstration token is present. The final project's API token
  is generated at run time and is redacted from its transcript.
- `ReadWriteOnce` with two replicas works in the final project only because this cluster has one
  node. On a multi-node cluster the second replica would not schedule; the README says so.
- The NetworkPolicies are applied and valid. Whether this CNI enforces every clause is a property
  of the cluster, not of the manifests, and enforcement is not claimed as tested.
- The Terraform sessions run against a local AWS-compatible emulator, not an AWS account. Two
  resources are planned but not applied because the community edition cannot serve them; both are
  behind a variable that defaults to the value a real account needs.
- The GitHub Actions workflows are executed by `act` in a container that mirrors a GitHub-hosted
  runner. `actions/upload-artifact` cannot complete there and the CD jobs are not executed, because
  running them would require a real registry credential and a real kubeconfig on this machine.
- The container panels in the Grafana dashboard identify containers by cgroup id, because cAdvisor
  cannot resolve container names on Docker Desktop.
