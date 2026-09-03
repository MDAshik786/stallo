.PHONY: up down api web migrate revision evals fmt

up:        ## start postgres + redis
	docker compose up -d --wait

down:
	docker compose down

api:       ## run the API with reload (needs python 3.12+)
	cd api && .venv/bin/uvicorn app.main:app --reload --port 8000

web:
	cd web && npm run dev

migrate:
	cd api && .venv/bin/alembic upgrade head

revision:  ## make rev m="add x"
	cd api && .venv/bin/alembic revision --autogenerate -m "$(m)"

evals:
	cd evals && ../api/.venv/bin/pytest -q

fmt:
	cd api && .venv/bin/ruff format app && .venv/bin/ruff check --fix app
