# HANNA OPSEC Runbook

## Принципи

HANNA дозволяє маршрутизацію трафіку через Tor або довільний SOCKS/HTTP-проксі.
Кожен адаптер підтримує проксі через аргумент `--proxy` або шорткат `--tor`.

---

## Режими маршрутизації

### Direct (clearnet)

```bash
./scripts/hanna agg --target example.com --modules pd-infra
```

Без проксі. Всі запити йдуть напряму.

### Tor

```bash
./scripts/hanna agg --target example.com --modules httpx_probe,katana,shodan --tor
./scripts/hanna ui --tor --plain
```

`--tor` → `socks5h://127.0.0.1:9050`. Вимагає запущеного Tor (порт 9050).

### Custom proxy

```bash
./scripts/hanna ch --target example.com --modules full-spectrum --proxy socks5h://127.0.0.1:9055
```

Довільний SOCKS5/HTTP проксі.

### Mutual exclusion

```bash
# ПОМИЛКА: Use either --tor or --proxy, not both
./scripts/hanna ch --target example.com --tor --proxy socks5h://127.0.0.1:9055
```

---

## Strict proxy policy

Змінна `HANNA_REQUIRE_PROXY=1` забороняє clearnet-запити:

```bash
HANNA_REQUIRE_PROXY=1 ./scripts/hanna agg --target example.com --modules pd-infra --tor
HANNA_REQUIRE_PROXY=1 ./scripts/hanna ch --target example.com --modules full-spectrum --tor --report-mode shareable --json-summary-only
HANNA_REQUIRE_PROXY=1 ./scripts/hanna ui --tor --plain
```

### Failure signatures

| Повідомлення | Причина |
|---|---|
| `Tor proxy endpoint is unreachable at 127.0.0.1:9050` | Tor не запущено |
| `HANNA_REQUIRE_PROXY=1 but no proxy provided for HTTP request` | HTTP-запит без проксі при strict mode |
| `HANNA_REQUIRE_PROXY=1 but no proxy provided for CLI execution` | CLI-інструмент без проксі |
| `nmap cannot be executed safely with proxy/Tor routing` | nmap не підтримує проксі |
| `Use either --tor or --proxy, not both` | Конфлікт --tor та --proxy |

---

## Безпечний nmap

nmap не маршрутизується через проксі. Якщо `HANNA_REQUIRE_PROXY=1`:

- Видаліть nmap з набору модулів, АБО
- Запускайте nmap окремо в direct mode

---

## Чек-лист перед OPSEC-сесією

1. `tor --verify-config` — конфіг Tor валідний
2. `curl --socks5-hostname 127.0.0.1:9050 https://check.torproject.org/api/ip` — Tor працює
3. `HANNA_REQUIRE_PROXY=1 ./scripts/hanna pf --modules full-spectrum` — preflight
4. Перевірити DNS leak: `--tor` використовує `socks5h://` (DNS через проксі)

---

## Рекомендована конфігурація `.env`

```
# Strict OPSEC: заборонити clearnet
HANNA_REQUIRE_PROXY=1
```
