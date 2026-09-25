FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY daily_press ./daily_press
COPY static ./static
COPY templates ./templates
COPY config ./config
RUN uv sync --frozen --no-dev \
    && /app/.venv/bin/playwright install --with-deps chromium

RUN groupadd --system --gid 10001 daily-press \
    && useradd --system --uid 10001 --gid 10001 --home-dir /app --no-create-home daily-press \
    && mkdir -p /app/data \
    && chown -R daily-press:daily-press /app \
    && chmod -R a+rX /ms-playwright

USER daily-press

EXPOSE 8080
CMD ["uvicorn", "daily_press.main:app", "--host", "0.0.0.0", "--port", "8080"]
