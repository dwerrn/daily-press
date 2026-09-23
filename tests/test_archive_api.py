import asyncio
from datetime import date
from pathlib import Path

import httpx

from daily_press.config import Settings
from daily_press.generator import GenerationResult
from daily_press.main import create_app


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        location_name="New York, United States",
        latitude=40.7,
        longitude=-74.0,
        timezone="America/New_York",
        archive_dir=str(tmp_path / "archive"),
        database_url=str(tmp_path / "daily-press.db"),
    )


def test_archive_endpoint_serves_latest_pdf(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    edition_dir = Path(settings.archive_dir) / "2026-09-20"
    edition_dir.mkdir(parents=True)
    (edition_dir / "edition.html").write_text("<h1>Daily Press</h1>", encoding="utf-8")
    (edition_dir / "daily-press.pdf").write_bytes(b"%PDF-fixture")
    app = create_app(settings=settings)

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(f"/editions/{date(2026, 9, 20)}/pdf")

    response = asyncio.run(request())

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_archive_endpoint_rejects_missing_edition(tmp_path: Path) -> None:
    app = create_app(settings=_settings(tmp_path))

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/editions/2026-09-20/pdf")

    response = asyncio.run(request())

    assert response.status_code == 404


def test_generation_endpoint_uses_shared_generator_without_exposing_paths(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    class FakeGenerator:
        async def generate(self, edition_date: date | None = None) -> GenerationResult:
            target = edition_date or date(2026, 9, 20)
            return GenerationResult(
                edition_date=target,
                status="complete",
                html_path=tmp_path / "archive" / target.isoformat() / "edition.html",
                pdf_path=tmp_path / "archive" / target.isoformat() / "daily-press.pdf",
            )

    app = create_app(settings=settings, generator=FakeGenerator())

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/editions/generate",
                json={"edition_date": "2026-09-20"},
            )

    response = asyncio.run(request())

    assert response.status_code == 200
    assert response.json()["pdf_url"] == "/editions/2026-09-20/pdf"
    assert str(tmp_path) not in response.text
