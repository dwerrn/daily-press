from pathlib import Path

import pytest
from pydantic import ValidationError

from daily_press.config import config_directory, load_settings, load_sources


def test_load_sources_reads_named_yaml_sources() -> None:
    sources = load_sources()

    assert [(source.name, source.section) for source in sources] == [
        ("Reuters", "top"),
        ("AP", "top"),
        ("NASA", "aerospace-defense"),
        ("Defense One", "aerospace-defense"),
        ("IEEE Spectrum", "engineering-technology"),
        ("The Register", "engineering-technology"),
    ]
    assert all(source.url.startswith("https://") for source in sources)


def test_load_settings_uses_new_york_defaults() -> None:
    settings = load_settings()

    assert settings.location_name == "New York, United States"
    assert settings.latitude == 40.7128
    assert settings.longitude == -74.0060
    assert settings.timezone == "America/New_York"
    assert settings.archive_dir == "data/archive"
    assert settings.database_url == "sqlite:///data/daily-press.db"


def test_load_sources_rejects_unknown_yaml_keys(tmp_path: Path) -> None:
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(
        "sources:\n"
        "  - name: Reuters\n"
        "    url: https://www.reuters.com/\n"
        "    section: top\n"
        "    unexpected: value\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_sources(sources_path)


def test_settings_is_immutable() -> None:
    settings = load_settings()

    with pytest.raises(ValidationError):
        settings.timezone = "UTC"


def test_config_directory_uses_explicit_environment_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DAILY_PRESS_CONFIG_DIR", str(tmp_path))

    assert config_directory() == tmp_path
def test_load_settings_rejects_unknown_yaml_keys(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(
        "location:\n"
        "  name: New York, United States\n"
        "  latitude: 40.7128\n"
        "  longitude: -74.0060\n"
        "  timezone: America/New_York\n"
        "unexpected: value\n",
        encoding="utf-8",
    )
    (tmp_path / "sources.yaml").write_text("sources: []\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        load_settings(settings_path)


def test_config_directory_uses_repository_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DAILY_PRESS_CONFIG_DIR", raising=False)

    assert config_directory().name == "config"
