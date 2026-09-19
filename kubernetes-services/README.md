# Session 11: Kubernetes Networking & Services

- **Name:** Vibhuti Bhatnagar
- **Roll no:** 24BCS10288
- **Email:** vibhuti.24bcs10288@sst.scaler.com
- **Batch:** B

Use the [disposable local lab](../kubernetes-fundamentals/README.md#local-lab-setup), then run the
commands from this folder. A Service gives clients a stable discovery name while its selected
Pods can change. EndpointSlices describe destinations; readiness affects eligible endpoints.

## Service patterns

| Pattern | Manifest | Behavior |
| --- | --- | --- |
| ClusterIP | [clusterip.yaml](clusterip.yaml) | Cluster-internal virtual IP and DNS name. |
| NodePort | [nodeport.yaml](nodeport.yaml) | Service exposed on node port `30081`, subject to node reachability/firewall settings. |
| LoadBalancer | [optional/loadbalancer.yaml](optional/loadbalancer.yaml) | Requires an implementation that supplies a load balancer; a cloud controller can provision external infrastructure. |
| ExternalName | [externalname.yaml](externalname.yaml) | CNAME alias to `kubernetes.io`; no Pod selector or traffic proxy. |
| Headless | [headless.yaml](headless.yaml) | `clusterIP: None`; DNS discovers Pod addresses and a StatefulSet demonstrates stable names. |

Headless is a ClusterIP configuration, not a fifth `spec.type` value. `port` is the Service's
listening port, `targetPort` is the application port (here named `http`), `nodePort` is the
node-facing port, and `containerPort` documents the container's port; it does not start a listener.

## ClusterIP and DNS

```bash
kubectl --context=kind-vibhuti-devops -n devops-homework apply -f deployment.yaml -f clusterip.yaml -f client.yaml
kubectl --context=kind-vibhuti-devops -n devops-homework rollout status deployment/service-web --timeout=120s
kubectl --context=kind-vibhuti-devops -n devops-homework wait --for=condition=Ready pod/dns-client --timeout=120s
kubectl --context=kind-vibhuti-devops -n devops-homework get services,pods -o wide
kubectl --context=kind-vibhuti-devops -n devops-homework exec dns-client -- nslookup -type=A web-clusterip.devops-homework.svc.cluster.local.
kubectl --context=kind-vibhuti-devops -n devops-homework exec dns-client -- wget -qO- http://web-clusterip
kubectl --context=kind-vibhuti-devops -n devops-homework get endpointslices -l kubernetes.io/service-name=web-clusterip -o wide
```

The trailing dot makes each DNS name absolute. BusyBox can print the correct answer to a
short name and still exit nonzero for other search-suffix candidates; specifying the record
type and full name avoids that ambiguity. The HTTP check uses the short Service name.

Expected behavior: DNS resolves the Service and HTTP returns `Hello from v1`. The full name is
`service.namespace.svc.cluster-domain`; `cluster.local` is the usual domain for this kind
setup. In the same namespace, the short Service name is sufficient. From another namespace use
`web-clusterip.devops-homework` or the full name. Inspect the actual resolver search list with:

```bash
kubectl --context=kind-vibhuti-devops -n devops-homework exec dns-client -- cat /etc/resolv.conf
```

## NodePort and LoadBalancer

```bash
kubectl --context=kind-vibhuti-devops -n devops-homework apply -f nodeport.yaml
kubectl --context=kind-vibhuti-devops -n devops-homework get service web-nodeport
curl --fail http://127.0.0.1:30081/
```

The kind configuration maps node port `30081` to `127.0.0.1:30081` on the host.
This lets macOS reach the real NodePort through Docker's port mapping.

The optional [LoadBalancer manifest](optional/loadbalancer.yaml) demonstrates the Service type.
A basic kind cluster has no external load balancer implementation, so its external IP stays
`<pending>`. The runner records that state and removes the optional Service. External
LoadBalancer traffic is not claimed as tested.

## ExternalName and headless Service

```bash
kubectl --context=kind-vibhuti-devops -n devops-homework apply -f externalname.yaml -f headless.yaml
kubectl --context=kind-vibhuti-devops -n devops-homework rollout status statefulset/stateful-web --timeout=120s
kubectl --context=kind-vibhuti-devops -n devops-homework exec dns-client -- nslookup -type=CNAME external-docs.devops-homework.svc.cluster.local.
kubectl --context=kind-vibhuti-devops -n devops-homework exec dns-client -- nslookup -type=A web-headless.devops-homework.svc.cluster.local.
kubectl --context=kind-vibhuti-devops -n devops-homework exec dns-client -- nslookup -type=A stateful-web-0.web-headless.devops-homework.svc.cluster.local.
kubectl --context=kind-vibhuti-devops -n devops-homework get pods -l app=stateful-web -o wide
```

The ExternalName query should show the alias target; HTTPS using the alias can fail hostname
validation because the upstream certificate is for the original domain. Headless results
identify ready Pod IPs instead of one virtual ClusterIP. This StatefulSet uses Nginx and no
persistent volume; it demonstrates naming, not persistent-data recovery.

## Troubleshooting an empty Service

Temporarily change only this lab Service's selector and inspect the endpoints:

```bash
kubectl --context=kind-vibhuti-devops -n devops-homework patch service web-clusterip --type=merge -p '{"spec":{"selector":{"app":"deliberately-missing"}}}'
kubectl --context=kind-vibhuti-devops -n devops-homework get endpointslices -l kubernetes.io/service-name=web-clusterip -o yaml
kubectl --context=kind-vibhuti-devops -n devops-homework get pods --show-labels
kubectl --context=kind-vibhuti-devops -n devops-homework apply -f clusterip.yaml
kubectl --context=kind-vibhuti-devops -n devops-homework exec dns-client -- wget -qO- http://web-clusterip
```

Check labels, readiness, Service ports, EndpointSlices, DNS, then relevant NetworkPolicies.
An empty ready-endpoint list does not by itself prove a DNS failure.

## Execution evidence and cleanup

[Raw logs](../evidence/kubernetes/README.md) record DNS answers, ClusterIP and NodePort
HTTP responses, headless discovery, and broken-selector recovery. See
[validation results](../KUBERNETES-VALIDATION.md). The shared client stays available for
the other sessions. Delete the dedicated kind cluster after finishing all labs.

References: [instructor session 11](https://github.com/Nency-Ravaliya/devops-heros/tree/1a24fe08c4956db0f8f22ffd6655581f7185699e/session-11-kubernetes-services),
[Services](https://kubernetes.io/docs/concepts/services-networking/service/),
[DNS for Services and Pods](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/).
