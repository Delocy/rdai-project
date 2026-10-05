FROM node:22-alpine AS ui
WORKDIR /ui
# the frontend and API share this container, so the key just has to match API_KEY
ARG VITE_API_KEY
ENV VITE_API_KEY=$VITE_API_KEY
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.22 /uv /usr/local/bin/uv

# create the user first, so files belong to it without a separate chown layer
RUN useradd --create-home --uid 10001 appuser && mkdir /app && chown appuser /app
USER appuser
WORKDIR /app
# PYTHONUNBUFFERED so seeding progress shows in the logs as it runs
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/app/.fastembed_cache \
    PATH="/app/.venv/bin:$PATH"

# install exactly what uv.lock pins; the cache mount keeps uv's cache out of the image
COPY --chown=appuser pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/home/appuser/.cache/uv,uid=10001 \
    uv sync --locked --no-dev --no-install-project

# bake in the ONNX weights so the first request doesn't download them
RUN python -c "from fastembed import ImageEmbedding, TextEmbedding; \
    ImageEmbedding('Qdrant/clip-ViT-B-32-vision'); TextEmbedding('Qdrant/clip-ViT-B-32-text')"

COPY --chown=appuser app ./app
COPY --chown=appuser scripts ./scripts
COPY --chown=appuser --from=ui /ui/dist ./frontend/dist

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
