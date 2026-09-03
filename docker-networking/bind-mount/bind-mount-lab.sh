#!/usr/bin/env bash
#
# Task 3 - bind mount a local folder into an Nginx container and show that
# edits on the host appear immediately, with no restart and no rebuild.

set -uo pipefail
cd "$(dirname "$0")"

step() { printf '\n$ %s\n' "$*"; "$@"; }

cleanup() { docker rm -f bind-mount-web >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

# Always start the lab from the same known content.
sed -i '' 's|<h1>.*</h1>|<h1>Hello students</h1>|' site/index.html 2>/dev/null || true
sed -i '' 's|<p>This text changed on the host.*</p>|<p>Served by Nginx from a bind-mounted folder</p>|' site/index.html 2>/dev/null || true

echo "=============================================================="
echo "1. The folder on the local machine"
echo "=============================================================="
step ls -l site/
echo
echo "\$ grep -E '<h1>|<p>' site/index.html"
grep -E '<h1>|<p>' site/index.html | sed 's/^[[:space:]]*//'

echo
echo "=============================================================="
echo "2. Bind mount it into Nginx"
echo "=============================================================="
step docker run -d --name bind-mount-web -p 8082:80 \
    -v "$PWD/site:/usr/share/nginx/html:ro" nginx:1.27-alpine
sleep 3

echo
echo "\$ docker inspect bind-mount-web --format '{{range .Mounts}}{{.Type}} {{.Source}} -> {{.Destination}} (rw={{.RW}}){{end}}'"
docker inspect bind-mount-web --format '{{range .Mounts}}{{.Type}} {{.Source}} -> {{.Destination}} (rw={{.RW}}){{end}}'
echo
echo "The mount Type is 'bind', not 'volume'. Docker is not managing any storage"
echo "here; it is mapping a host directory straight into the container."

echo
echo "=============================================================="
echo "3. Access the website"
echo "=============================================================="
step curl -s http://localhost:8082/
STARTED_BEFORE=$(docker inspect bind-mount-web --format '{{.State.StartedAt}}')
PID_BEFORE=$(docker inspect bind-mount-web --format '{{.State.Pid}}')

echo
echo "=============================================================="
echo "4. Modify index.html on the host - the container is NOT touched"
echo "=============================================================="
echo "\$ sed -i '' 's|Hello students|Hello students - edited at $(date +%H:%M:%S) with the container still running|' site/index.html"
sed -i '' "s|<h1>.*</h1>|<h1>Hello students - edited at $(date +%H:%M:%S) with the container still running</h1>|" site/index.html
echo
echo "\$ grep '<h1>' site/index.html"
grep '<h1>' site/index.html | sed 's/^[[:space:]]*//'

# Give Docker Desktop's file-sharing layer a moment to invalidate its cache.
# See the note on VirtioFS in README.md - without this, a request fired in the
# same millisecond as the write can be served with the new Content-Length but
# the old body length.
sleep 1

echo
echo "=============================================================="
echo "5. Re-request the page - no restart, no rebuild, no docker command"
echo "=============================================================="
step curl -s http://localhost:8082/
STARTED_AFTER=$(docker inspect bind-mount-web --format '{{.State.StartedAt}}')
PID_AFTER=$(docker inspect bind-mount-web --format '{{.State.Pid}}')

echo
echo "Proof that the container never restarted:"
printf '  StartedAt before edit : %s\n' "$STARTED_BEFORE"
printf '  StartedAt after edit  : %s\n' "$STARTED_AFTER"
printf '  Main PID before/after : %s / %s\n' "$PID_BEFORE" "$PID_AFTER"
if [ "$STARTED_BEFORE" = "$STARTED_AFTER" ] && [ "$PID_BEFORE" = "$PID_AFTER" ]; then
    echo "  Identical - the same process served both responses."
else
    echo "  MISMATCH - the container restarted, which should not happen."
fi
echo
step docker ps --filter name=bind-mount-web --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

echo
echo "=============================================================="
echo "6. The mount is read-only from the container's side"
echo "=============================================================="
echo "\$ docker exec bind-mount-web sh -c 'echo test > /usr/share/nginx/html/index.html'"
docker exec bind-mount-web sh -c 'echo test > /usr/share/nginx/html/index.html' 2>&1 \
    || echo "  Refused, because the mount was made with :ro. The host stays the single"
echo "  source of truth for this content."

echo
echo "=============================================================="
echo "7. Clean up"
echo "=============================================================="
echo "docker rm -f bind-mount-web"
