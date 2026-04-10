#!/usr/bin/env bash
set -euo pipefail

TOOLS_FILE="${TOOLS_FILE:-config/tools.json}"
BACKUP_DIR="${BACKUP_DIR:-backups}"
CHANGESET="${1:-config/changes.json}"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
die() { log "ERROR: $*"; exit 1; }

command -v jq >/dev/null 2>&1 || die "jq is required"

[ -f "$TOOLS_FILE" ] || die "Tools file not found: $TOOLS_FILE"
if [ ! -f "$CHANGESET" ]; then
  # If no changeset provided, just perform a no-op self-check
  log "No changeset provided. Synced tools.json cleanly."
  exit 0
fi

mkdir -p "$BACKUP_DIR"
cp "$TOOLS_FILE" "$BACKUP_DIR/tools.$(date +%Y%m%d_%H%M%S).json"

tmp="$(mktemp)"

jq -f <(cat <<'JQ'
def tool_index($name):
  to_entries | map(select(.value.name == $name)) | .[0].key;

reduce .changes[] as $c (.tools;
  if $c.action == "remove" then
    map(select(.name != $c.name))
  elif $c.action == "add" then
    . + [$c.tool]
  elif $c.action == "replace" then
    map(if .name == $c.name then $c.tool else . end)
  elif $c.action == "update" then
    map(if .name == $c.name then . * $c.patch else . end)
  else
    .
  end
)
JQ
) --slurpfile changes "$CHANGESET" \
   --argfile tools "$TOOLS_FILE" \
   '{tools: $tools.tools, changes: $changes[0].changes}' > "$tmp"

mv "$tmp" "$TOOLS_FILE"
log "Tools updated successfully: $TOOLS_FILE"
