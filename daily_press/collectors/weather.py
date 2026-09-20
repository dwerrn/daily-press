import httpx
from pydantic import BaseModel, ConfigDict

from daily_press.collectors import CollectorError


FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
USER_AGENT = "Daily Press/0.1 (+https://daily-press.local)"


class WeatherForecast(BaseModel):
    model_config = ConfigDict(frozen=True)

    current_temperature_c: float
    high_temperature_c: float
    low_temperature_c: float
    precipitation_probability: int
    condition: str


def collect_weather(
    latitude: float, longitude: float, timezone: str, *, client: httpx.Client | None = None
) -> WeatherForecast:
    """Fetch the current and daily forecast from Open-Meteo."""
    owns_client = client is None
    http_client = client or httpx.Client()
    try:
        response = http_client.get(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,weather_code",
                "timezone": timezone,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        return WeatherForecast(
            current_temperature_c=payload["current"]["temperature_2m"],
            high_temperature_c=payload["daily"]["temperature_2m_max"][0],
            low_temperature_c=payload["daily"]["temperature_2m_min"][0],
            precipitation_probability=payload["daily"]["precipitation_probability_max"][0],
            condition=_weather_condition(payload["current"]["weather_code"]),
        )
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
        raise CollectorError("weather", str(error)) from error
    finally:
        if owns_client:
            http_client.close()


def _weather_condition(code: int) -> str:
    conditions = {
        0: "clear sky",
        1: "mainly clear",
        2: "partly cloudy",
        3: "overcast",
        45: "fog",
        48: "rime fog",
        51: "light drizzle",
        53: "moderate drizzle",
        55: "heavy drizzle",
        61: "slight rain",
        63: "moderate rain",
        65: "heavy rain",
        71: "slight snow",
        73: "moderate snow",
        75: "heavy snow",
        80: "rain showers",
        81: "moderate rain showers",
        82: "violent rain showers",
        95: "thunderstorm",
        96: "thunderstorm with hail",
        99: "thunderstorm with heavy hail",
    }
    return conditions.get(code, "unknown")
