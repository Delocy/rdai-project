FROM node:22-alpine AS ui
WORKDIR /ui
# same-origin here (frontend and API share this container's :8000), so this
# just needs to match API_KEY below - docker-compose.yml passes it through
ARG VITE_API_KEY
ENV VITE_API_KEY=$VITE_API_KEY
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.22 /uv /usr/local/bin/uv

# build as the runtime user from the start - a trailing `chown -R` would copy
# the whole venv and the model weights into a second layer
RUN useradd --create-home --uid 10001 appuser && mkdir /app && chown appuser /app
USER appuser
WORKDIR /app
# PYTHONUNBUFFERED so print() output (e.g. first-run seeding progress) reaches
# `docker compose logs` as it happens rather than in one burst afterwards
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/app/.fastembed_cache \
    PATH="/app/.venv/bin:$PATH"

# install exactly what uv.lock pins (--locked fails the build if the lock is
# stale against pyproject.toml); the cache mount keeps uv's cache out of the image
COPY --chown=appuser pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/home/appuser/.cache/uv,uid=10001 \
    uv sync --locked --no-dev --no-install-project

# bake the ONNX weights in so first request is not a cold download
RUN python -c "from fastembed import ImageEmbedding, TextEmbedding; \
    ImageEmbedding('Qdrant/clip-ViT-B-32-vision'); TextEmbedding('Qdrant/clip-ViT-B-32-text')"

COPY --chown=appuser app ./app
COPY --chown=appuser scripts ./scripts
COPY --chown=appuser --from=ui /ui/dist ./frontend/dist

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
