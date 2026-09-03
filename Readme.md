# Stallo

AI-native commerce platform. Sellers run their store by describing what
they want; shoppers see and control what the store knows about them.

## Local setup

    cp .env.example .env
    docker compose up -d --wait
    cd api && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
    cd web && npm install

## Run

    docker compose up -d --wait                              # postgres + redis
    cd api && .venv/bin/uvicorn app.main:app --reload         # :8000
    cd web && npm run dev                                     # :3000

## Local ports

This machine runs other Postgres/Redis instances, so Stallo uses non-default
host ports. Inside Docker and in production these are the standard ports.

| Service  | Host port |
|----------|-----------|
| postgres | 5434      |
| redis    | 6380      |
| api      | 8000      |
| web      | 3000      |