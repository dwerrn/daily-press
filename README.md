# Daily Press

Daily Press creates a small, print-first personal newspaper from curated RSS
feeds and a local weather forecast. It archives the rendered HTML and PDF by
date and exposes them through a LAN-only FastAPI service.

## Local checks

```bash
uv sync --extra dev
uv run --extra dev pytest -q
```

The PDF smoke test requires the Playwright Chromium browser. Install it with:

```bash
uv run playwright install chromium
```

## Local generation

```bash
cp .env.example .env
daily-press generate --date 2026-09-24
```

Without `OPENAI_API_KEY`, the generator uses its deterministic source-excerpt
fallback. Generated files are written to `data/archive/YYYY-MM-DD/`.

## Compose deployment

The production target is an unprivileged Debian 13 LXC at `192.168.0.123`.
The source tree is deployed to `/opt/daily-press`; `data/` and `.env` remain
outside source synchronization.

On the target machine, after copying the committed `main` tree to
`/opt/daily-press`:

```bash
cd /opt/daily-press
sudo deploy/install.sh
sudoedit /opt/daily-press/.env
sudo deploy/deploy.sh
sudo systemctl start daily-press-generate.timer
```

The web service is bound to `192.168.0.123:8080` by default. To override the
bind address for a controlled local test, set `DAILY_PRESS_BIND_ADDRESS` in the
shell invoking Compose; do not put it in `.env`, because `.env` is passed to the
application and only application settings belong there.

The timer runs daily at 05:30 America/New_York with a five-minute randomized
delay. `deploy.sh` validates Compose configuration, stores root-only SQLite
backups under `.releases/backups/`, rebuilds the service, and waits for
`/healthz` before succeeding. This baseline does not provide automatic
rollback.

## Archive API

```text
GET  /healthz
GET  /
GET  /editions/YYYY-MM-DD
GET  /editions/YYYY-MM-DD/pdf
POST /editions/generate
```

The manual generation endpoint accepts an optional JSON body such as
`{"edition_date":"2026-09-24"}`. The MVP is intentionally LAN-only and has no
public authentication layer.
