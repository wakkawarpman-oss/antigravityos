# Apache NiFi Logging Setup (Production)

This setup adds a dedicated NiFi + Loki + Promtail + Grafana stack for flow logging.

## Components

- NiFi UI: `http://localhost:8080/nifi`
- Loki: `http://localhost:3101`
- Grafana: `http://localhost:3001`

## Added files

- `docker-compose.nifi.yml`
- `monitoring/nifi/conf/logback.xml`
- `monitoring/nifi/conf/nifi.properties`
- `monitoring/nifi/promtail-config.yml`
- `monitoring/grafana/dashboards/nifi-logging-dashboard.json`

## Start/stop

```bash
make nifi-up
make nifi-logs
make nifi-down
```

## NiFi production logging defaults

- Rolling file: `nifi-app.log`
- Rotation: daily + `500MB`
- Retention: `14 days`
- Cap: `10GB`
- Pattern includes:
  - `processor=%X{processor}`
  - `flowfile_uuid=%X{uuid}`

## Promtail pipeline

Promtail scrapes:

- `/var/log/nifi/nifi-app*.log`

Extracted labels:

- `level`
- `processor`
- `uuid`
- `logger`

## Grafana usage

Dashboard auto-provisioned:

- **NiFi Flow Logging - Production**

Example query in Explore:

```logql
{job="nifi"} |~ "shodan|censys|LogAttribute|LogMessage"
```

## Notes

- This stack is isolated from `docker-compose.grafana.yml` and uses different ports.
- If Docker daemon is unavailable, start Docker Desktop first.
