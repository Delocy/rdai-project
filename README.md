# Visual Product Search

Multimodal agentic RAG over a product catalogue. You give it an image, a description, or both
("like this but cheaper, in blue") and an agent loop retrieves, checks its own results against
your constraints, repairs the query when they fall short, and explains what it picked.

![architecture](docs/architecture.svg)

## How it works

1. **Parse** — an LLM turns the request into structured constraints (category, colour, budget).
2. **Retrieve** — CLIP embedding, vector kNN in Qdrant with price/category filters applied server side.
3. **Check** — price, category and colour matched against indexed metadata. No LLM, no embedding call.
4. **Repair** — if too few survive, rewrite the query and retry (max 3 passes). Dropping the colour
   filter moves the colour into the embedding probe instead, so it stays a soft preference rather
   than disappearing; the price ceiling widens; the category is dropped last.
5. **Justify** — a vision LLM ranks the survivors and writes one line per item.

Only steps 1 and 5 call an LLM. Everything else is embedding maths and metadata filtering, which
keeps the whole thing inside free-tier rate limits.

Colour checking started out as CLIP zero-shot classification. Measured on this catalogue it was
42% accurate, and an absolute cosine threshold separated blue from non-blue items barely at all
(0.175–0.227 against 0.162–0.219), because product shots on white backgrounds compress CLIP
similarity into a narrow band. The catalogue already carries colour as metadata, so that is what
the check uses. CLIP is left to do what it is good at: ranking overall visual similarity.

Embeddings run locally as ONNX (CLIP ViT-B/32 via fastembed) and are baked into the image, so no
embedding API is involved. Only the two LLM calls leave the machine.

## Running it

Requires Docker and an OpenRouter API key (free — https://openrouter.ai/keys).

```bash
cp .env.example .env      # add your key, change API_KEY
docker compose up --build
```

Then open http://localhost:8000.

The free model IDs in `.env.example` go stale as OpenRouter rotates them. List current ones with:

```bash
curl -s https://openrouter.ai/api/v1/models | jq -r '.data[] | select(.pricing.prompt=="0") | .id'
```

`TEXT_MODELS` and `VISION_MODELS` both take a comma-separated list and are tried in order.

**The free tier allows 50 requests per day.** At two LLM calls per search that is about 25 searches,
which is enough to try it out but not to develop against. Adding 10 credits to an OpenRouter account
raises it to 1000/day.

When every remote model fails the service falls back to a local Ollama model if one is configured,
and failing that returns vector search results with `degraded: true` and an explanation in the trace
rather than an error. To use the fallback, run Ollama on the host and set `OLLAMA_TEXT_MODEL` and
`OLLAMA_VISION_MODEL`:

```bash
ollama pull llama3.2:3b
ollama pull qwen2.5vl:7b
```

## Loading a catalogue

Pull a sample catalogue (fashion products from Hugging Face, no account needed) and index it:

```bash
docker compose exec api python -m scripts.fetch_catalogue --limit 300
docker compose exec api python -m scripts.ingest data/catalogue.csv --images data/images
```

The source dataset has no prices, so `fetch_catalogue.py` invents them per article type. They are
deterministic for a given item but they are not real.

For your own data, point `ingest.py` at a CSV with `title,price,image,category,colour` and an image
folder. Single items can go in via `POST /ingest`.

## Endpoints

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/search` | `query` and/or `image`, returns ranked results + agent trace |
| POST | `/ingest` | single item, multipart |
| GET | `/health` | liveness |

`/search` and `/ingest` require an `X-API-Key` header matching `API_KEY`.

## Security notes

- API key compared with `secrets.compare_digest`, never logged
- uploads restricted to jpeg/png/webp and capped at 5 MB, enforced while reading rather than trusting `Content-Length`
- container runs as a non-root user
- `.env` is gitignored; `.env.example` carries no real secrets
- frontend renders catalogue text through React, which escapes it, so catalogue text cannot inject markup

## Development

### Backend

```bash
uv sync
uv run pytest
uv run uvicorn app.main:app --reload
```

Local runs need Qdrant reachable — `docker compose up qdrant` and set `QDRANT_URL=http://localhost:6333`.

### Frontend

React + Vite, in `frontend/`. Requires Node 22.

```bash
cd frontend
npm ci
npm run dev
```

That serves the UI on http://localhost:5173 with hot reload, proxying `/search`, `/ingest` and
`/images` to the backend on port 8000 (see `vite.config.js`), so run uvicorn alongside it.

`npm run build` emits `frontend/dist`, which `app/main.py` mounts at `/` when it exists. The Docker
image builds it in a separate stage, so `docker compose up --build` serves the built UI from port
8000 and needs no Node on the host.

Dependencies are pinned in `package-lock.json` — use `npm ci`, and commit the lockfile alongside
any `package.json` change.
