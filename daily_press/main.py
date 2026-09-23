"""FastAPI archive and operational endpoints."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from daily_press.config import Settings, load_settings
from daily_press.db import StoryRepository
from daily_press.generator import EditionGenerator, GenerationInProgress, GenerationResult


class GenerateRequest(BaseModel):
    edition_date: date | None = None


def create_app(
    *,
    settings: Settings | None = None,
    generator: EditionGenerator | None = None,
    repository: StoryRepository | None = None,
) -> FastAPI:
    app = FastAPI(title="Daily Press")
    app.state.settings = settings or load_settings()
    app.state.generator = generator
    app.state.repository = repository

    @app.middleware("http")
    async def security_headers(request: Any, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
        return response

    def get_repository() -> StoryRepository:
        if app.state.repository is None:
            app.state.repository = StoryRepository(app.state.settings.database_url)
        return app.state.repository

    def get_generator() -> EditionGenerator:
        if app.state.generator is None:
            app.state.generator = EditionGenerator(
                app.state.settings,
                repository=get_repository(),
            )
        return app.state.generator

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    async def archive_index() -> dict[str, object]:
        archive_dir = Path(app.state.settings.archive_dir)
        editions = []
        if archive_dir.is_dir():
            for child in sorted(archive_dir.iterdir(), reverse=True):
                try:
                    edition_date = date.fromisoformat(child.name)
                except ValueError:
                    continue
                if not child.is_dir() or not (child / "edition.html").is_file():
                    continue
                editions.append(
                    {
                        "date": edition_date.isoformat(),
                        "html": True,
                        "pdf": (child / "daily-press.pdf").is_file(),
                    }
                )
        return {"editions": editions, "latest_run": get_repository().latest_run()}

    @app.get("/editions/{edition_date}")
    async def edition_html(edition_date: date) -> HTMLResponse:
        path = Path(app.state.settings.archive_dir) / edition_date.isoformat() / "edition.html"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="edition not found")
        return HTMLResponse(path.read_text(encoding="utf-8"))

    @app.get("/editions/{edition_date}/pdf")
    async def edition_pdf(edition_date: date) -> Response:
        path = Path(app.state.settings.archive_dir) / edition_date.isoformat() / "daily-press.pdf"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="edition not found")
        return Response(
            content=path.read_bytes(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="daily-press-{edition_date.isoformat()}.pdf"'
                )
            },
        )

    @app.post("/editions/generate")
    async def generate_edition(request: GenerateRequest | None = None) -> dict[str, object]:
        try:
            result: GenerationResult = await get_generator().generate(
                request.edition_date if request else None
            )
        except GenerationInProgress as error:
            raise HTTPException(status_code=409, detail="generation already in progress") from error
        except Exception as error:
            raise HTTPException(status_code=500, detail="generation failed") from error
        return result.api_dict()

    return app


app = create_app()
