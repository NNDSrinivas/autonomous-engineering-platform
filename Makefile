.PHONY: dev up down migrate rev lint test

up:
	docker compose up -d

down:
	docker compose down -v

dev: up
	uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload & \
	uvicorn backend.api.realtime:app --host 0.0.0.0 --port 8001 --reload

migrate:
	alembic upgrade head

rev:
	alembic revision -m "update" --autogenerate

seed-policy:
	docker exec -i aep_postgres psql -U mentor -d mentor < scripts/seed_policy.sql

lint:
	python -m pip install ruff black || true
	ruff check .
	black --check .

test:
	pytest -q
