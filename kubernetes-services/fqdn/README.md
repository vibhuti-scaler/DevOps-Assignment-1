# FQDN and Kubernetes Service DNS

- **Name:** Vibhuti Bhatnagar · **Roll no:** 24BCS10288 · **Batch:** B

Session 11, Task 3. The lookups quoted here are from
[05-services.txt](../../evidence/kubernetes/05-services.txt).

## What is an FQDN?

A fully qualified domain name is a name that is complete: it names every label from the host up to
the root, so a resolver has nothing left to guess. In DNS terms it ends with a dot.

```text
web-clusterip . devops-homework . svc . cluster.local .
     │                 │            │        │         └─ the root
     │                 │            │        └─ the cluster's DNS domain
     │                 │            └─ this name belongs to a Service
     │                 └─ the namespace
     └─ the Service name
```

`web-clusterip` on its own is a *relative* name. The resolver completes it using the search list in
`/etc/resolv.conf`, and the answer therefore depends on which namespace the asking Pod is in.
`web-clusterip.devops-homework.svc.cluster.local.` means the same thing everywhere.

## Kubernetes Service DNS

Every Service gets an A record. For a normal ClusterIP Service the record points at the virtual IP,
not at a Pod:

```bash
kubectl -n devops-homework exec dns-client -- nslookup -type=A web-clusterip.devops-homework.svc.cluster.local.
```

```text
Name:      web-clusterip.devops-homework.svc.cluster.local
Address 1: 10.96.x.y web-clusterip.devops-homework.svc.cluster.local
```

The address stays the same while the Pods behind it come and go. That indirection is the reason the
name is worth having at all.

For a **headless** Service (`clusterIP: None`) there is no virtual IP, so DNS returns the Pod
addresses instead — one A record per ready Pod. With a StatefulSet each Pod also gets its own name:

```text
web-0.web-headless.devops-homework.svc.cluster.local
web-1.web-headless.devops-homework.svc.cluster.local
```

That is how a database replica addresses a specific peer rather than "whichever one answers".

An **ExternalName** Service produces a CNAME to a name outside the cluster and no proxying at all.

## Naming convention

| Object | Pattern |
| --- | --- |
| Service | `<service>.<namespace>.svc.<cluster-domain>` |
| Named port (SRV) | `_<port-name>._<protocol>.<service>.<namespace>.svc.<cluster-domain>` |
| StatefulSet Pod via headless Service | `<pod>.<service>.<namespace>.svc.<cluster-domain>` |
| Pod by IP (rarely used) | `<ip-with-dashes>.<namespace>.pod.<cluster-domain>` |

`cluster.local` is the default cluster domain and is what this kind cluster uses.

## Namespace-based DNS, and why the short name usually works

A Pod's `/etc/resolv.conf` is written by the kubelet:

```bash
kubectl -n devops-homework exec dns-client -- cat /etc/resolv.conf
```

```text
search devops-homework.svc.cluster.local svc.cluster.local cluster.local
nameserver 10.96.0.10
options ndots:5
```

Two details explain most DNS confusion in Kubernetes:

- **`search`** is why `web-clusterip` resolves from inside `devops-homework` and does not resolve
  from another namespace. The resolver tries each suffix in order; the first one is this Pod's own
  namespace.
- **`ndots:5`** means any name with fewer than five dots is tried against the search list *first*,
  before being tried as an absolute name. That is why a name like `api.example.com` costs four
  failed lookups before the real one, and why appending a trailing dot is a real optimisation for
  external names.

| Calling from | Name that works |
| --- | --- |
| The same namespace | `web-clusterip` |
| Another namespace | `web-clusterip.devops-homework` |
| Anywhere, unambiguously | `web-clusterip.devops-homework.svc.cluster.local.` |

## Pod-to-Service communication, step by step

1. The client resolves the Service name. CoreDNS answers with the ClusterIP.
2. The client opens a connection to that ClusterIP.
3. `kube-proxy` rules on the node rewrite the destination to one ready Pod address from the
   Service's EndpointSlice.
4. The packet reaches the Pod on its `targetPort`.

Step 3 is the one that fails silently: if the EndpointSlice is empty — wrong selector, or no Pod
Ready — DNS still answers happily and the connection is simply refused. The symptom looks like a
DNS problem and is not one. `kubectl get endpointslices -l kubernetes.io/service-name=<service>` is
the command that tells the two apart.

## Examples from this repository

| Name | What it resolves to |
| --- | --- |
| `web-clusterip.devops-homework.svc.cluster.local.` | ClusterIP of the Session 11 Service. |
| `web-headless.devops-homework.svc.cluster.local.` | The ready Pod addresses, no virtual IP. |
| `web-0.web-headless.devops-homework.svc.cluster.local.` | One specific StatefulSet Pod. |
| `kubernetes.default.svc.cluster.local.` | The API server, reachable from every Pod. |
| `notes.notes.svc.cluster.local.` | The final project's Service, called across namespaces. |

One practical note from the transcript: BusyBox's `nslookup` can print the correct answer and still
exit non-zero, because it reports failures for the other search-list candidates it tried. Asking for
the absolute name and an explicit record type avoids the ambiguity:
`nslookup -type=A web-clusterip.devops-homework.svc.cluster.local.`
