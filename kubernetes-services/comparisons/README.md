# Kubernetes object comparison

- **Name:** Vibhuti Bhatnagar · **Roll no:** 24BCS10288 · **Batch:** B

Session 11, Task 2. Every claim here is visible in the
[Session 10](../../kubernetes-core-objects/README.md) and
[Session 11](../README.md) transcripts.

## Deployment vs ReplicaSet

| | Deployment | ReplicaSet |
| --- | --- | --- |
| Purpose | Declares the desired version of an application and manages the move between versions. | Keeps a fixed number of identical Pods running. |
| Pod management | Indirect. It creates and retires ReplicaSets; they create the Pods. | Direct. It owns the Pods through `ownerReferences`. |
| Scaling | `kubectl scale deployment/x` changes the current ReplicaSet's replica count. | `kubectl scale replicaset/x` changes it directly. |
| Rolling updates | Yes. Changing the Pod template creates a new ReplicaSet and shifts replicas across. | No. Changing the template does nothing to Pods that already exist. |
| Rollback | `kubectl rollout undo` scales the previous ReplicaSet back up. | Nothing to roll back to. |

The relationship is the whole point: a Deployment is a controller *of* ReplicaSets, and the
ReplicaSet is the controller *of* Pods. One Deployment usually has several ReplicaSets at once —
the current one at full size and older ones scaled to zero, which is what makes
`kubectl rollout undo` instant rather than a redeployment.

```text
Deployment  ──creates──▶  ReplicaSet (v2, 3 replicas)  ──creates──▶  Pod Pod Pod
            └─keeps────▶  ReplicaSet (v1, 0 replicas)   (kept for rollback)
```

In the [Session 10 transcript](../../evidence/kubernetes/02-core.txt) the v1 → v2 rollout produces
a second ReplicaSet with new Pod names, and `kubectl rollout undo` brings back the v1 response
without rebuilding anything.

**When you would use a bare ReplicaSet:** essentially never, by hand. It exists so a Deployment has
something to delegate to.

## Deployment vs DaemonSet vs StatefulSet

| | Deployment | DaemonSet | StatefulSet |
| --- | --- | --- | --- |
| Use case | Stateless, interchangeable replicas: APIs, web front ends, workers. | One Pod per node: log shippers, CNI agents, node exporters. | Workloads where each replica has an identity: databases, queues, anything with a quorum. |
| Pod creation | A ReplicaSet creates N interchangeable Pods with random name suffixes. | The controller creates one Pod per matching node and follows nodes as they join or leave. | Pods are created in order, `app-0`, `app-1`, `app-2`, and the next one waits for the previous to be Ready. |
| Scaling | `replicas: N`, any order, any node. | Not scaled by a number. The node count is the replica count. | `replicas: N`, created in order and removed in reverse order. |
| Networking | Any ClusterIP Service. Pods are addressed as a group. | Usually scraped or reached on the node itself. | A headless Service gives every Pod a stable DNS name, `app-0.svc.ns.svc.cluster.local`. |
| Storage | Usually none, or one shared claim. | Usually a `hostPath` into the node it runs on. | `volumeClaimTemplates` gives each Pod its own PersistentVolumeClaim, kept across rescheduling. |
| Example here | [deployment.yaml](../deployment.yaml) | [daemonset.yaml](../../kubernetes-core-objects/daemonset.yaml) | [headless.yaml](../headless.yaml) |

The deciding question is whether replica number 2 is interchangeable with replica number 1. If it
is, use a Deployment. If "which one" matters — because it holds data, or because peers address each
other by name — use a StatefulSet. If the answer is "one per machine", use a DaemonSet.

## ReplicaSet vs Service

These are often confused because both involve "a group of Pods", but they solve opposite problems.

| | ReplicaSet | Service |
| --- | --- | --- |
| Responsibility | *How many* Pods exist, and recreating them when they die. | *How to reach* whichever Pods currently exist. |
| What it watches | Pods matching its selector; it creates or deletes to reach `replicas`. | Pods matching its selector; it records their addresses in an EndpointSlice. |
| What it owns | The Pods. Deleting the ReplicaSet deletes them. | Nothing. Deleting the Service leaves every Pod running. |
| Readiness | Ignores it. A failing Pod still counts towards `replicas`. | Respects it. An unready Pod is removed from the endpoints. |

**Why a Service is required.** Pod IP addresses are not stable. A rescheduled Pod comes back with a
new address, and a scaled-out ReplicaSet adds addresses nobody was told about. A ReplicaSet does
nothing to help a client find them. The Service provides the two things a client actually needs: a
name that does not change (`web.devops-homework.svc.cluster.local`) and a virtual IP that is
load-balanced across whichever Pods are ready right now.

**How traffic actually reaches a Pod:**

```text
client Pod
   │  resolves web.devops-homework.svc.cluster.local via CoreDNS
   ▼
ClusterIP (a virtual address, not owned by any Pod)
   │  kube-proxy rewrites the destination using the EndpointSlice
   ▼
one ready Pod's IP:targetPort
```

The EndpointSlice is the join between the two objects: the ReplicaSet decides which Pods exist, the
kubelet decides which are Ready, and the Service's endpoint controller writes the ready ones into
the slice. The [Session 11 transcript](../../evidence/kubernetes/05-services.txt) shows what happens
when that join breaks — a Service whose selector matches nothing has an empty EndpointSlice, DNS
still resolves, and every connection is refused even though the Pods are perfectly healthy.
