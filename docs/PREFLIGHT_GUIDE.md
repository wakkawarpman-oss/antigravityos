# preflight.py Guide

## Purpose

`preflight.py` validates required runtime/API keys before launch and reports missing values with actionable fallbacks.

## How It Works

The script loads environment values from `.env` via `python-dotenv`, then checks configured keys from its internal map.

- Non-empty key -> `active`
- Missing/empty key -> `warning`

## Install

```bash
pip install python-dotenv
```

## Required Location

Place `.env` in the project root (same level as `preflight.py`).

## Example .env (generic app keys)

```ini
API_KEY=sk_abc123xyz
DATABASE_URL=postgresql://localhost:5432/mydb
DEBUG=True
PORT=8000
SECRET_KEY=secret_123456
REDIS_URL=redis://localhost:6379
JWT_SECRET=jwt_secret_789
S3_BUCKET=my-s3-bucket
EMAIL_SERVICE=smtp
```

## Run

```bash
python3 preflight.py
```

## Output Meaning

- `active_keys`: number of keys with values
- `warning_keys`: number of missing/empty keys
- `final_status`: overall readiness summary

## Multiple Environments

For environment isolation, keep separate files:

- `.env.dev`
- `.env.prod`

To load a specific file, update the loader call in `preflight.py`:

```python
load_dotenv(".env.prod")
```

## Operational Recommendations

- Run preflight before deploy and scheduled jobs.
- Keep secrets out of source control.
- Add JSON output mode for CI/CD parsing.
