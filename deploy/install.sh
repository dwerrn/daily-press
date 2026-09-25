#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/daily-press}"
SERVICE_DIR="/etc/systemd/system"
APP_UID="${DAILY_PRESS_UID:-10001}"
APP_GID="${DAILY_PRESS_GID:-10001}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "install.sh must run as root" >&2
  exit 1
fi

if [[ ! -f "${APP_DIR}/docker-compose.yml" ]]; then
  echo "expected source tree at ${APP_DIR}" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install --no-install-recommends -y ca-certificates curl docker.io docker-cli docker-compose git sqlite3

install -d -m 0750 "${APP_DIR}/data" "${APP_DIR}/data/archive" "${APP_DIR}/.releases"
install -d -o root -g root -m 0700 "${APP_DIR}/.releases/backups"
if [[ ! -e "${APP_DIR}/.env" ]]; then
  install -m 0600 "${APP_DIR}/.env.example" "${APP_DIR}/.env"
fi
chown -R "${APP_UID}:${APP_GID}" "${APP_DIR}/data"
chmod 0600 "${APP_DIR}/.env"

install -m 0644 "${APP_DIR}/deploy/daily-press.service" "${SERVICE_DIR}/daily-press.service"
install -m 0644 "${APP_DIR}/deploy/daily-press-generate.service" "${SERVICE_DIR}/daily-press-generate.service"
install -m 0644 "${APP_DIR}/deploy/daily-press-generate.timer" "${SERVICE_DIR}/daily-press-generate.timer"

systemctl daemon-reload
systemctl enable docker.service daily-press.service daily-press-generate.timer
systemctl start docker.service
echo "Daily Press dependencies and systemd units installed. Set OPENAI_API_KEY in ${APP_DIR}/.env before deployment."
