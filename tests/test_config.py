from daily_press.config import load_settings, load_sources


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
