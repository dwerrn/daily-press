# Daily Press MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a deployable Daily Press service that creates and archives a live weather/RSS personal newspaper PDF each morning.

**Architecture:** One Python 3.13 FastAPI package exposes the archive and a guarded manual generation endpoint. A shared CLI runs fixture-tested collection, SQLite persistence, deterministic/OpenAI editorial selection, Jinja rendering, and Playwright PDF generation. Compose runs the app in LXC 123; a systemd timer invokes the CLI daily.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy/SQLite, Pydantic Settings, httpx, feedparser, OpenAI Python SDK, Jinja2, Playwright Chromium, pytest, Docker Compose, systemd.

---

## File structure

- `pyproject.toml` — dependencies, Ruff, pytest, and CLI entry point.
- `daily_press/config.py` — validated environment and YAML-backed settings.
- `daily_press/models.py` — Pydantic content, weather, story, and edition models.
- `daily_press/db.py` — SQLite engine, schema, and repository operations.
- `daily_press/collectors/` — isolated RSS and weather adapters.
- `daily_press/editorial.py` — scoring, repeat suppression, and OpenAI editor boundary.
- `daily_press/rendering.py` — Jinja HTML and PDF renderer.
- `daily_press/generator.py` — locked orchestration and archive persistence.
- `daily_press/main.py` / `daily_press/cli.py` — HTTP and command interfaces.
- `templates/edition.html` / `static/edition.css` — print-first edition template.
- `config/*.yaml` / `config/editorial.md` — tracked, editable editorial settings.
- `tests/fixtures/` and `tests/` — fixture-only unit, integration, and renderer checks.
- `deploy/` — Docker, systemd, deployment, backup, and install files.

### Task 1: Initialize the testable Python package

**Files:**
- Create: `pyproject.toml`, `daily_press/__init__.py`, `tests/test_health.py`, `.gitignore`, `.env.example`

- [ ] **Step 1: Write the failing FastAPI health test.**

```python
from fastapi.testclient import TestClient
from daily_press.main import create_app

def test_healthz_reports_ready() -> None:
    response = TestClient(create_app()).get('/healthz')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
```

- [ ] **Step 2: Run the focused test and confirm import failure.**

Run: `uv run pytest tests/test_health.py::test_healthz_reports_ready -q`

Expected: FAIL because `daily_press.main` does not exist.

- [ ] **Step 3: Add the minimum package, dependency, and app factory.**

```toml
[project]
name = "daily-press"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = ["fastapi>=0.115", "uvicorn[standard]>=0.30"]

[project.optional-dependencies]
dev = ["pytest>=8.3", "httpx>=0.27"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

```python
# daily_press/main.py
from fastapi import FastAPI

def create_app() -> FastAPI:
    app = FastAPI(title="Daily Press")
    @app.get('/healthz')
    def healthz() -> dict[str, str]:
        return {'status': 'ok'}
    return app

app = create_app()
```

- [ ] **Step 4: Run the focused test, then commit.**

Run: `uv run --extra dev pytest tests/test_health.py -q`

Expected: `1 passed`.

Commit: `git add pyproject.toml daily_press tests .gitignore .env.example && git commit -m "feat: initialize Daily Press service"`

### Task 2: Define validated settings and domain models

**Files:**
- Create: `daily_press/config.py`, `daily_press/models.py`, `config/settings.yaml`, `config/sources.yaml`, `config/editorial.md`, `tests/test_config.py`, `tests/test_models.py`

- [ ] **Step 1: Write failing configuration and canonical-URL tests.**

```python
from daily_press.models import ContentItem

def test_content_item_strips_tracking_parameters() -> None:
    item = ContentItem(source="Reuters", title="Test", url="https://example.test/a?utm_source=x&id=4")
    assert item.canonical_url == "https://example.test/a?id=4"
```

```python
from daily_press.config import load_settings

def test_settings_loads_sources_from_yaml(tmp_path) -> None:
    (tmp_path / "sources.yaml").write_text("sources:\n  - name: NASA\n    url: https://example.test/rss\n    section: radar\n")
    assert load_settings(tmp_path).sources[0].name == "NASA"
