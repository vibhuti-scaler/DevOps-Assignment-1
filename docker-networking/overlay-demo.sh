#!/usr/bin/env bash
#
# Task 4 - a working overlay network on a single-node Swarm.
#
# The homework only asks for research, but a one-node Swarm shows the real
# objects: the overlay driver, swarm scope, the ingress network, VIP-based
# service discovery, and the routing mesh. What it cannot show is traffic
# actually crossing two machines - that needs a second Docker host.
#
# This script leaves the Swarm at the end, so the daemon ends up as it started.

set -uo pipefail

step() { printf '\n$ %s\n' "$*"; "$@"; }

cleanup() {
    docker service rm web >/dev/null 2>&1 || true
    docker rm -f overlay-client >/dev/null 2>&1 || true
    sleep 2
    docker network rm app_overlay >/dev/null 2>&1 || true
    docker swarm leave --force >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "=============================================================="
echo "0. Before: overlay networks need Swarm mode"
echo "=============================================================="
step docker info --format 'Swarm state: {{.Swarm.LocalNodeState}}'
echo
echo "Creating an overlay network outside Swarm mode is refused:"
printf '\n$ docker network create --driver overlay will_fail\n'
docker network create --driver overlay will_fail 2>&1 | head -3

echo
echo "=============================================================="
echo "1. Initialise a Swarm"
echo "=============================================================="
step docker swarm init
step docker node ls

echo
echo "Swarm mode creates two networks automatically:"
step docker network ls --filter driver=overlay --format 'table {{.Name}}\t{{.Driver}}\t{{.Scope}}'
echo "  ingress        - the routing mesh, used for published service ports"
echo "  docker_gwbridge - how overlay containers reach the outside world"

echo
echo "=============================================================="
echo "2. Create an overlay network"
echo "=============================================================="
step docker network create --driver overlay --attachable app_overlay
echo
echo "Compare the scope column with a normal bridge network:"
step docker network ls --format 'table {{.Name}}\t{{.Driver}}\t{{.Scope}}' --filter name=app_overlay --filter name=bridge
echo
echo "'swarm' scope means the network definition is shared across every node in"
echo "the cluster, not just this one. A bridge network is 'local' to one host."

echo
echo "=============================================================="
echo "3. Run a replicated service on it"
echo "=============================================================="
step docker service create --name web --network app_overlay --replicas 3 \
    --publish published=8090,target=80 nginx:1.27-alpine
sleep 6
step docker service ls --format 'table {{.Name}}\t{{.Mode}}\t{{.Replicas}}\t{{.Ports}}'
step docker service ps web --format 'table {{.Name}}\t{{.Node}}\t{{.CurrentState}}'
echo
echo "All three tasks are on this one node. On a real cluster the Node column"
echo "would show different hostnames, and the overlay would carry traffic"
echo "between them."

echo
echo "=============================================================="
echo "4. Service discovery over the overlay"
echo "=============================================================="
step docker run -d --name overlay-client --network app_overlay alpine:3.20 sleep 300
sleep 3
echo
echo "The service name resolves to a single virtual IP, not to three addresses:"
step docker exec overlay-client getent hosts web
echo
echo "Docker load-balances that VIP across the three tasks. The individual task"
echo "addresses are visible under the special tasks.<service> name:"
step docker exec overlay-client getent hosts tasks.web
echo
echo "And the service answers over the overlay:"
step docker exec overlay-client wget -qS -O /dev/null http://web/ 2>&1

echo
echo "=============================================================="
echo "5. What the overlay looks like from the inside"
echo "=============================================================="
step docker network inspect app_overlay --format 'Driver: {{.Driver}}  Scope: {{.Scope}}  Attachable: {{.Attachable}}'
step docker network inspect app_overlay --format 'Subnet: {{range .IPAM.Config}}{{.Subnet}}{{end}}'
echo
echo "Members:"
docker network inspect app_overlay --format '{{range .Containers}}  {{.Name}}  {{.IPv4Address}}{{end}}'
echo
echo "The routing mesh published port:"
step docker service inspect web --format 'Published: {{range .Endpoint.Ports}}{{.PublishedPort}} -> {{.TargetPort}} ({{.PublishMode}}){{end}}'
echo
echo "PublishMode 'ingress' means a request to port 8090 on ANY node in the"
echo "cluster is forwarded to a healthy task, even if that task runs elsewhere."

echo
echo "=============================================================="
echo "6. Clean up - leaving the Swarm"
echo "=============================================================="
echo "docker service rm web && docker network rm app_overlay && docker swarm leave --force"
