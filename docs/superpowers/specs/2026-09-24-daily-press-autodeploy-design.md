# Daily Press CI-Gated Auto-Deployment Design

**Date:** 2026-09-24
**Status:** Approved design; implementation has not started.

## Goal

Keep the production Daily Press LXC (123) up to date with the tested `main`
branch of `dwerrn/daily-press`, using the same conservative polling model as
Forge. A bad, untested, or unavailable upstream revision must never replace a
known healthy production release.

## Scope

This change adds continuous integration and a production deployment controller.
It does not change the newspaper's editorial source selection, external LAN
address, generation schedule, or deterministic-editorial fallback.

## Architecture

The production LXC owns a root-only deployment cache at
`/var/lib/daily-press-deploy/repo`. The cache is a detached Git checkout which
fetches `main` from GitHub over HTTPS. It is separate from the live application
directory, `/opt/daily-press`.

A systemd timer invokes the controller every five minutes. The controller:

1. acquires a non-blocking deployment lock;
2. fetches the current remote `main` SHA into the isolated cache;
3. exits successfully if that SHA is already the recorded production release;
4. uses the GitHub CLI and a root-only read credential to require successful CI
   for that exact SHA;
5. stages the checked-out revision while retaining production-only state
   (`.env`, SQLite data, edition archive, and any generated output);
6. invokes the committed deployment entrypoint from the staged revision;
7. verifies the container health endpoint and the expected running image;
8. records the new healthy SHA only after verification succeeds.

The deployer does not use the developer LXC checkout or any uncommitted source.
It does not accept inbound webhooks and exposes no new network port.

## Components

- `.github/workflows/ci.yml` runs the Daily Press test suite for pull requests
  and commits to `main`. Deployment considers the workflow's required result as
  its release gate.
- `deploy/daily-press-autodeploy` is the small, root-run controller. It owns
  fetch, CI verification, locking, staging, deployment invocation, health
  verification, and state updates.
- `deploy/daily-press-deploy-alert` sends concise, deduplicated operational
  alerts through the already configured local Postfix relay.
- Systemd service and timer units schedule the five-minute controller run.
  A staleness check warns if a successful GitHub commit remains undeployed
  beyond the allowed window.
- `deploy/install.sh` installs and reconciles the controller, units, required
  packages, cache directory, ownership, and secrets-file permissions.
- The existing `deploy/deploy.sh` remains the release builder/launcher; its
  interface will be made explicit enough for the controller to deploy a staged
  revision rather than the live checkout.

## Security and Secrets

The deployment identity is a GitHub fine-grained credential with read-only
access limited to this repository and to the CI-status information needed by
the gate. It is stored in a root-owned `0600` configuration file on LXC 123;
it is never committed, logged, added to the container image, or copied into the
application environment.

Production continues to bind only to its existing LAN address and port. The
timer's polling model avoids a public webhook endpoint and removes the need for
GitHub to reach the homelab.

## Failure Behavior

The controller fails closed:

- Git fetch, authentication, GitHub-status, or CI failures prevent deployment.
- A failed staging, Docker build, container start, or health check preserves
  the previously healthy application and does not record the candidate SHA.
- Concurrent timer/manual invocations are skipped while the lock is held.
- Failure state includes the candidate SHA, timestamp, and concise reason.
  Alerts are deduplicated for the same failed SHA/reason combination.
- A separate stale-release check alerts only when a newer CI-passing SHA has
  remained undeployed longer than the configured threshold.

## Data Flow

```text
GitHub main -> GitHub Actions CI -> root-only cache on LXC 123
                                      |
                                      v
five-minute systemd timer -> deploy controller -> stage -> deploy.sh
                                      |                         |
                                      v                         v
                             release state / alerts       Docker health check
```

The recorded release SHA is the sole source of truth for the currently verified
deployment. The controller changes it only after the health check passes.

## Verification Strategy

Before the change is accepted:

1. CI demonstrates the existing Python suite passes from a clean checkout.
2. Automated controller tests cover no-op at the recorded SHA, failed/pending
   CI, GitHub-query error, successful update, lock contention, failed health
   check, and alert de-duplication.
3. Installation is verified in LXC 123: units are enabled, timer cadence is
   five minutes, cache and secret permissions are root-only, and the existing
   Daily Press service remains healthy.
4. A controlled deployment from a CI-passing commit proves the recorded SHA,
   Docker health, HTTP health endpoint, archived-edition index, and PDF serving
   endpoint all agree.
5. A rollback simulation proves a failing candidate does not replace the last
   healthy release.

## Non-Goals

- No webhook-based deployment.
- No automatic modification of content sources or editorial policy.
- No automatic creation of public DNS, TLS, or internet-facing ingress.
- No deployment of uncommitted developer changes.
