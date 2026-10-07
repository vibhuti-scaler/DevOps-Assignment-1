#!/usr/bin/env bash
# Brings up the Session 20 monitoring stack, proves each piece works, makes an
# alert fire and then resolve, and records everything in evidence/monitoring/.
# The stack is left running so it can be inspected; the final line says how to
# stop it.
set -uo pipefail

repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
compose=("docker" "compose" "-f" "$repo_dir/monitoring-observability-gitops/monitoring/docker-compose.yml")
out="$repo_dir/evidence/monitoring"
mkdir -p "$out"
transcript="$out/20-monitoring-stack.txt"
: > "$transcript"

failures=0
log() { printf '%s\n' "$*" | tee -a "$transcript"; }
run() { log ""; log "\$ $*"; "$@" 2>&1 | tee -a "$transcript"; return "${PIPESTATUS[0]}"; }
check() {
  if [ "$1" -eq 0 ]; then log ""; log "PASS: $2"
  else log ""; log "FAIL: $2"; failures=$((failures + 1)); fi
}

# Poll a shell expression until it prints "true", so nothing in the transcript
# is a timing accident. The last evaluated output is recorded either way.
await() {
  local label="$1" attempts="$2" expression="$3" body=""
  for _ in $(seq 1 "$attempts"); do
    body="$(eval "$expression" 2>&1)"
    if [ "$body" = "true" ]; then
      log ""; log "PASS: $label"
      return 0
    fi
    sleep 3
  done
  log ""; log "FAIL: $label (last result: $body)"
  failures=$((failures + 1))
  return 1
}

