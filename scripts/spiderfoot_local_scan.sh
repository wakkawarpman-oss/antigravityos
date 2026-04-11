#!/usr/bin/env bash
set -euo pipefail

TARGETS_RAW="${TARGETS:-${TARGET:-}}"
MODULES="${MODULES:-ALL}"
OUT_FILE="${OUT_FILE:-scan.json}"
DATA_DIR="${DATA_DIR:-$PWD/monitoring/spiderfoot/local-data}"
SPIDERFOOT_IMAGE="${SPIDERFOOT_IMAGE:-ctdc/spiderfoot:latest}"

if [[ -z "$TARGETS_RAW" ]]; then
  echo "usage: TARGET=example.com $0"
  echo "   or: TARGETS=\"example.com 8.8.8.8\" $0"
  exit 2
fi

mkdir -p "$DATA_DIR"

target_count=0
for _ in $TARGETS_RAW; do
  target_count=$((target_count + 1))
done

for target in $TARGETS_RAW; do
  safe_target="$(printf '%s' "$target" | tr '/:@ ' '____')"
  out_name="$OUT_FILE"
  if [[ "$target_count" -gt 1 ]]; then
    out_name="${safe_target}.json"
  fi

  docker run --rm \
    --entrypoint python3 \
    -v "$DATA_DIR:/data" \
    "$SPIDERFOOT_IMAGE" \
    /home/spiderfoot/sf.py -q -s "$target" -m "$MODULES" -o json > "$DATA_DIR/$out_name"

  echo "saved: $DATA_DIR/$out_name"
done
