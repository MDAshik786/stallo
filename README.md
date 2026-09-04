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

Both API and database run on free tiers and sleep after inactivity, so the
first request after an idle period can take up to a minute.

## Architecture

    Browser → Vercel (Next.js 16) → Render (FastAPI, Docker) → Neon (Postgres 18)
                                                     Singapore region

| Layer | |
|---|---|
| Web | Next.js App Router, TypeScript, Tailwind v4, React Query |
| API | FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
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

## Known gaps

- Authentication is an unverified header (see status note above)
- No mutations beyond product creation
- `/orders` and `/analytics` are navigation placeholders