```

- [ ] **Step 2: Run the two tests and confirm missing-module failures.**

Run: `uv run --extra dev pytest tests/test_config.py tests/test_models.py -q`

Expected: FAIL because the modules do not exist.

- [ ] **Step 3: Implement immutable Pydantic models and YAML settings.**

```python
class ContentItem(BaseModel):
    source: str
    title: str
    url: str
    summary: str = ""
    published_at: datetime | None = None
    section: str = "top"
    @property
    def canonical_url(self) -> str: ...
```

```python
class Settings(BaseModel):
    timezone: str = "America/New_York"
    location_name: str
    latitude: float
    longitude: float
    archive_dir: Path = Path("data/archive")
    database_url: str = "sqlite:///data/daily_press.db"
    sources: list[Source]
```

Implement `load_settings(config_dir: Path) -> Settings` with `yaml.safe_load`, and seed the six approved sources plus the editorial profile.

- [ ] **Step 4: Re-run tests and commit.**

Run: `uv run --extra dev pytest tests/test_config.py tests/test_models.py -q`

Expected: all pass.

Commit: `git add daily_press config tests && git commit -m "feat: add editorial configuration and models"`

### Task 3: Add independent, fixture-tested collectors

**Files:**
- Create: `daily_press/collectors/rss.py`, `daily_press/collectors/weather.py`, `tests/fixtures/rss.xml`, `tests/fixtures/weather.json`, `tests/test_rss.py`, `tests/test_weather.py`

- [ ] **Step 1: Write failing RSS and weather tests using fixture transports.**

```python
async def test_rss_collector_normalizes_feed_entries(respx_mock) -> None:
    respx_mock.get("https://feed.test/rss").respond(200, text=RSS_FIXTURE)
    items = await RssCollector(httpx.AsyncClient()).collect(Source(name="NASA", url="https://feed.test/rss", section="radar"))
    assert [item.title for item in items] == ["Artemis update", "Flight test"]
```

```python
async def test_weather_collector_returns_daily_forecast(respx_mock) -> None:
    respx_mock.get("https://api.open-meteo.com/v1/forecast").respond(200, json=WEATHER_FIXTURE)
    weather = await WeatherCollector(httpx.AsyncClient()).collect(38.9, -77.0)
    assert weather.high_f == 82
```

- [ ] **Step 2: Run tests and confirm collector import failures.**

Run: `uv run --extra dev pytest tests/test_rss.py tests/test_weather.py -q`

Expected: FAIL because collectors are absent.

- [ ] **Step 3: Implement timeout-bounded collectors.**

Use `httpx.AsyncClient(timeout=15.0, follow_redirects=True)` and `feedparser.parse`. RSS failures must raise `CollectorError(source, message)`; the orchestrator handles it. Weather uses Open-Meteo forecast fields `temperature_2m_max`, `temperature_2m_min`, `precipitation_probability_max`, and `weather_code`.

- [ ] **Step 4: Re-run collector tests and commit.**

Run: `uv run --extra dev pytest tests/test_rss.py tests/test_weather.py -q`

Expected: all pass without network access.

Commit: `git add daily_press/collectors tests && git commit -m "feat: collect weather and RSS sources"`

### Task 4: Persist stories and deterministically select candidates

**Files:**
- Create: `daily_press/db.py`, `daily_press/editorial.py`, `tests/test_repository.py`, `tests/test_editorial.py`

- [ ] **Step 1: Write failing repeat-suppression test.**

```python
def test_pre_rank_excludes_recently_printed_story(repository) -> None:
    item = ContentItem(source="NASA", title="Flight test", url="https://nasa.test/flight")
    repository.record_printed(item, date(2026, 9, 19))
    assert pre_rank([item], repository, date(2026, 9, 20)) == []
```

- [ ] **Step 2: Run focused tests and confirm failure.**

Run: `uv run --extra dev pytest tests/test_repository.py tests/test_editorial.py -q`

Expected: FAIL because persistence and ranking are absent.

- [ ] **Step 3: Implement schema and scoring.**

Create tables `sources`, `stories`, `editions`, `edition_items`, and `runs` with SQLAlchemy. Store canonical URL hashes. `pre_rank` removes items printed in the prior seven days and sorts remaining items by configured source weight, title/summary topic matches, and recency; it returns at most 12 candidates.

- [ ] **Step 4: Re-run persistence/editorial tests and commit.**

Run: `uv run --extra dev pytest tests/test_repository.py tests/test_editorial.py -q`

Expected: all pass using temporary SQLite databases.

Commit: `git add daily_press tests && git commit -m "feat: add story memory and deterministic ranking"`

### Task 5: Add an OpenAI editor with a safe deterministic fallback

**Files:**
- Create: `daily_press/openai_editor.py`, `tests/test_openai_editor.py`

- [ ] **Step 1: Write failing editor contract test.**

```python
def test_editor_returns_three_source_attributed_stories(fake_openai) -> None:
    edition = OpenAIEditor(fake_openai).select(CANDIDATES)
    assert len(edition.top_stories) == 3
    assert edition.top_stories[0].source == "Reuters"
