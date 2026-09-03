#!/usr/bin/env bash
#
# Task 2 - Apache2 on the host network.
#
# With --network host the container does not get its own network namespace.
# It shares the host's, so it binds port 80 on the host directly and needs
# no -p mapping at all.

set -uo pipefail
cd "$(dirname "$0")"

step() { printf '\n$ %s\n' "$*"; "$@"; }

cleanup() { docker rm -f apache-host netcheck >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

echo "=============================================================="
echo "1. Pull the Apache2 image from Docker Hub"
echo "=============================================================="
step docker pull httpd:2.4-alpine
step docker images httpd --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}'

echo
echo "=============================================================="
echo "2. Run it on the host network - note there is no -p flag"
echo "=============================================================="
step docker run -d --name apache-host --network host \
    -v "$PWD/index.html:/usr/local/apache2/htdocs/index.html:ro" httpd:2.4-alpine
sleep 3

step docker inspect apache-host --format 'NetworkMode = {{.HostConfig.NetworkMode}}'
step docker inspect apache-host --format 'Networks    = {{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}'
echo
echo "In host mode Docker allocates no address of its own for the container:"
step docker inspect apache-host --format '{{json .NetworkSettings.Networks}}'

echo
echo "\$ docker ps --filter name=apache-host --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
docker ps --filter name=apache-host --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
echo "The PORTS column is empty. In host mode there is nothing to map, because the"
echo "container is already bound to port 80 on the host."

echo
echo "=============================================================="
echo "3. Access the site on port 80"
echo "=============================================================="
echo
echo "3a. From inside the container's (= the host's) namespace:"
step docker exec apache-host wget -qO- http://localhost:80/

echo
echo "3b. From a second, separate container also on the host network."
echo "    It has no link to apache-host other than the shared namespace,"
echo "    so reaching port 80 proves they share the host's network stack:"
step docker run --rm --name netcheck --network host alpine:3.20 \
    wget -qO- --timeout=5 http://localhost:80/

echo
echo "3c. Compare: the same image WITHOUT host networking gets its own namespace."
step docker run --rm --name netcheck --network bridge alpine:3.20 \
    sh -c 'wget -qO- --timeout=3 http://localhost:80/ || echo "nothing on localhost:80 - this container has its own network namespace"'

echo
echo "=============================================================="
echo "4. Interfaces seen from inside the container"
echo "=============================================================="
IPQ="ip -o addr show | grep 'inet ' | awk '{print \$2, \$4}'"

echo "In host mode the container sees every interface the host has,"
echo "including docker0 and the user-defined bridges:"
printf '\n$ docker run --rm --network host alpine:3.20 sh -c "ip -o addr show | grep inet"\n'
docker run --rm --network host alpine:3.20 sh -c "$IPQ"

echo
echo "In bridge mode the same command shows only loopback and one veth endpoint:"
printf '\n$ docker run --rm --network bridge alpine:3.20 sh -c "ip -o addr show | grep inet"\n'
docker run --rm --network bridge alpine:3.20 sh -c "$IPQ"

echo
echo "=============================================================="
echo "5. Reaching it from the machine you are sitting at"
echo "=============================================================="
if curl -s -m 5 -o /dev/null -w '%{http_code}' http://localhost:80/ | grep -q 200; then
    echo "curl http://localhost:80 from this machine returned HTTP 200."
    printf '\n$ curl -s http://localhost:80/\n'
    curl -s http://localhost:80/
else
    cat <<'NOTE'
curl http://localhost:80 from macOS did NOT connect, and that is expected here.

Docker Desktop does not run containers on macOS directly. It runs a small Linux
VM, and "the host" in --network host means that VM, not the Mac. The container
really is on port 80 of the host it belongs to, which is why steps 3a and 3b
succeed, but macOS is outside that namespace.

On a native Linux Docker host there is no VM in between, so http://localhost:80
in the browser works immediately.

To reach it from macOS as well, enable Docker Desktop's host networking:
  Settings -> Resources -> Network -> "Enable host networking", then Apply & restart.
Re-running this script afterwards makes this section print the page instead.
NOTE
fi

echo
echo "=============================================================="
echo "6. Clean up"
echo "=============================================================="
echo "docker rm -f apache-host"