prom()  { curl -fsS --max-time 10 "http://127.0.0.1:9090$1"; }
graf()  { curl -fsS --max-time 10 "http://127.0.0.1:3000$1"; }
alertm(){ curl -fsS --max-time 10 "http://127.0.0.1:9093$1"; }
promql(){ curl -fsS --max-time 10 --get http://127.0.0.1:9090/api/v1/query --data-urlencode "query=$1"; }
show()  { log ""; log "\$ $1"; shift; "$@" 2>&1 | tee -a "$transcript" >/dev/null; "$@" 2>/dev/null >> /dev/null; }

emit() { log ""; log "\$ $1"; shift; local body; body="$("$@" 2>&1)"; printf '%s\n' "$body" | tee -a "$transcript"; }

log "Vibhuti Bhatnagar | 24BCS10288 | vibhuti.24bcs10288@sst.scaler.com"
log "$(date -u +%Y-%m-%dT%H:%M:%SZ) | 20-monitoring-stack"

run "${compose[@]}" up -d --build --wait --quiet-pull
check $? "the monitoring stack started"
run "${compose[@]}" ps

# ---------------------------------------------------------------- Prometheus
await "Prometheus reports itself ready" 40 \
  'prom /-/ready | grep -q "Ready" && echo true'
await "Prometheus loaded all four alert rule groups" 30 \
  'test "$(prom /api/v1/rules | jq "[.data.groups[].rules[]] | length")" -ge 6 && echo true'
await "every scrape target is up" 60 \
  'test "$(prom "/api/v1/targets?state=active" | jq "[.data.activeTargets[] | select(.health != \"up\")] | length")" -eq 0 && echo true'

log ""
log "\$ curl http://127.0.0.1:9090/api/v1/targets"
prom "/api/v1/targets?state=active" \
  | jq -r '.data.activeTargets[] | "\(.labels.job)\t\(.scrapeUrl)\t\(.health)"' | tee -a "$transcript"

log ""
log "--- Metrics, read back through PromQL -------------------------------------"
log ""
log '$ promql 100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[2m])) * 100)'
promql '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[2m])) * 100)' \
  | jq -r '.data.result[] | "host CPU utilisation: \((.value[1] | tonumber) * 100 | round / 100)%"' | tee -a "$transcript"
log ""
log '$ promql (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100'
promql '(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100' \
  | jq -r '.data.result[] | "host memory in use: \((.value[1] | tonumber) * 100 | round / 100)%"' | tee -a "$transcript"
log ""
log '$ promql topk(5, container_memory_working_set_bytes{id=~"/docker/.+"})'
promql 'topk(5, container_memory_working_set_bytes{id=~"/docker/.+"})' \
  | jq -r '.data.result[] | "\(.metric.id)\t\((.value[1] | tonumber / 1048576) | round) MiB"' | tee -a "$transcript"

log ""
log "--- Application metrics ---------------------------------------------------"
log ""
log "Three notes are created through the API, then counted through Prometheus."
for title in "write the monitoring lab" "check the alert fires" "record the evidence"; do
  curl -fsS --max-time 10 -X POST http://127.0.0.1:8086/api/notes \
    -H 'Content-Type: application/json' -d "{\"title\": \"$title\"}" >/dev/null
done
log ""
log '$ curl http://127.0.0.1:8086/metrics | grep notes_'
curl -fsS --max-time 10 http://127.0.0.1:8086/metrics \
  | grep -E '^notes_(stored_total|storage_writable)' | tee -a "$transcript"
await "Prometheus scraped the application's own note count" 40 \
  'test "$(promql "notes_stored_total" | jq -r ".data.result[0].value[1] // 0")" = "3" && echo true'
log ""
log '$ promql sum by (endpoint) (notes_http_requests_total)'
promql 'sum by (endpoint) (notes_http_requests_total)' \
  | jq -r '.data.result[] | "\(.metric.endpoint)\t\(.value[1]) requests"' | tee -a "$transcript"

# ------------------------------------------------------------------- Grafana
await "Grafana reports a healthy database" 60 \
  'test "$(graf /api/health | jq -r .database)" = "ok" && echo true'
log ""
log '$ curl http://127.0.0.1:3000/api/datasources'
graf /api/datasources | jq -r '.[] | "datasource: \(.name) (\(.type)) -> \(.url), default: \(.isDefault)"' | tee -a "$transcript"
await "the provisioned dashboard is present" 30 \
  'test "$(graf "/api/search?query=DevOps" | jq -r ".[0].uid // \"\"")" = "devops-overview" && echo true'
log ""
log '$ curl http://127.0.0.1:3000/api/search?query=DevOps'
graf "/api/search?query=DevOps" | jq -r '.[] | "dashboard: \(.title) (uid \(.uid))"' | tee -a "$transcript"
await "Grafana can query Prometheus through its datasource proxy" 30 \
  'test "$(curl -fsS --max-time 10 --get "http://127.0.0.1:3000/api/datasources/proxy/uid/prometheus/api/v1/query" --data-urlencode "query=count(up == 1)" | jq -r ".status")" = "success" && echo true'
log ""
log '$ curl http://127.0.0.1:3000/api/datasources/proxy/uid/prometheus/api/v1/query?query=count(up==1)'
curl -fsS --max-time 10 --get "http://127.0.0.1:3000/api/datasources/proxy/uid/prometheus/api/v1/query" \
  --data-urlencode 'query=count(up == 1)' \
  | jq -r '"Grafana queried Prometheus through its datasource: \(.data.result[0].value[1]) targets up"' | tee -a "$transcript"

# -------------------------------------------------------------------- alerts
log ""
log "--- Alerting --------------------------------------------------------------"
log ""
log "No alert is firing while everything is healthy:"
prom /api/v1/alerts | jq -r '"active alerts: \(.data.alerts | length)"' | tee -a "$transcript"
log ""
log "Stopping the application container so the scrape fails:"
run docker stop devops-demo-app
await "TargetDown entered the pending state" 30 \
  'test "$(prom /api/v1/alerts | jq -r "[.data.alerts[] | select(.labels.alertname == \"TargetDown\" and .state == \"pending\")] | length")" -ge 1 && echo true'
log ""
log '$ curl http://127.0.0.1:9090/api/v1/alerts'
prom /api/v1/alerts | jq -r '.data.alerts[] | "\(.labels.alertname)\tjob=\(.labels.job // "-")\t\(.state)"' | tee -a "$transcript"
await "TargetDown moved from pending to firing after its 30s wait" 40 \
  'test "$(prom /api/v1/alerts | jq -r "[.data.alerts[] | select(.labels.alertname == \"TargetDown\" and .state == \"firing\")] | length")" -ge 1 && echo true'
log ""
log '$ curl http://127.0.0.1:9090/api/v1/alerts'
prom /api/v1/alerts | jq -r '.data.alerts[] | "\(.labels.alertname)\tjob=\(.labels.job // "-")\t\(.state)\t\(.annotations.summary // "")"' | tee -a "$transcript"
await "Alertmanager received the firing alert" 40 \
  'test "$(alertm /api/v2/alerts | jq -r "[.[] | select(.labels.alertname == \"TargetDown\")] | length")" -ge 1 && echo true'
log ""
log '$ curl http://127.0.0.1:9093/api/v2/alerts'
alertm /api/v2/alerts | jq -r '.[] | "\(.labels.alertname)\t\(.status.state)\t\(.annotations.summary // "")"' | tee -a "$transcript"

log ""
log "Starting the container again:"
run docker start devops-demo-app
await "the alert resolved once the target answered again" 60 \
  'test "$(prom /api/v1/alerts | jq -r "[.data.alerts[] | select(.labels.alertname == \"TargetDown\")] | length")" -eq 0 && echo true'
log ""
log '$ curl http://127.0.0.1:9090/api/v1/alerts'
prom /api/v1/alerts | jq -r '"active alerts: \(.data.alerts | length)"' | tee -a "$transcript"

# ---------------------------------------------------------------------- logs
log ""
log "--- Logs: the third signal ------------------------------------------------"
log ""
log "The metric said a scrape failed. The logs say what happened inside the"
log "containers while it did."
run docker logs --tail 6 devops-prometheus
run docker logs --tail 6 devops-demo-app

log ""
log "Stages that reported a failure: $failures"
log ""
log "The stack is still running. Stop it with:"
log "  docker compose -f monitoring-observability-gitops/monitoring/docker-compose.yml down -v"
exit "$failures"
