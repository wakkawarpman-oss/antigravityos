# Grafana Dashboard Setup (Hanna v3.2)

This project now includes a ready-to-run Grafana monitoring stack with:

- Grafana on `http://localhost:3000`
- Loki for logs (`job=hanna`)
- Promtail log shipping from `./logs` and `./runs`
- Prometheus metrics scraping
- Pre-provisioned dashboard: **Hanna v3.2 - Data Quality & Logs**

## Quick start

```bash
make grafana-up
```

Login:

- User: `admin`
- Password: `admin`

## Useful commands

```bash
make grafana-logs
make grafana-down
make grafana-open
```

## Files added

- `docker-compose.grafana.yml`
- `monitoring/promtail/config.yml`
- `monitoring/prometheus/prometheus.yml`
- `monitoring/grafana/provisioning/datasources/datasources.yml`
- `monitoring/grafana/provisioning/dashboards/dashboards.yml`
- `monitoring/grafana/dashboards/hanna-quality-dashboard.json`

## Dashboard panels

- Parse Rate % (Prometheus)
- Validation Rate % (Prometheus)
- Quality Counters (1h)
- Adapter Errors (Live Logs via Loki)
- Top Failing Adapters (5m)

## Notes

- Prometheus target is configured to `host.docker.internal:3000/metrics`.
- If your API runs on another host/port, update:
  - `monitoring/prometheus/prometheus.yml`
- Promtail scans:
  - `./logs/**/*.log`
  - `./runs/**/*.log`

## Importing external dashboard 7752

If you also want Grafana Labs dashboard ID 7752:

1. Open Grafana UI.
2. Go to Dashboards -> Import.
3. Enter `7752` and load.
4. Select Loki datasource.
