# Task 2 — Apache2 on the host network

- **Name:** Vibhuti Bhatnagar · **Roll no:** 24BCS10288 · **Batch:** B

```bash
docker pull httpd:2.4-alpine
docker run -d --name apache-host --network host \
  -v "$PWD/index.html:/usr/local/apache2/htdocs/index.html:ro" httpd:2.4-alpine
docker ps --filter name=apache-host
docker exec apache-host wget -qO- http://localhost:80/
docker rm -f apache-host
```

Everything is in [`host-network-lab.sh`](host-network-lab.sh); the transcript is in
[verification.txt](verification.txt).

## What host mode actually changes

With the default bridge driver a container gets its **own network namespace**: its own interfaces,
its own IP, and a `-p` flag to forward a host port into it. With `--network host` it gets none of
that — it shares the host's namespace and binds host ports directly.

Three pieces of evidence from the run:

**1. No `-p` flag, and nothing in the PORTS column.**

```text
NAMES         STATUS         PORTS
apache-host   Up 3 seconds
```

There is nothing to map, because Apache is already listening on port 80 of the host.

**2. Docker allocated no address for it.**

```json
{"host":{ ... "Gateway":"", "IPAddress":"", "MacAddress":"", "IPPrefixLen":0 ... }}
```

Every address field is empty. In bridge mode these would be filled in.

**3. It sees the host's interfaces.**

| `--network host` | `--network bridge` |
| --- | --- |
| `lo 127.0.0.1/8` | `lo 127.0.0.1/8` |
| `eth0 192.168.65.3/24` | `eth0 172.17.0.3/16` |
| `services1 192.168.65.6/32` | |
| `docker0 172.17.0.1/16` | |
| `br-4f4ea5480595 172.18.0.1/16` | |

The host-mode container can see `docker0` and the user-defined bridges — interfaces that belong to
the Docker host itself. The bridge-mode container sees only loopback and its own veth endpoint.

## Accessing it on port 80

A second container started with `--network host` fetched the page over `http://localhost:80`
successfully. The two containers were never linked to each other, so the only reason this works is
that they share one network namespace. The same command in bridge mode got
`Connection refused`, because there is nothing on port 80 inside its own namespace.

## One honest caveat about Docker Desktop on macOS

`curl http://localhost:80` **from macOS did not connect**, and that is expected on this setup.

Docker Desktop does not run Linux containers on macOS directly — it runs them inside a small Linux
VM. So "the host" in `--network host` is that VM, not the Mac. The container genuinely is on port
80 of its host, which is why both in-namespace checks succeed, but macOS sits outside that
namespace and there is no published port to bridge the gap.

On a native Linux Docker host there is no VM in between and `http://localhost:80` works in the
browser straight away.

Docker Desktop can close the gap too: **Settings → Resources → Network → "Enable host networking"**,
then Apply & restart. With that on, `./host-network-lab.sh` prints the page in section 5 instead of
this note.

## When host mode is worth using

- Removes the userland proxy and NAT hop, so it is faster for high-throughput or
  latency-sensitive services.
- Necessary for tools that need to see the host's real interfaces — packet capture, network
  monitoring agents, DHCP or mDNS services.
- Simpler for a service that must own a well-known port on the host.

The trade-offs: no network isolation from the host, port conflicts become real conflicts, and
container names no longer resolve through Docker's embedded DNS. For ordinary multi-container
applications, user-defined bridge networks like the ones in [Task 1](../container-networking/) are
the better default.

## Compose version

```bash
docker compose up -d
docker compose exec apache wget -qO- http://localhost:80/
docker compose down
```

Note that [`docker-compose.yml`](docker-compose.yml) has **no `ports:` block** — Compose rejects
publishing ports alongside `network_mode: host`, for the same reason the `-p` flag is pointless.
