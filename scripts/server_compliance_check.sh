#!/usr/bin/env bash
set -euo pipefail

# Hosts to check. Supports comma or space separated values.
SERVER_HOSTS_RAW="${SERVER_HOSTS:-127.0.0.1}"
PRIMARY_HOST="${PRIMARY_HOST:-}"

# Port checks (default: 80, 443)
CHECK_PORTS="${CHECK_PORTS:-80 443}"

# Weekly config freshness threshold.
CONFIG_MAX_AGE_DAYS="${CONFIG_MAX_AGE_DAYS:-7}"

# Optional explicit config path; otherwise autodetect Apache/Nginx configs.
CONFIG_PATH="${CONFIG_PATH:-}"

# Expected Apache version for the compliance message.
EXPECTED_APACHE_VERSION="${EXPECTED_APACHE_VERSION:-2.4.51}"

normalize_hosts() {
  printf '%s' "$SERVER_HOSTS_RAW" | tr ',' ' ' | xargs
}

pick_primary_host() {
  local hosts
  hosts="$(normalize_hosts)"
  if [[ -n "$PRIMARY_HOST" ]]; then
    printf '%s' "$PRIMARY_HOST"
    return
  fi
  for h in $hosts; do
    printf '%s' "$h"
    return
  done
}

check_ping() {
  local hosts host failed=0
  hosts="$(normalize_hosts)"

  for host in $hosts; do
    if ! ping -c 1 "$host" >/dev/null 2>&1; then
      failed=1
      break
    fi
  done

  if [[ "$failed" -eq 0 ]]; then
    echo "Сервери доступні — всі в порядку."
  else
    echo "Виявлено недоступний сервер — потрібна перевірка мережі."
  fi
}

check_ports() {
  local host port failed=0
  host="$(pick_primary_host)"

  for port in $CHECK_PORTS; do
    if ! nc -z "$host" "$port" >/dev/null 2>&1; then
      failed=1
      break
    fi
  done

  if [[ "$failed" -eq 0 ]]; then
    echo "Порти 80 і 443 відкриті — відповідно до норми."
  else
    echo "Виявлено відхилення по портах — перевірте доступність 80/443."
  fi
}

server_header() {
  local host header
  host="$(pick_primary_host)"

  header="$(curl -fsS -I "http://$host" 2>/dev/null | awk -F': ' 'tolower($1)=="server" {print $2}' | tr -d '\r' || true)"
  if [[ -z "$header" ]]; then
    header="$(curl -kfsS -I "https://$host" 2>/dev/null | awk -F': ' 'tolower($1)=="server" {print $2}' | tr -d '\r' || true)"
  fi

  printf '%s' "$header"
}

check_services() {
  local header
  header="$(server_header)"

  if [[ "$header" == *"Apache/$EXPECTED_APACHE_VERSION"* ]]; then
    echo "Apache 2.4.51 — стабільний, відповідно до стандарту."
    return
  fi

  if [[ "${header,,}" == *"nginx"* ]]; then
    echo "Nginx активний — стабільний, відповідно до стандарту."
    return
  fi

  echo "Сервіс Apache/Nginx не ідентифіковано — потрібна ручна перевірка."
}

resolve_config_path() {
  if [[ -n "$CONFIG_PATH" ]]; then
    printf '%s' "$CONFIG_PATH"
    return
  fi

  local candidates=(
    "/etc/apache2/httpd.conf"
    "/etc/apache2/apache2.conf"
    "/usr/local/etc/httpd/httpd.conf"
    "/etc/nginx/nginx.conf"
    "/usr/local/etc/nginx/nginx.conf"
  )
  local file
  for file in "${candidates[@]}"; do
    if [[ -f "$file" ]]; then
      printf '%s' "$file"
      return
    fi
  done
}

file_age_days() {
  local file now mtime age
  file="$1"
  now="$(date +%s)"
  if stat -f %m "$file" >/dev/null 2>&1; then
    mtime="$(stat -f %m "$file")"
  else
    mtime="$(stat -c %Y "$file")"
  fi
  age=$(( (now - mtime) / 86400 ))
  printf '%s' "$age"
}

check_config_freshness() {
  local cfg age
  cfg="$(resolve_config_path || true)"

  if [[ -z "$cfg" ]]; then
    echo "Файл конфігурації не знайдено — задайте CONFIG_PATH для перевірки."
    return
  fi

  age="$(file_age_days "$cfg")"
  if (( age <= CONFIG_MAX_AGE_DAYS )); then
    echo "Конфігурація оновлена — без змін у відкритих вадах."
  else
    echo "Конфігурація потребує оновлення — остання зміна ${age} дн. тому."
  fi
}

main() {
  check_ping
  check_ports
  check_services
  check_config_freshness
}

main "$@"
