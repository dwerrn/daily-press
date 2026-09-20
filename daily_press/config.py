from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from daily_press.models import Source


CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    location_name: str
    latitude: float
    longitude: float
    timezone: str
    data_dir: str = "data"
    archive_dir: str = "data/archive"
    database_url: str = "sqlite:///data/daily-press.db"
    sources: tuple[Source, ...] = ()


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as config_file:
        data = yaml.safe_load(config_file)
    return data or {}


def load_sources(path: Path | None = None) -> tuple[Source, ...]:
    data = _read_yaml(path or CONFIG_DIR / "sources.yaml")
    return tuple(Source.model_validate(source) for source in data["sources"])


def load_settings(path: Path | None = None) -> Settings:
    settings_path = path or CONFIG_DIR / "settings.yaml"
    data = _read_yaml(settings_path)
    location = data.pop("location")
    return Settings(
        **data,
        location_name=location["name"],
        latitude=location["latitude"],
        longitude=location["longitude"],
        timezone=location["timezone"],
        sources=load_sources(settings_path.with_name("sources.yaml")),
    )
