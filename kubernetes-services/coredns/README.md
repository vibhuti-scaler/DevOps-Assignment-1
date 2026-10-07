# CoreDNS

- **Name:** Vibhuti Bhatnagar · **Roll no:** 24BCS10288 · **Batch:** B

Session 11, Task 4. CoreDNS is running in the lab cluster; the commands below were run against it.

## What is CoreDNS?

CoreDNS is a DNS server written as a chain of plugins. A query enters at the top of the chain and
each plugin either answers it, rewrites it, or passes it to the next one. In Kubernetes it runs as
an ordinary Deployment in `kube-system`, fronted by a Service on a fixed address, and every Pod is
configured to use that address as its nameserver.

```bash
kubectl -n kube-system get deployment coredns
kubectl -n kube-system get service kube-dns
kubectl -n kube-system get pods -l k8s-app=kube-dns -o wide
```

```text
NAME      READY   UP-TO-DATE   AVAILABLE
coredns   2/2     2            2
```

Two replicas, because DNS failing is indistinguishable from everything failing.

## Why Kubernetes uses it

It replaced kube-dns in Kubernetes 1.13. The reasons are practical rather than ideological:

- **One process.** kube-dns was three containers (`kubedns`, `dnsmasq`, `sidecar`) that had to agree
  with each other. CoreDNS is a single Go binary.
- **The `kubernetes` plugin.** It watches the API server for Services, EndpointSlices and
  Namespaces, and answers from that watch rather than from a cache that can go stale.
- **Configurable.** Stub domains, forwarding, rewriting and caching are plugin lines in a
  ConfigMap rather than special-cased options.

## How Service discovery works

```text
Pod asks for notes.notes.svc.cluster.local
        │
        ▼
/etc/resolv.conf -> nameserver 10.96.0.10   (the kube-dns Service address)
        │
        ▼
CoreDNS Pod, kubernetes plugin
        │  looks up the Service in its API watch cache
        ▼
answer: the Service's ClusterIP
        │
        ▼
kube-proxy rewrites that address to a ready Pod from the EndpointSlice
```

Two things are worth separating. CoreDNS answers *names*. `kube-proxy` chooses *which Pod*. A Pod
that is Running but not Ready is still in the Service's selector and still absent from the
EndpointSlice, so DNS is unaffected and the connection is what fails.

## How a query is resolved

1. The kubelet writes `/etc/resolv.conf` into the Pod with the cluster DNS address, a `search` list
   built from the Pod's namespace, and `ndots:5`.
2. The client library appends each search suffix in turn to any name with fewer than five dots.
3. CoreDNS receives the query. The `kubernetes` plugin claims anything under `cluster.local` and
   the two reverse zones.
4. For a cluster name it answers from its watch of the API server. For anything else the `forward`
   plugin sends it to the node's upstream resolvers.
5. The `cache` plugin stores the answer for the record's TTL, so repeated lookups never leave
   the CoreDNS Pod.

## Configuration

```bash
kubectl -n kube-system get configmap coredns -o jsonpath='{.data.Corefile}'
```

```text
.:53 {
    errors
    health {
       lameduck 5s
    }
    ready
    kubernetes cluster.local in-addr.arpa ip6.arpa {
       pods insecure
       fallthrough in-addr.arpa ip6.arpa
       ttl 30
    }
    prometheus :9153
    forward . /etc/resolv.conf {
       max_concurrent 1000
    }
    cache 30
    loop
    reload
    loadbalance
}
```

Reading it line by line is the fastest way to understand what CoreDNS is doing:

| Line | What it does |
| --- | --- |
| `errors` | Logs failures. |
| `health` / `ready` | The endpoints the liveness and readiness probes use. `lameduck` keeps answering briefly during shutdown so in-flight queries are not dropped. |
| `kubernetes cluster.local …` | Claims the cluster zones and answers them from the API watch. `ttl 30` is how long clients may cache. |
| `prometheus :9153` | Exports metrics, including `coredns_dns_requests_total` and the response-code counters. |
| `forward . /etc/resolv.conf` | Everything else goes to the node's own resolvers. |
| `cache 30` | A 30-second answer cache. |
| `loop` | Detects a forwarding loop at start-up and refuses to run rather than melting down later. |
| `reload` | Picks up ConfigMap edits without a restart. |
| `loadbalance` | Shuffles A records so clients do not all pick the first one. |

Editing the ConfigMap is the supported way to add a stub domain or change forwarding. Because of
`reload`, the change applies within a couple of minutes without touching the Deployment.

## Troubleshooting DNS

The order below goes from "is DNS even involved" to the details, which is usually the fastest route.

**1. Is it DNS at all?** Resolve the name and connect separately.

```bash
kubectl -n devops-homework exec dns-client -- nslookup -type=A notes.notes.svc.cluster.local.
kubectl -n devops-homework exec dns-client -- wget -qO- http://notes.notes
```

If the name resolves and the connection is refused, the problem is endpoints, not DNS.

**2. Are the endpoints there?**

```bash
kubectl -n notes get endpointslices -l kubernetes.io/service-name=notes
```

An empty slice means a selector mismatch or no Ready Pod. Session 14's
[service and DNS scenario](../../kubernetes-troubleshooting/README.md) is exactly this case.

**3. Is CoreDNS healthy?**

```bash
kubectl -n kube-system get pods -l k8s-app=kube-dns
kubectl -n kube-system logs -l k8s-app=kube-dns --tail=50
kubectl -n kube-system get service kube-dns
```

**4. Is the Pod configured to use it?**

```bash
kubectl -n devops-homework exec dns-client -- cat /etc/resolv.conf
```

A missing `search` list or the wrong nameserver address points at `dnsPolicy` — a Pod with
`hostNetwork: true` and the default policy uses the *node's* resolver and cannot see cluster names
at all. `dnsPolicy: ClusterFirstWithHostNet` is the fix.

**5. Is it slow rather than broken?** `ndots:5` makes every short external name cost several failed
lookups first. Either use a trailing dot, or set `dnsConfig.options` to a lower `ndots` for that
Pod.

**6. Common causes, collected**

| Symptom | Usual cause |
| --- | --- |
| `NXDOMAIN` for a Service name | Wrong namespace in the name, or the Service does not exist. |
| Resolves, connection refused | Empty EndpointSlice: selector mismatch or no Ready Pod. |
| Works in one namespace only | A short name relying on the `search` list. |
| Nothing resolves from one Pod | `hostNetwork` with the wrong `dnsPolicy`. |
| Everything is slow | `ndots:5` plus external names without a trailing dot. |
| CoreDNS crash-looping at start-up | The `loop` plugin found a forwarding loop, usually a node resolver pointing back at the cluster DNS address. |
