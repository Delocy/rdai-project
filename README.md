# Visual Product Search

Multimodal product search over a small fashion catalogue, served by FastAPI in Docker. Give it a
photo, a description or both ("like this but cheaper, in grey") and an agent loop retrieves
candidates, checks them against the request, repairs the query when they fall short and marks
anything that doesn't fully match.

The model is CLIP ViT-B/32 (public weights, ONNX via fastembed), baked into the image and run on
CPU, with Qdrant as the vector database. `POST /embed` serves it directly; `/search` runs the agent
on top. No API keys are needed. An LLM is optional and only re-ranks results by looking at the
photos.

![search results for "red running shoes under 40", showing the agent's trace, what it relaxed and the marked misses](docs/screenshot.png)

![architecture](docs/architecture.svg)

## Running it

Needs Docker with Compose v2, and ports 8000 and 6333 free.

```bash
git clone https://github.com/Delocy/rdai-project.git
cd rdai-project
cp .env.example .env      # works as is; change API_KEY if you like
docker compose up --build
```

Open http://localhost:8000 once the log shows `Application startup complete`. The first run takes
longer: the build bakes in the CLIP weights, and the API indexes the 300 sample products before it
starts serving (20 seconds to a couple of minutes; the log counts them), and `docker compose ps`
then shows the api as healthy. The API docs are at http://localhost:8000/docs.
`docker compose down` stops it, and `docker compose down -v` also wipes the index.

## How it works

1. **Read** - rules pull out a budget ("under 40"), a colour and a category, using the catalogue's
   own labels plus a few everyday words (sneakers, tee). `LLM_PARSE=true` hands this to an LLM.
2. **Retrieve** - CLIP embeds the text and/or photo; Qdrant returns the 24 nearest products within
   budget.
3. **Check** - category and colour against each product's metadata, word by word ("Shirts" isn't
   "Tshirts").
4. **Repair** - with fewer than five survivors, relax and retry, at most 3 passes: colour becomes a
   soft preference, then the budget widens 25%, and the category goes last. What was relaxed is
   reported, and misses are marked ("over budget by 4.50", "Black, not Red").
5. **Rank** - by visual similarity, or, with a vision model configured, by the model looking at a
   numbered contact sheet of the shortlist's photos and dropping what doesn't fit.

The UI streams each step as it happens. If nothing in the catalogue fits, it says so rather than
passing off the nearest photos as matches.

Colour checking started out as CLIP zero-shot classification. Measured on this catalogue it was
42% accurate, and an absolute cosine threshold separated blue from non-blue items barely at all
(0.175–0.227 against 0.162–0.219), because product shots on white backgrounds compress CLIP
similarity into a narrow band. The catalogue already carries colour as metadata, so that is what
the check uses. CLIP is left to do what it is good at: ranking overall visual similarity.

## Evaluation

`scripts/evaluate.py` runs 50 hand-labelled queries (`scripts/eval_cases.json`): 41 with at least
one matching product and 9 with none ("sunglasses under 50" - every pair costs more). Five search
by photo, and ten are rephrasings the rules weren't written against ("sunnies", "smart office
shoes").

| | precision@5 | recall@5 | impossible requests handled | correctly labelled | median time |
| --- | --- | --- | --- | --- | --- |
| CLIP nearest neighbours alone | 45% | 63% | 0% | 37% | 0.15s |
| check & repair, given the right constraints | 62% | 84% | 100% | 100% | 0.15s |
| rules (the default, no LLM) | 62% | 83% | 100% | 96% | 0.12s |
| LLM parsing (qwen2.5:7b on Ollama) | 57% | 75% | 100% | 96% | 15.3s |

Recall counts matching products (up to five) that made the shortlist; a request is handled when
nothing is passed off as a match, and a result is correctly labelled when it's marked as a miss
exactly when it is one.

CLIP alone always returns five photos, so it never admits a request can't be met - the loop is
what fixes that. The rules come within a point of being handed the correct constraints. A local 7B
model read one more query right (89% against 87%) but did worse overall at 15 seconds a search,
hence rules by default. Recall stops at 84% even with perfect constraints because only the 24
nearest neighbours get checked; filtering on category and colour inside Qdrant would fix that.

Vision ranking isn't scored: locally it took minutes a search on a 16 GB laptop, and on
OpenRouter's free tier it would need about twice the daily limit. In spot checks it judges the photos,
sometimes harder than asked - it dropped a checked navy shirt from "navy blue shirt".

