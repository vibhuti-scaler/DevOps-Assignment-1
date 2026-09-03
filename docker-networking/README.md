# Docker networking and volumes

- **Name:** Vibhuti Bhatnagar
- **Roll no:** 24BCS10288
- **Batch:** B

Four exercises, each in its own folder with a runnable script and a captured transcript.

| # | Task | Folder | Evidence |
| --- | --- | --- | --- |
| 1 | Three containers across three networks, backend on two | [container-networking/](container-networking/) | [verification.txt](container-networking/verification.txt) |
| 2 | Apache2 on the host network, port 80 | [host-network/](host-network/) | [verification.txt](host-network/verification.txt) |
| 3 | Bind mount into Nginx, edited live | [bind-mount/](bind-mount/) | [verification.txt](bind-mount/verification.txt) |
| 4 | Overlay networks | [overlay-network.md](overlay-network.md) | [overlay-demo-output.txt](overlay-demo-output.txt) |

Each lab is a separate project so the different network modes do not interfere with each other —
host networking in particular is much easier to reason about when nothing else is running.

## Run everything

```bash
cd container-networking && cp .env.example .env && ./network-lab.sh && cd ..
cd host-network        && ./host-network-lab.sh && cd ..
cd bind-mount          && ./bind-mount-lab.sh   && cd ..
./overlay-demo.sh
```

Every script cleans up after itself with a `trap`, including `docker swarm leave` in the overlay
demo, so the daemon ends up as it started.

## Task 1 — container networking

Three networks with distinct jobs, and the **backend attached to two** of them:

```text
public_net  : frontend
app_net     : frontend  backend      <-- backend network #1
data_net    : backend   database     <-- backend network #2
```

| Check | Result |
| --- | --- |
| frontend → backend | returned the backend page |
| backend → database | `database` resolved to `172.21.0.2`, TCP 3306 open |
| frontend → database | **no DNS record** — they share no network |

![Frontend on port 8081](screenshots/01-frontend-8081.png)

Details in [container-networking/README.md](container-networking/README.md). A Compose file
reproducing the same topology is included there as the "remaining exercises" part of the session.

## Task 2 — host network

```bash
docker run -d --name apache-host --network host httpd:2.4-alpine
```

No `-p` flag, and the `PORTS` column in `docker ps` is empty, because in host mode the container
binds port 80 on the host directly. A second container on the host network fetched the page over
`http://localhost:80`, proving the shared namespace; the same request from a bridge-mode container
got `Connection refused`.

**One honest caveat:** `curl http://localhost:80` from macOS did not connect. Docker Desktop runs
containers inside a Linux VM, so "the host" is that VM, not the Mac. On native Linux this works in
the browser immediately. Details and the workaround are in
[host-network/README.md](host-network/README.md).

## Task 3 — bind mount

A host folder with `index.html` saying **Hello students**, mounted into Nginx, then edited while
the container kept running:

| Before | After |
| --- | --- |
| ![Before](screenshots/02-bind-mount-before.png) | ![After](screenshots/03-bind-mount-after.png) |

`StartedAt` and the main PID were identical either side of the edit, so the same process served
both responses — no restart, no rebuild. Details in [bind-mount/README.md](bind-mount/README.md),
including a sub-second VirtioFS caching race I hit on macOS and how I worked around it.

## Task 4 — overlay networks

Research notes in [overlay-network.md](overlay-network.md), plus a real single-node Swarm demo
([overlay-demo.sh](overlay-demo.sh)) showing the overlay driver, `swarm` scope, VIP-based service
discovery, and the ingress routing mesh. The write-up is explicit about what one node **cannot**
demonstrate — traffic actually crossing hosts — and gives the two-host commands that would.

## Secrets

The MySQL password for Task 1 comes from an untracked `.env`. Only `.env.example` is committed, and
Compose refuses to start if the variable is unset rather than falling back to a default. The Swarm
join token in the overlay transcript is redacted.
