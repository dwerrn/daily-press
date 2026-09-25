from pathlib import Path
import stat

import yaml


ROOT = Path(__file__).parents[1]


def test_compose_has_healthcheck_persistent_data_and_lan_binding() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    service = compose["services"]["daily-press"]

    assert service["healthcheck"]["test"] == [
        "CMD-SHELL",
        "curl -fsS http://127.0.0.1:8080/healthz || exit 1",
    ]
    assert "./data:/app/data" in service["volumes"]
    assert "./config:/app/config:ro" in service["volumes"]
    assert service["env_file"] == [".env"]
    assert "${DAILY_PRESS_BIND_ADDRESS:-192.168.0.123}:8080:8080" in service["ports"]
    assert service["cap_drop"] == ["ALL"]


def test_systemd_timer_is_persistent_and_bounded() -> None:
    timer = (ROOT / "deploy/daily-press-generate.timer").read_text(encoding="utf-8")

    assert "OnCalendar=*-*-* 05:30:00 America/New_York" in timer
    assert "Persistent=true" in timer
    assert "RandomizedDelaySec=300" in timer


def test_deployment_scripts_are_executable_and_preserve_secrets() -> None:
    for name in ("install.sh", "deploy.sh"):
        path = ROOT / "deploy" / name
        assert path.stat().st_mode & stat.S_IXUSR
    deploy = (ROOT / "deploy/deploy.sh").read_text(encoding="utf-8")
    install = (ROOT / "deploy/install.sh").read_text(encoding="utf-8")

    assert "sqlite3" in deploy
    assert 'BACKUP_DIR="${APP_DIR}/.releases/backups"' in deploy
    assert 'BACKUP_PATH="${BACKUP_DIR}/daily-press-${STAMP}.db"' in deploy
    assert 'install -d -o root -g root -m 0700 "${BACKUP_DIR}"' in deploy
    assert '"${APP_DIR}/data/backups"' not in deploy
    assert "git archive" not in deploy
    assert 'ln -s "${APP_DIR}/data"' not in deploy
    assert "prior release snapshot" not in deploy
    assert "Daily Press deployment failed its health check" in deploy
    assert 'install -d -o root -g root -m 0700 "${APP_DIR}/.releases/backups"' in install
    assert '"${APP_DIR}/data/backups"' not in install
    assert "missing ${APP_DIR}/.env" in deploy
