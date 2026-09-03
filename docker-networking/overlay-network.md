# Task 4 — Docker overlay networks

- **Name:** Vibhuti Bhatnagar · **Roll no:** 24BCS10288 · **Batch:** B

## The problem overlay networks solve

A bridge network — the kind used in [Task 1](container-networking/) — only exists on **one** Docker
host. Two containers can talk over it because they are plugged into the same Linux bridge on the
same machine. Put them on different machines and that bridge is useless: the containers have
private addresses that mean nothing outside their own host.

An **overlay** network sits on top of whatever physical network already connects the hosts. Docker
gives the containers addresses from one shared subnet and tunnels their traffic between machines,
so from the container's point of view every other container is on the same flat LAN — regardless of
which host it is on.

| | bridge | overlay |
| --- | --- | --- |
| Scope | one host (`local`) | the whole cluster (`swarm`) |
| Needs Swarm mode | no | yes |
| Spans multiple hosts | no | yes |
| Service discovery | container names on that host | service names cluster-wide, via a VIP |
| Traffic between hosts | not possible | encapsulated, usually VXLAN |

## How it works across multiple hosts

1. **The hosts join a Swarm.** `docker swarm init` on the first, `docker swarm join` on the rest.
   Managers keep the cluster state in an internal Raft store and gossip it to every node.
2. **An overlay network is created**, e.g. `docker network create --driver overlay app_overlay`.
   The definition is stored cluster-wide, not on one machine. It does not appear on a node until
   something on that node actually attaches to it.
3. **Each participating host builds the plumbing.** Docker creates a hidden network namespace per
   overlay containing a Linux bridge (`br0`) and a **VXLAN** interface. Containers get a veth into
   that bridge, plus a second interface into `docker_gwbridge` for outbound traffic to the wider
   internet.
4. **A container sends a packet** to another container's overlay address. The local VXLAN
   interface wraps the original Ethernet frame inside a UDP packet addressed to the *host* that owns
   the destination, and sends it over the physical network.
5. **The receiving host decapsulates it** and delivers the original frame onto its own `br0`. The
   destination container sees an ordinary frame from a neighbour on its subnet and has no idea it
   crossed a machine boundary.

Swarm distributes the address-to-host mapping, so each node knows which peer to send a given
overlay address to without flooding.

### Service discovery

Each service gets one **virtual IP**. Resolving the service name returns that single VIP, and the
kernel load-balances connections across the healthy tasks behind it. `tasks.<service>` resolves to
the individual task addresses when a client needs them directly.

### The routing mesh

A service published with `--publish` is reachable on that port on **every** node, whether or not a
task is running there. A node that receives a request it cannot serve locally forwards it over the
ingress overlay to a node that can.

### Ports the hosts must be able to reach each other on

| Port | Purpose |
| --- | --- |
| TCP 2377 | cluster management (managers only) |
| TCP + UDP 7946 | node-to-node gossip and discovery |
| UDP 4789 | VXLAN data plane — the encapsulated container traffic |

If UDP 4789 is blocked, the Swarm forms and services start, but containers on different hosts
cannot reach one another. It is the usual cause of "the service is running but nothing can talk to
it".

Traffic is **not encrypted by default**. `docker network create --opt encrypted` turns on IPsec for
the data plane, at some throughput cost.

## Where they get used

- Docker Swarm services spread across several nodes — the main case.
- Keeping service-to-service traffic on stable names instead of host IPs that change when a
  container is rescheduled.
- Segmenting tiers across a cluster the same way Task 1 segments them on one host: a `data_net`
  overlay that only backend services join keeps the database unreachable from anything else, even
  across machines.

## What I ran

The homework asks for research, so this is theory — but I wanted to see the objects rather than
just read about them. [`overlay-demo.sh`](overlay-demo.sh) brings up a **single-node** Swarm,
creates an overlay, runs a 3-replica service on it, and then leaves the Swarm again. Output is in
[overlay-demo-output.txt](overlay-demo-output.txt).

What it showed:

**Overlay networks genuinely require Swarm mode.** Before `swarm init`:

```text
$ docker network create --driver overlay will_fail
Error response from daemon: This node is not a swarm manager. Use "docker swarm init" ...
```

**Swarm mode creates `ingress` automatically** — the routing-mesh network — alongside
`docker_gwbridge`.

**The scope really is different:**

```text
NAME          DRIVER    SCOPE
app_overlay   overlay   swarm
bridge        bridge    local
```

**Service discovery returns one VIP, not three addresses:**

```text
$ docker exec overlay-client getent hosts web
10.0.1.2          web  web

$ docker exec overlay-client getent hosts tasks.web
10.0.1.4          tasks.web  tasks.web
```

The service answered with `HTTP/1.1 200 OK` over the overlay, and the network held all three tasks
plus my attached client on `10.0.1.0/24`:

```text
overlay-client                    10.0.1.7/24
web.1.pm91pzgfqh9hic8janhur4jb5   10.0.1.3/24
web.2.p34qbsv7x9u3cjgd7kov626jq   10.0.1.4/24
web.3.jcf60xoixd0b8bc2t8bqt8bds   10.0.1.5/24
app_overlay-endpoint              10.0.1.6/24
```

**The published port is in ingress mode:**

```text
Published: 8090 -> 80 (ingress)
```

### What one node cannot show

Every task landed on `docker-desktop`, the only node. So no packet was ever actually encapsulated
and sent to another machine — the VXLAN path, the part that makes an overlay an overlay, was never
exercised. Demonstrating that honestly needs two Docker hosts, for example two cloud VMs or two
local VMs on the same network:

```bash
# on host A
docker swarm init --advertise-addr <host-A-ip>
docker network create --driver overlay --attachable app_overlay

# on host B
docker swarm join --token <worker-token> <host-A-ip>:2377

# back on host A
docker service create --name web --network app_overlay --replicas 4 nginx:alpine
docker service ps web        # the NODE column now shows both hostnames
```

With two nodes, `docker service ps` shows tasks split across hostnames, and a `tcpdump` on UDP 4789
on either host shows the encapsulated container traffic going past.

I also attached my client container with `--attachable` on the network. Without that flag, only
Swarm services can join an overlay, and a plain `docker run --network app_overlay` is rejected.
