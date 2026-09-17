FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    FASTEMBED_CACHE_PATH=/app/.fastembed_cache \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project

# bake the ONNX weights in so first request is not a cold download
RUN python -c "from fastembed import ImageEmbedding, TextEmbedding; \
    ImageEmbedding('Qdrant/clip-ViT-B-32-vision'); TextEmbedding('Qdrant/clip-ViT-B-32-text')"

COPY app ./app
COPY frontend ./frontend

RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
