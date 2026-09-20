# Daily Press MVP Design

## Purpose and scope

Daily Press is a self-hosted, single-user personal newspaper. The MVP produces a one-page (with a supported path to two pages) US Letter, grayscale-friendly PDF each morning. It answers what matters today using live weather and a small curated RSS set. It archives each edition for LAN review; automatic printing, Google Calendar, project integrations, and feedback are later work.

## Deployment

The application runs in a dedicated unprivileged Debian 13 LXC on the Proxmox host:

- VMID: `123`
- hostname: `daily-press`
- network: `192.168.0.123/24` on `vmbr0`, gateway `192.168.0.1`
- resources: two vCPU, 2 GiB RAM, 16 GiB root filesystem

Docker Compose runs the web service and its shared application image. The source tree deploys to `/opt/daily-press`. Persistent SQLite data, HTML/PDF archives, run logs, and the non-versioned `.env` remain outside source synchronization. The container has no public exposure or authentication in the MVP; LAN/host access is enough for validation.

## Architecture

One Python 3.13 FastAPI application provides archive and operational endpoints. The same codebase exposes a CLI generator. A systemd timer in the LXC invokes the generator through Docker Compose every day at 05:30 America/New_York. An advisory run lock prevents concurrent timer and manual runs.

The generation pipeline is:

1. Read validated settings, editorial profile, and configured sources.
2. Collect weather and RSS items independently.
3. Normalize items to a stable `ContentItem` shape and persist them.
4. Deduplicate canonical URLs and title-similar stories; consult previous editions for repetition penalties.
5. Pre-rank candidates deterministically by freshness, source quality, stated interests, and novelty.
6. Send the bounded candidate set to OpenAI for editorial selection and short source-attributed summaries.
7. Construct a versioned edition model, render Jinja HTML, and render a US Letter PDF through Playwright Chromium.
8. Persist the run result and archive dated HTML and PDF files.

Collector failures are isolated. An unavailable feed or weather provider produces a visible compact status note rather than discarding the whole edition. The run record and application log retain diagnostic detail.

## Sources and editorial policy

`config/sources.yaml` initially defines Reuters/AP for major news, NASA and Defense One for aerospace/defense, and IEEE Spectrum and The Register for engineering/technology. Sources are enabled independently and are replaceable without code changes. `config/editorial.md` contains the stated interests, priority topics, source-quality preference, and exclusions from the supplied brief.

The OpenAI API is used only for final ranking and short summaries. Its credential is stored in `.env` as `OPENAI_API_KEY` and is never committed, exposed through HTTP, or written to the SQLite database. The app records inputs/outputs sufficient to understand editorial choices without persisting credentials.

## Data model

SQLite is the durable source of truth. The initial schema contains `sources`, `stories`, `editions`, `edition_items`, and `runs`. Story records retain source identity, canonical URL hash, timestamp, topic hints, and article excerpt. Edition items retain the selected story, section, score, summary, and source attribution. This permits archive browsing, repeat suppression, and later feedback without changing the edition format.

## Interfaces

- `GET /healthz` returns readiness and basic dependency state.
- `GET /` returns the archive index and the most recent run status.
- `GET /editions/{edition_date}` displays a rendered edition.
- `GET /editions/{edition_date}/pdf` downloads its PDF.
- `POST /editions/generate` triggers the same guarded generation path used by the scheduler.
- `daily-press generate` is the CLI entry point for timer and operator use.

## Layout

The printed page uses a serif masthead and headlines, compact body text, rules, narrow columns, and no card/dashboard treatment. Page 1 places the masthead, weather, and schedule at the top; the center column carries the three top stories; the side column carries an Engineering/R&M radar. Source names accompany all stories. The layout is designed at Letter size with 0.35-inch margins and black-and-white printing in mind.

## Operations and verification

The project includes Compose health checks, an installable systemd timer, operational documentation, and a deployment script that preserves `.env` and persistent data. A backup occurs before upgrades. A release can roll back to the preceding image/source revision without overwriting archives or the database.

Tests use local weather and RSS fixtures; they do not need network access or API credits. Unit tests cover normalization, ranking, repeat suppression, and source failure isolation. An integration test builds a complete edition from fixtures. A renderer smoke test asserts a non-empty, valid PDF. Live source and OpenAI checks are explicit operator smoke tests.

## Deferred work

Google Calendar, GitHub/Forge project radar, automatic CUPS printing, a feedback UI/QR code, a second rotating page, public reverse-proxy access, and personalized source onboarding are deliberately out of the MVP. Their interfaces are accommodated by the normalized content and edition models but no external credentials or print actions are included now.
