# Monitoring execution evidence

**Vibhuti Bhatnagar · 24BCS10288 · vibhuti.24bcs10288@sst.scaler.com**

[20-monitoring-stack.txt](20-monitoring-stack.txt) is the transcript from
[`scripts/run-monitoring-lab.sh`](../../scripts/run-monitoring-lab.sh), captured on 7 October 2026.

Worth reading in order:

1. All four scrape targets reporting `up`.
2. Infrastructure metrics read back through PromQL — host CPU, host memory, per-container memory.
3. Application metrics: three notes created through the API, then counted through Prometheus.
4. Grafana's provisioned datasource and dashboard, and a query made through its datasource proxy.
5. The alert path end to end: no alerts → the target is stopped → `pending` → `firing` → Alertmanager
   receives it → the target returns → resolved.
6. Container logs, as the third signal alongside the metric that detected the failure.

Each check polls until it matches, so nothing recorded here is a timing accident. Screenshots are in
[`monitoring-observability-gitops/screenshots/`](../../monitoring-observability-gitops/screenshots/).
