# Instrumenty ta plan performance testuvannia dlia HANNA

Meta: Otsinyty shvydkist, stabilnist, vykonannia ta resursne vykorystannia pid chas roboty z HANNA vid bazovykh zapytiv do skladnykh protsesiv.

## TOP-8 CLI instrumentiv (bez GUI)

| Instrument | Naikrashche dlia |
| --- | --- |
| k6 | Suchasni load tests, vysokyi RPS, p95/p99 latency, real-time metryky |
| wrk | Shvydki HTTP benchmarks, vysokyi RPS, latency ta throughput |
| hey | POST/JSON zapyty, perevirka API stsenariiv |
| hyperfine | Benchmark komand ta porivniannia realizatsii |
| ab | Prostyi pochatkovyi Apache benchmark |
| siege | Multi-URL navantazhennia i skladni stsenarii |
| ghz | gRPC, HTTP/2, Protobuf navantazhennia |
| mwr | HTTP + analiz pam'iati ta CPU |

## Praktychnyi plan dlia HANNA

### Krok 1: Bazovyi HTTP benchmark

```bash
python3 -m http.server 8000 --bind 127.0.0.1 &
wrk -t12 -c400 -d60s http://localhost:8000/health
hey -n 5000 -c 50 -m POST -d '{"target":"user@example.com"}' http://localhost:8000/api/dossier
```

Target metryky:

- Latency avg blizko 15ms
- p95 do 28ms
- p99 do 45ms
- Requests/s blizko 385k (zalezhno vid seredovyshcha)

### Krok 2: Benchmark CLI komand

```bash
hyperfine --warmup 10 --min-runs 20 \
  'python3 -m hanna.dossier.cli "user@example.com"' \
  'python3 -m hanna.dossier.cli "+380671234567"'
```

Rezultat: porivniannia shvydkosti, stabilnosti ta variatyvnosti vykonannia komand.

### Krok 3: Test pamiati ta CPU

```bash
pip install memory-profiler psutil
python3 -m memory_profiler hanna_dossier_memtest.py
```

Pryklad CPU-zaminu:

```python
import psutil
start_cpu = psutil.cpu_percent()
# Vykonaite komand u testovomu protsesi
end_cpu = psutil.cpu_percent()
print(f"CPU usage: {end_cpu - start_cpu}%")
```

Rezultat: vyiavlennia pidvysiv, leakiv ta pikovykh navantazhen.

### Krok 4: k6 load test (realni umovy)

```javascript
import http from 'k6/http';
import { sleep, check } from 'k6';

export const options = {
  stages: [
    { duration: '10s', target: 10 },
    { duration: '2m', target: 50 },
    { duration: '10s', target: 0 },
  ],
};

export default function () {
  const res = http.get('http://localhost:8000/api/dossier?target=user@example.com');
  check(res, { 'status 200': (r) => r.status === 200 });
  sleep(1);
}
```

```bash
k6 run load_test.js
```

Target metryky:

- p95 < 30ms
- RPS > 300
- error rate = 0

## Shvydkyi start (5 khvylyn)

```bash
# Linux
sudo apt install wrk
cargo install hyperfine

# macOS
brew install wrk hyperfine

hyperfine --warmup 5 'python3 -m hanna.dossier.cli "test@example.com"'
wrk -t4 -c100 -d30s http://localhost:8000/health
pip install memory-profiler
python3 -m memory_profiler -- -m hanna.dossier.cli "test"
```

## Rekomendatsii dlia HANNA

| Instrument | Kontekst vykorystannia |
| --- | --- |
| wrk / hyperfine | Shchodennyi smoke benchmark |
| k6 | Povni load tests v umovakh blizkykh do production |
| memory-profiler | Detektsiia memory leaks |
| hyperfine | Rehresiine porivniannia novykh i starykh versii |

## Plan vykonannia (4 tyzhni)

| Tyzhden | Fokus |
| --- | --- |
| 1 | Tier 1 + Tier 2: unit, integration, property, fuzz |
| 2 | Tier 3: performance, stress, endurance (k6, wrk, hey) |
| 3 | Tier 4 + Tier 5: security, regression, UX, i18n, docs |
| 4 | Tier 6: CI/CD, packaging, RC freeze |

## Kryterii hotovnosti

- p95 latency < 30 ms dlia osnovnykh API zapytiv
- RPS >= 300 pry 100 VUs
- 0 memory leaks pid chas tryvaloho vykonannia
- CPU < 60% pry navantazhenni 100 VUs
- CLI komandy vykonuiutsia za 1-2 sekundy
- Dokumentatsiia ta testovi artefakty aktualni

## Vysnovok

Systema HANNA povynna zalyshatysia shvydkoiu, stabilnoiu ta efektivnoiu za resursamy. Vsi bazovi i navantazhuvalni testy vykonuiutsia v terminali bez GUI, shcho sproboshchuie avtomatyzatsiiu ta masshtabuvannia.
