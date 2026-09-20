import json
from pathlib import Path

import httpx
import pytest

from daily_press.collectors import CollectorError
from daily_press.collectors.weather import WeatherForecast, collect_weather


FIXTURES = Path(__file__).parent / "fixtures"


def test_collect_weather_maps_open_meteo_forecast() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json=json.loads((FIXTURES / "weather.json").read_text()))

    client = httpx.Client(transport=httpx.MockTransport(handler))

    forecast = collect_weather(40.7128, -74.0060, client=client)

    assert forecast == WeatherForecast(
        current_temperature_c=16.4,
        high_temperature_c=23.7,
        low_temperature_c=15.1,
        precipitation_probability=35,
        condition="partly cloudy",
    )
    assert captured_request is not None
    assert captured_request.url.host == "api.open-meteo.com"
    assert captured_request.url.params["latitude"] == "40.7128"
    assert captured_request.url.params["longitude"] == "-74.006"
    assert captured_request.url.params["current"] == "temperature_2m,weather_code"
    assert captured_request.url.params["daily"] == (
        "temperature_2m_max,temperature_2m_min,precipitation_probability_max"
    )


def test_collect_weather_wraps_http_failures_as_collector_errors() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(500, request=request))
    )

    with pytest.raises(CollectorError, match="weather"):
        collect_weather(40.7128, -74.0060, client=client)
