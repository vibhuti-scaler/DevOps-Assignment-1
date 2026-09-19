# Kubernetes Fundamentals

- **Name:** Vibhuti Bhatnagar
- **Roll no:** 24BCS10288
- **Email:** vibhuti.24bcs10288@sst.scaler.com
- **Batch:** B

Kubernetes reconciles declared desired state with running workloads. A Deployment requesting
three replicas lets controllers replace lost Pods without manually starting new containers.

## Components

| Component | Responsibility |
| --- | --- |
| API server | Validates authenticated requests for API objects. |
| etcd | Stores cluster configuration and state. |
| Scheduler | Chooses a suitable node for an unscheduled Pod. |
| Controller manager | Runs reconciliation loops such as Deployment and ReplicaSet controllers. |
| kubelet | Ensures containers assigned to its node run through the container runtime. |
| Container runtime | Pulls images and starts/stops containers; this lab uses containerd. |
| CNI networking | Provides Pod connectivity; this kind cluster uses kindnet. |
| kube-proxy | Implements Service routing in this cluster. |
| CoreDNS | Resolves cluster Service names. |

```text
kubectl --> API server --> etcd
                 |
           controllers + scheduler
                 |
              Pod on node
                 |
           kubelet --> containerd
```

An **image** packages an application; a **container** runs it. A **Pod** is the scheduling unit,
containing cooperating containers that share networking and declared volumes. A **node** runs
Pods, and a **cluster** combines control-plane and worker components. A **namespace** groups
objects but does not alone isolate network traffic. This single-node lab runs control-plane
components and application Pods on the same node.

## Local lab setup

Prerequisites: Docker running locally, `kind`, `kubectl`, Python 3, curl and OpenSSL.
Follow the official [kind installation guide](https://kind.sigs.k8s.io/docs/user/quick-start/).
The recorded run used kind v0.33.0 and Kubernetes v1.35.0.

Run from the repository root:

```bash
mkdir -p .lab
kind create cluster --name vibhuti-devops --image kindest/node:v1.35.0 \
  --config kubernetes-fundamentals/kind-config.yaml \
  --kubeconfig .lab/kubeconfig --wait 180s
export KUBECONFIG="$PWD/.lab/kubeconfig"
kubectl --context=kind-vibhuti-devops cluster-info
kubectl --context=kind-vibhuti-devops get nodes -o wide
kubectl --context=kind-vibhuti-devops get pods -n kube-system
kubectl --context=kind-vibhuti-devops apply -f kubernetes-fundamentals/namespace.yaml
```

The isolated kubeconfig is ignored by Git. The context and namespace in every session are
explicit. The [kind configuration](kind-config.yaml) maps the session 11 NodePort to
`127.0.0.1:30081`; this port must be free when creating the cluster.

Keep `KUBECONFIG` set in every terminal used for manual commands. Set it before changing
directories, so the absolute path continues to work. The automated runner supplies the path itself.

## Run and capture the exercises

```bash
bash scripts/run-kubernetes-labs.sh
```

The runner waits for the node, CoreDNS, the namespace's default ServiceAccount and the client
Pod, then executes the workload, lifecycle, networking and configuration sessions. It checks
HTTP response content and retries reads while endpoints settle. A failed check stops the run
and remains visible in the transcript. No interactive screenshot picker is required.

Each section writes a real transcript under [evidence/kubernetes](../evidence/kubernetes/README.md).
Re-running a section replaces that section's log. To resume a failed session:

```bash
bash scripts/run-kubernetes-labs.sh 05-services 06-ingress
```

Available sections are `01-fundamentals`, `02-core`, `03-strategies`, `04-lifecycle`,
`05-services`, and `06-ingress`. Run fundamentals first on a new cluster to create the
namespace and client Pod. The runner leaves its cluster available for inspection.

## Reading manifests

`apiVersion` and `kind` identify the API resource. `metadata` gives its name, namespace and
labels. `spec` is desired state, while `status` is reported by the cluster. Controllers and
Services match label selectors, so a mismatch can leave a Service without ready destinations.
Label values cannot contain spaces. The `kind-config.yaml` file is a kind tool configuration,
not an API object; do not pass it to `kubectl apply`.

Continue with [core objects](../kubernetes-core-objects/README.md),
[Services](../kubernetes-services/README.md), and
[Ingress, ConfigMaps and Secrets](../kubernetes-ingress-configmaps-secrets/README.md).

## Evidence and cleanup

[Validation results](../KUBERNETES-VALIDATION.md) and [actual logs](../evidence/kubernetes/README.md)
identify the environment and executed checks. After finishing all sessions:

```bash
kind delete cluster --name vibhuti-devops --kubeconfig .lab/kubeconfig
unset KUBECONFIG
```

Only the dedicated assignment cluster is removed. Existing Docker applications are separate.

References: [Kubernetes components](https://kubernetes.io/docs/concepts/overview/components/),
[kind setup](https://kind.sigs.k8s.io/docs/user/quick-start/),
[reference commits and adaptations](../REFERENCES.md).