Run it with `docker compose exec api python -m scripts.evaluate` (`--no-llm` or `--no-vision` skip
the model rows).

## Optional LLM

Not needed to run anything. A configured vision model adds one call per search to re-rank;
`LLM_PARSE=true` adds a second to read the request.

- OpenRouter: set `OPENROUTER_API_KEY` (free at https://openrouter.ai/keys, 50 requests a day).
  Free model IDs come and go; list the current ones with
  `curl -s https://openrouter.ai/api/v1/models | jq -r '.data[] | select(.pricing.prompt=="0") | .id'`.
- Ollama: no key or limit, but slow. `ollama pull qwen2.5vl:7b` (and `qwen2.5:7b` for parsing),
  then set `OLLAMA_VISION_MODEL` / `OLLAMA_TEXT_MODEL`.

Models that come back missing, rate-limited or unreachable are skipped for five minutes, and if
they all fail the search finishes with rules and similarity.

## Catalogue

The 300-item sample (real fashion product photos, invented prices) is committed under `data/` and
indexes itself on first start. It's a demo catalogue, not real inventory - the point is watching
the agent work, not buying anything. Product IDs come from the image file names, so re-indexing
overwrites instead of duplicating.

To pull a different sample from the source (fashion products on Hugging Face, no account needed)
and re-index it:

```bash
docker compose exec api python -m scripts.fetch_catalogue --limit 300
docker compose exec api python -m scripts.ingest data/catalogue.csv --images data/images
```

The source dataset has no prices, so `fetch_catalogue.py` invents them per article type. They are
deterministic for a given item but they are not real.

For your own data, point `ingest.py` at a CSV with `title,price,image,category,colour` and an image
folder. There's no write endpoint over HTTP, so the catalogue only changes from inside the container.

## Endpoints

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/search` | `query` and/or `image`; streams each agent step, then the results |
| POST | `/embed` | the model on its own: CLIP vectors for `text` and/or `image`, and their similarity |
| GET | `/health` | liveness |
| GET | `/ready` | readiness: Qdrant answers, the catalogue is indexed, the models are loaded |

`/search` and `/embed` need an `X-API-Key` header matching `API_KEY`, and each client gets 30 of
them a minute (`RATE_LIMIT_PER_MINUTE`).

## Security notes

- API keys compared with `secrets.compare_digest`, never logged
- the Docker build bakes `API_KEY` into the frontend as `VITE_API_KEY`, so anyone who loads the
  page has it. That's acceptable because the HTTP API is read-only: it searches and embeds, and
  nothing over HTTP can change the catalogue
- request bodies over 5 MB are turned away before they're read - Starlette would otherwise take
  in a whole upload before the endpoint's own size check. Uploads must also decode as
  JPEG/PNG/WebP whatever their `Content-Type`, and images over 25 megapixels are refused
- `/search` and `/embed` are rate limited per client, since each runs the model on the CPU. Behind
  Docker's port mapping every local request comes from one address, so locally the limit is shared
- errors stay in the server log; clients get a generic message, not internal hostnames or paths
- the api container runs as a non-root user on a read-only filesystem (only `/tmp` and `data/`
  are writable), with all Linux capabilities dropped, `no-new-privileges`, and memory and process
  limits
- both ports are published on `127.0.0.1` only, so other machines on the network can't reach the
  app or Qdrant (which has no auth)
- dependencies install from the lockfiles, and uv and Qdrant are pinned
- `.env` is gitignored; `.env.example` carries no real secrets
- frontend renders catalogue text through React, which escapes it, so catalogue text cannot inject markup

## Development

### Backend

```bash
uv sync
uv run pytest
uv run uvicorn app.main:app --reload
```

Local runs need Qdrant reachable - `docker compose up qdrant` and set `QDRANT_URL=http://localhost:6333`.

### Frontend

React + Vite, in `frontend/`. Requires Node 22.

```bash
cd frontend
npm ci
npm run dev
```

That serves the UI on http://localhost:5173 with hot reload, proxying `/search` and `/images`
to the backend on port 8000 (see `vite.config.js`), so run uvicorn alongside it. `npm test` runs
the wording tests, which pin every sentence the UI builds from a search.

`npm run build` emits `frontend/dist`, which `app/main.py` mounts at `/` when it exists. The Docker
image builds it in a separate stage, so `docker compose up --build` serves the built UI from port
8000 and needs no Node on the host.

Dependencies are pinned in `package-lock.json` - use `npm ci`, and commit the lockfile alongside
any `package.json` change.
