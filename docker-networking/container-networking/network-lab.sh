#!/usr/bin/env bash
#
# Task 1 - three containers across three Docker networks, with the backend
# attached to two of them. Uses plain docker CLI commands, as the homework asks.
#
#   public_net : frontend                 (edge network, the published port)
#   app_net    : frontend <-> backend     (backend network #1)
#   data_net   : backend  <-> database    (backend network #2)
#
# The frontend and the database share no network, so the frontend cannot reach
# the database. That isolation is the point of splitting the tiers up.

set -uo pipefail
cd "$(dirname "$0")"

if [ -f .env ]; then
    # shellcheck disable=SC1091
    . ./.env
fi
: "${MYSQL_ROOT_PASSWORD:?Copy .env.example to .env and set MYSQL_ROOT_PASSWORD}"

step() { printf '\n$ %s\n' "$*"; "$@"; }

cleanup() {
    docker rm -f frontend backend database >/dev/null 2>&1 || true
    docker network rm public_net app_net data_net >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

echo "=============================================================="
echo "1. Create the three networks"
echo "=============================================================="
step docker network create public_net
step docker network create app_net
step docker network create data_net
step docker network ls --filter name=public_net --filter name=app_net --filter name=data_net \
    --format 'table {{.Name}}\t{{.Driver}}\t{{.Scope}}'

echo
echo "=============================================================="
echo "2. Start the three containers"
echo "=============================================================="
# Printed with the password masked so the transcript stays safe to commit.
echo
echo '$ docker run -d --name database --network data_net \'
echo '    -e MYSQL_ROOT_PASSWORD="$MYSQL_ROOT_PASSWORD" -e MYSQL_DATABASE=homework mysql:8.4'
docker run -d --name database --network data_net \
    -e MYSQL_ROOT_PASSWORD="$MYSQL_ROOT_PASSWORD" -e MYSQL_DATABASE=homework mysql:8.4

step docker run -d --name backend --network app_net \
    -v "$PWD/backend/index.html:/usr/share/nginx/html/index.html:ro" nginx:1.27-alpine

step docker run -d --name frontend --network public_net -p 8081:80 \
    -v "$PWD/frontend/index.html:/usr/share/nginx/html/index.html:ro" nginx:1.27-alpine

echo
echo "=============================================================="
echo "3. Attach the extra networks"
echo "=============================================================="
echo "The backend joins a second network so it can reach the database."
step docker network connect data_net backend
echo "The frontend joins app_net so it can reach the backend."
step docker network connect app_net frontend

echo
echo "Network membership per container:"
for c in frontend backend database; do
    printf '  %-9s -> %s\n' "$c" \
        "$(docker inspect "$c" --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}')"
done

echo
echo "Waiting for MySQL to finish initialising..."
for _ in $(seq 1 60); do
    if docker exec database mysqladmin ping -h 127.0.0.1 -uroot -p"$MYSQL_ROOT_PASSWORD" \
        >/dev/null 2>&1; then
        echo "MySQL is ready."
        break
    fi
    sleep 2
done

echo
echo "=============================================================="
echo "4. Connectivity checks"
echo "=============================================================="

echo
echo "4a. frontend -> backend  (shared network: app_net)  EXPECT: success"
step docker exec frontend wget -qO- --timeout=5 http://backend/

echo
echo "4b. backend -> database  (shared network: data_net)  EXPECT: success"
step docker exec backend getent hosts database
step docker exec backend nc -z -w 3 database 3306
echo "TCP 3306 on 'database' is reachable from the backend."

echo
echo "4c. frontend -> database (no shared network)  EXPECT: failure"
if docker exec frontend getent hosts database >/dev/null 2>&1; then
    echo "UNEXPECTED: the frontend resolved 'database'."
else
    echo "As expected, the frontend cannot resolve 'database': the two containers"
    echo "share no network, so Docker's embedded DNS gives the frontend no record."
fi

echo
echo "4d. the published frontend page, from the host"
# Attaching a second network to a running container briefly disturbs the
# published port mapping, so retry rather than failing on a transient error.
printf '\n$ curl -s http://localhost:8081/\n'
for attempt in $(seq 1 15); do
    if curl -sf --max-time 5 http://localhost:8081/; then
        break
    fi
    if [ "$attempt" -eq 15 ]; then
        echo "  still not reachable after 15 attempts"
    fi
    sleep 1
done

echo
echo "=============================================================="
echo "5. Which containers each network holds"
echo "=============================================================="
for n in public_net app_net data_net; do
    printf '\n$ docker network inspect %s --format ...\n' "$n"
    printf '  %-11s : %s\n' "$n" \
        "$(docker network inspect "$n" --format '{{range .Containers}}{{.Name}} {{end}}')"
done

echo
echo "=============================================================="
echo "6. Clean up"
echo "=============================================================="
echo "docker rm -f frontend backend database"
echo "docker network rm public_net app_net data_net"