```

- [ ] **Step 2: Run the test and confirm the editor is missing.**

Run: `uv run --extra dev pytest tests/test_openai_editor.py -q`

Expected: FAIL with import error.

- [ ] **Step 3: Implement structured editorial selection.**

Send only the pre-ranked source, title, URL, excerpt, section, and date to `gpt-5-mini` through the OpenAI Responses API. Require JSON matching `EditionSelection`. Validate returned indices and source attribution. On absent API key, invalid model response, or API error, select the top deterministic candidates and write summaries from source excerpts; record the degraded mode in the run.

- [ ] **Step 4: Re-run editor test and commit.**

Run: `uv run --extra dev pytest tests/test_openai_editor.py -q`

Expected: all pass with a fake client and no API call.

Commit: `git add daily_press tests && git commit -m "feat: add OpenAI editorial selection"`

### Task 6: Render a print-first edition and archive a PDF

**Files:**
- Create: `daily_press/rendering.py`, `templates/edition.html`, `static/edition.css`, `tests/test_rendering.py`

- [ ] **Step 1: Write failing HTML/PDF rendering test.**

```python
def test_renderer_writes_letter_pdf(tmp_path, sample_edition) -> None:
    pdf_path = Renderer(template_dir=TEMPLATES).render_pdf(sample_edition, tmp_path)
    assert pdf_path.suffix == ".pdf"
    assert pdf_path.read_bytes().startswith(b"%PDF")
```

- [ ] **Step 2: Run test and confirm renderer failure.**

Run: `uv run --extra dev pytest tests/test_rendering.py -q`

Expected: FAIL because `Renderer` is absent.

- [ ] **Step 3: Implement Jinja and Playwright rendering.**

Render `edition.html` with date, weather, three top stories, and two radar stories. In `edition.css`, set `@page { size: Letter; margin: 0.35in; }`, compact serif typography, three columns, black rules, and print color adjustment. Launch Chromium with Playwright, call `page.pdf(format="Letter", print_background=True)`, and close the browser in `finally`.

- [ ] **Step 4: Re-run renderer test and commit.**

Run: `uv run --extra dev pytest tests/test_rendering.py -q`

Expected: a valid fixture-driven PDF is written.

Commit: `git add daily_press templates static tests && git commit -m "feat: render Daily Press PDF editions"`

### Task 7: Orchestrate generation and expose archive operations

**Files:**
- Create: `daily_press/generator.py`, `daily_press/cli.py`, `tests/test_generation.py`, `tests/test_archive_api.py`
- Modify: `daily_press/main.py`

- [ ] **Step 1: Write failing end-to-end generation and archive tests.**

```python
async def test_generation_archives_partial_edition_when_one_source_fails(generator) -> None:
    result = await generator.generate(date(2026, 9, 20))
    assert result.status == "partial"
    assert result.pdf_path.exists()
