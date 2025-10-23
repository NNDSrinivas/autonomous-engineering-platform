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

web-dev:
	cd web && npm install && npm run dev

reindex:
	curl -s -X POST "http://localhost:8002/api/search/reindex/jira" -H 'X-Org-Id: default' | jq .
	curl -s -X POST "http://localhost:8002/api/search/reindex/meetings" -H 'X-Org-Id: default' | jq .
	curl -s -X POST "http://localhost:8002/api/search/reindex/code" -H 'X-Org-Id: default' | jq .

reindex-ext:
	curl -s -X POST "http://localhost:8002/api/search/reindex/slack" -H 'X-Org-Id: default' | jq .
	curl -s -X POST "http://localhost:8002/api/search/reindex/confluence" -H 'X-Org-Id: default' -H 'content-type: application/json' -d '{"space_key":"ENG"}' | jq .
	curl -s -X POST "http://localhost:8002/api/search/reindex/wiki" -H 'X-Org-Id: default' | jq .
	curl -s -X POST "http://localhost:8002/api/search/reindex/zoom_teams" -H 'X-Org-Id: default' | jq .

lint:
	python -m pip install ruff black || true
	ruff check .
	black --check .

test:
	pytest -q
