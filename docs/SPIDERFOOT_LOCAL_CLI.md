# SpiderFoot Local CLI Mode (No Ports)

This mode runs SpiderFoot scans without exposing any ports.

## Zero-port options

### Option A: One-shot docker run

```bash
TARGET=example.com OUT_FILE=example.com.json bash ./scripts/spiderfoot_local_scan.sh
```

Results are written to:

- `monitoring/spiderfoot/local-data/<OUT_FILE>`

### Option B: Local compose container (still no published ports)

```bash
make spiderfoot-local-up
```

Then run scans with:

```bash
make spiderfoot-local-scan TARGET=example.com OUT=example.com.json
make spiderfoot-local-batch TARGETS="example.com 8.8.8.8 user@gmail.com"
```

Stop container:

```bash
make spiderfoot-local-down
```

## Notes

- `docker-compose.spiderfoot.local.yml` does not define `ports` or `expose`.
- This is CLI-only execution for maximum isolation.
- Default module set: `ALL`
- Uses direct `sf.py` CLI mode (no web server, no exposed ports)
