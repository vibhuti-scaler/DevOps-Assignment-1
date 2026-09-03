# Task 3 — bind mount into Nginx

- **Name:** Vibhuti Bhatnagar · **Roll no:** 24BCS10288 · **Batch:** B

A folder on the local machine, [`site/`](site/), containing an `index.html` that says
**Hello students**, mounted into an Nginx container.

```bash
docker run -d --name bind-mount-web -p 8082:80 \
  -v "$PWD/site:/usr/share/nginx/html:ro" nginx:1.27-alpine
curl http://localhost:8082/
```

Everything is in [`bind-mount-lab.sh`](bind-mount-lab.sh); the transcript is in
[verification.txt](verification.txt).

## It is a bind mount, not a volume

```text
$ docker inspect bind-mount-web --format '{{range .Mounts}}{{.Type}} {{.Source}} -> {{.Destination}} (rw={{.RW}}){{end}}'
bind  .../docker-networking/bind-mount/site -> /usr/share/nginx/html  (rw=false)
```

The `Type` is `bind`. Docker is not managing any storage — it is mapping a directory that already
exists on the host straight into the container. A named volume would instead live under Docker's
own storage area and show `Type: volume`.

## Before the edit

![Hello students](../screenshots/02-bind-mount-before.png)

## After editing the file on the host

The heading and one paragraph were changed with `sed` on the host. **No `docker` command was run** —
no restart, no rebuild, no `docker cp`:

![Edited page](../screenshots/03-bind-mount-after.png)

## Proof the container never restarted

Recorded either side of the edit:

```text
StartedAt before edit : 2026-09-03T13:10:13.55597788Z
StartedAt after edit  : 2026-09-03T13:10:13.55597788Z
Main PID before/after : 99202 / 99202
```

Identical start time and identical PID, so the same Nginx process served both responses. That is
the whole point of a bind mount: the container reads the file from the host on every request, so
whatever is on disk is what gets served.

## The mount is read-only

It was mounted with `:ro`, so the container cannot write back:

```text
$ docker exec bind-mount-web sh -c 'echo test > /usr/share/nginx/html/index.html'
sh: can't create /usr/share/nginx/html/index.html: Read-only file system
```

Worth doing for static content — the host stays the single source of truth, and a compromised
container cannot rewrite the pages it serves.

## One thing I hit: a sub-second race on macOS

The first time I ran this, the page came back **truncated** — the response stopped mid-tag. It
reproduces reliably if the request is fired in the same instant as the write:

```text
host file size before edit : 749
host file size after edit  : 795

after +0s: response body = 749 bytes, Content-Length: 795   <-- mismatch
after +1s: response body = 795 bytes, Content-Length: 795
after +2s: response body = 795 bytes, Content-Length: 795
```

Nginx had already `stat`ed the new size, but Docker Desktop's VirtioFS file sharing had not yet
invalidated the cached page contents, so it sent the new length with the old body. It settles
within about a second and does not happen on a native Linux host, where the bind mount is a plain
kernel mount with no sharing layer in between.

It never shows up when a human edits a file and switches to the browser, because that takes far
longer than a second. It matters for a script, so [`bind-mount-lab.sh`](bind-mount-lab.sh) waits
one second after writing before re-requesting the page.

## Compose version

```bash
docker compose up -d
curl http://localhost:8082/
docker compose down
```

[`docker-compose.yml`](docker-compose.yml) uses `./site:/usr/share/nginx/html:ro`. A relative
source path is resolved against the Compose file's own directory, so the mount works from any
clone of this repository — unlike the `docker run` version, which needs an absolute `$PWD`.
