# Stallo

AI-native commerce platform. Sellers run their store by describing what they
want; shoppers see and control what the store knows about them.

## Live

| | |
|---|---|
| Web | https://stallo-nu.vercel.app |
| API | https://stallo-pnd4.onrender.com |

> **Status: in development.** Authentication is a development stub — the API
> trusts an `X-Seller-Id` header without verifying it, so any caller can claim
> any seller. Seed data only; not suitable for real data until replaced.

> **The assistant only runs locally.** It uses a local model via Ollama, so the
> hosted demo has no model to reach and says so when you try. The storefront,
> catalogue and product form all work there; for the agent, clone and run it
> locally — three commands, below.

Both API and database run on free tiers and sleep after inactivity, so the
first request after an idle period can take up to a minute.

## What it does

A seller types what they want instead of filling a form.

    "add a jasmine garland"
      -> agent pauses: "What price should I set?"
    "₹340"
      -> created as a draft
    "publish it"
      -> agent pauses: "This will publish Jasmine Garland. Approve?"
      [Approve] -> live in the storefront

Clarification and approval are the same mechanism — a tool that suspends the
run. The run is a row in Postgres, not React state, so a pending question
survives a refresh, a closed tab, or tomorrow morning.

`publish` and `delete` are not reachable by the model. They execute only on a
resume carrying the seller's decision, so no amount of typed "yes" authorises
a write.

Every tool call appends to an audit log with its arguments, result, duration,
and inverse. The activity timeline and undo are both reads of that log.

## Agent quality

The agent is regression-tested against a 42-case golden set covering tool
selection, argument accuracy, and safety. Twelve cases are adversarial:
ambiguous pronouns, prompt injection inside a product description, cross-tenant
probes, festival dates, and chit-chat that must call no tool at all.

Measured on `qwen3:8b` running locally via Ollama:

| | Tool selection | Arguments | Safety violations |
|---|---|---|---|
| baseline | 59.5% | 92.0% | 4 |
| longer system prompt | 57.1% | 87.5% | 5 |
| + deterministic guards | 69.0% | 93.1% | 1 |
| + numeric grounding | 71.4% | 93.3% | **0** |

The longer prompt scoring *worse* is why `app/agent/guards.py` exists. An
invariant that must hold is code, not a sentence in a system prompt. Guards
rewrite unsafe model output before anything runs: a resume-only write becomes
an approval request, an unknown id becomes a question, an impossible value
becomes a refusal.

Numeric grounding closed the last gap. Asked to "add a jasmine bouquet", the
model produced a confident price of ₹1500 — structurally perfect arguments for
a number the seller never said. Values that must trace back to the utterance
now do; optional ones the model invents are dropped rather than saved.

    cd evals && STALLO_EVAL_PROVIDER=ollama ../api/.venv/bin/pytest

The suite caches raw model output and applies guards afterwards, so iterating
on policy costs no API calls. `providers.py` supports Ollama, Anthropic, and
Gemini behind one interface; nothing else in the suite knows which ran.

## Architecture

    Browser → Vercel (Next.js 16) → Render (FastAPI, Docker) → Neon (Postgres 18)
                                                     Singapore region

| Layer | |
|---|---|
| Web | Next.js App Router, TypeScript, Tailwind v4, React Query |
| API | FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| Agent | Ollama (local, free) by default; Anthropic and Gemini adapters included |
| Data | Postgres 18, UUIDv7 primary keys generated in application code |

Every product query is scoped to one seller in the repository layer, where
`seller_id` is a constructor argument rather than a method argument — there is
no call site that can forget it.

## Local setup

    cp .env.example .env
    docker compose up -d --wait
    cd api && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
    cd api && .venv/bin/alembic upgrade head
    cd api && .venv/bin/python scripts/seed.py     # prints a SELLER_ID
    cd web && npm install

Put the printed `SELLER_ID` in `web/.env.local`:

    NEXT_PUBLIC_API_URL=http://localhost:8000
    NEXT_PUBLIC_DEV_SELLER_ID=<the uuid seed printed>

## Run

    docker compose up -d --wait                          # postgres + redis
    cd api && .venv/bin/uvicorn app.main:app --reload    # :8000
    cd web && npm run dev                                # :3000

API docs at http://localhost:8000/docs — disabled in production.

## Local ports

This machine runs other Postgres/Redis instances, so Stallo uses non-default
host ports locally. Inside Docker and in production these are standard.

| Service | Host port |
|---|---|
| postgres | 5434 |
| redis | 6380 |
| api | 8000 |
| web | 3000 |

## Deploying

Both halves deploy automatically on push to `main`.

| Service | Platform | Root directory |
|---|---|---|
| Web | Vercel | `web` |
| API | Render (Docker) | `api` |
| Database | Neon | — |

The API container runs `alembic upgrade head` before starting, so migrations
apply on every deploy.

Environment variables are set in each platform's dashboard, never committed.
The API needs `DATABASE_URL` (with the `postgresql+psycopg://` scheme),
`STALLO_ENV`, and `CORS_ORIGINS`. The web app needs `NEXT_PUBLIC_API_URL` and
`NEXT_PUBLIC_DEV_SELLER_ID` — both are compiled into the browser bundle and
are therefore public by design.

## Running the agent locally

The agent needs a local model. Nothing is sent to a paid API.

    brew install ollama && brew services start ollama
    ollama pull qwen3:8b

Then talk to it at http://localhost:3000/agent

## Known gaps

- Authentication is an unverified header (see status note above)
- Variant, image, and analytics tools are declared but not implemented;
  calling one returns a clear "not implemented" rather than failing
- Responses are not streamed — a turn takes a few seconds on local hardware
- `/orders` and `/analytics` are navigation placeholders