```

```python
def test_archive_endpoint_serves_latest_pdf(client, archived_edition) -> None:
    response = client.get(f"/editions/{archived_edition.date}/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
```

- [ ] **Step 2: Run focused tests and confirm missing orchestrator failures.**

Run: `uv run --extra dev pytest tests/test_generation.py tests/test_archive_api.py -q`

Expected: FAIL because generation and archive routes are absent.

- [ ] **Step 3: Implement a locked generation path.**

`EditionGenerator.generate()` uses `filelock.FileLock`, collects each source with `asyncio.gather(..., return_exceptions=True)`, records source errors, calls ranking/editor/rendering, and creates `data/archive/YYYY-MM-DD/{edition.html,daily-press.pdf}`. Add `GET /`, `GET /editions/{date}`, `GET /editions/{date}/pdf`, and `POST /editions/generate`. The CLI must call this same service, not duplicate logic.

- [ ] **Step 4: Re-run tests and commit.**

Run: `uv run --extra dev pytest tests/test_generation.py tests/test_archive_api.py -q`

Expected: all pass and prove partial editions continue to archive.

Commit: `git add daily_press tests && git commit -m "feat: generate and serve archived editions"`

### Task 8: Package, deploy, and schedule the LXC service

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `deploy/daily-press.service`, `deploy/daily-press-generate.service`, `deploy/daily-press-generate.timer`, `deploy/install.sh`, `deploy/deploy.sh`, `README.md`

- [ ] **Step 1: Write failing deployment configuration checks.**

```python
def test_compose_has_healthcheck_and_persistent_data() -> None:
    compose = yaml.safe_load(Path("docker-compose.yml").read_text())
    assert compose["services"]["daily-press"]["healthcheck"]
    assert "./data:/app/data" in compose["services"]["daily-press"]["volumes"]
```

- [ ] **Step 2: Run the check and confirm deployment files are missing.**

Run: `uv run --extra dev pytest tests/test_deployment.py -q`

Expected: FAIL because Compose is absent.

- [ ] **Step 3: Add hardened service artifacts.**

Docker image installs Playwright Chromium and runs `uvicorn daily_press.main:app --host 0.0.0.0 --port 8080`. Compose mounts `./data:/app/data`, `./config:/app/config:ro`, uses `.env`, publishes `8080` only on the LXC LAN address, and has a `curl -fsS http://127.0.0.1:8080/healthz` health check. The timer runs `docker compose run --rm daily-press daily-press generate`; it has `Persistent=true` and a random delay under five minutes. `deploy.sh` preserves `data/` and `.env`, takes a SQLite backup, rebuilds, verifies health, and retains the prior release directory for rollback.

- [ ] **Step 4: Re-run deployment test and the full suite, then commit.**

Run: `uv run --extra dev pytest -q`

Expected: all tests pass.

Commit: `git add Dockerfile docker-compose.yml deploy README.md tests && git commit -m "feat: package and schedule Daily Press"`

### Task 9: Provision LXC 123 and perform an end-to-end smoke test

**Files:**
- Modify: `.env` on the LXC only

- [ ] **Step 1: Confirm VMID 123 and IP 192.168.0.123 are unused.**

Run: `pct status 123; ping -c 2 -W 1 192.168.0.123`

Expected: no LXC status and no ping replies.

- [ ] **Step 2: Create and start the container.**

Run: `pct create 123 local:vztmpl/debian-13-standard_13.1-2_amd64.tar.zst --hostname daily-press --cores 2 --memory 2048 --swap 512 --rootfs local:16 --net0 name=eth0,bridge=vmbr0,firewall=1,ip=192.168.0.123/24,gw=192.168.0.1 --unprivileged 1 --features nesting=1 --onboot 1`

Then: `pct start 123`.

- [ ] **Step 3: Install Docker and deploy the committed release.**

Run `deploy/install.sh` from the Proxmox host, set `OPENAI_API_KEY` in `/opt/daily-press/.env`, and run `deploy/deploy.sh`.

- [ ] **Step 4: Verify the service, timer, and a live manual edition.**

Run: `pct exec 123 -- curl -fsS http://127.0.0.1:8080/healthz`

Run: `pct exec 123 -- systemctl list-timers daily-press-generate.timer --no-pager`

Run: `pct exec 123 -- docker compose -f /opt/daily-press/docker-compose.yml run --rm daily-press daily-press generate`

Expected: health JSON, enabled next timer run, and a dated PDF under `/opt/daily-press/data/archive/`.

- [ ] **Step 5: Inspect the full diff and record deployment state.**

Run: `git status --short --branch && git log --oneline -5`

Expected: clean committed source tree; `.env`, archive, and SQLite data remain untracked/excluded.

## Plan self-review

- Spec coverage: Tasks 1-8 cover API, configuration, independent collectors, story memory, deterministic/OpenAI editorial selection, print rendering, archive, scheduling, health, deploy/backup/rollback; Task 9 covers the approved LXC and smoke test. Calendar, printing, and personal integrations remain deferred.
- Placeholder scan: no deferred implementation placeholders exist inside MVP tasks; explicitly deferred work is isolated in the design document.
- Type consistency: `ContentItem`, `Settings`, `EditionGenerator.generate`, and `Renderer.render_pdf` retain the same roles across all tasks.
