#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/daily-press}"
BIND_ADDRESS="${DAILY_PRESS_BIND_ADDRESS:-192.168.0.123}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DB_PATH="${APP_DIR}/data/daily-press.db"
BACKUP_DIR="${APP_DIR}/.releases/backups"
BACKUP_PATH="${BACKUP_DIR}/daily-press-${STAMP}.db"

if [[ "${EUID}" -ne 0 ]]; then
  echo "deploy.sh must run as root" >&2
  exit 1
fi
if [[ ! -f "${APP_DIR}/.env" ]]; then
  echo "missing ${APP_DIR}/.env; refusing to deploy without explicit configuration" >&2
  exit 1
fi

cd "${APP_DIR}"
docker compose config >/dev/null
install -d -o root -g root -m 0700 "${BACKUP_DIR}"

if [[ -f "${DB_PATH}" ]]; then
  sqlite3 "${DB_PATH}" ".backup '${BACKUP_PATH}'"
  chmod 0640 "${BACKUP_PATH}"
fi


docker compose up -d --build

for attempt in {1..30}; do
  if curl -fsS "http://${BIND_ADDRESS}:8080/healthz" >/dev/null; then
    echo "Daily Press is healthy at http://${BIND_ADDRESS}:8080"
    exit 0
  fi
  sleep 2
done

echo "Daily Press deployment failed its health check." >&2
docker compose ps >&2 || true
docker compose logs --tail=80 daily-press >&2 || true
exit 1
