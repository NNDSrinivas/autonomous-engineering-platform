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
	curl -s -X POST "http://localhost:8002/api/search/reindex/confluence" -H 'X-Org-Id: default' -H 'Content-Type: application/json' -d '{"space_key":"ENG"}' | jq .
	curl -s -X POST "http://localhost:8002/api/search/reindex/wiki" -H 'X-Org-Id: default' | jq .
	curl -s -X POST "http://localhost:8002/api/search/reindex/zoom_teams" -H 'X-Org-Id: default' | jq .

context-smoke:
	curl -s -X POST "http://localhost:8000/api/context/pack" -H 'Content-Type: application/json' -d '{"query":"authentication bug","k":5,"sources":["github","jira"]}' | jq .

mem-event:
	curl -s -X POST "http://localhost:8000/api/memory/event" -H 'Content-Type: application/json' -d '{"session_id":"sess_123","event_type":"decision","task_key":"ENG-42","context":"Decided to use FastAPI for async endpoints"}' | jq .

mem-consolidate:
	curl -s -X POST "http://localhost:8000/api/memory/consolidate" -H 'Content-Type: application/json' -d '{"session_id":"sess_123","task_key":"ENG-42","summary":"Implemented async API with FastAPI","importance":7,"tags":["api","fastapi","async"]}' | jq .

lint:
	python -m pip install ruff black || true
	ruff check .
	black --check .

# Frontend configuration generation
frontend-config:
	python scripts/generate_frontend_config.py

config: frontend-config

test:
	pytest -q

# Memory graph utilities
CORE ?= http://localhost:8000

graph-rebuild:
	curl -s -X POST "$(CORE)/api/memory/graph/rebuild" \
	  -H "Content-Type: application/json" \
	  -H "X-Org-Id: default" \
	  -d '{"org_id":"default","since":"30d"}' | jq .

# Frontend UI
ui-dev:
	cd frontend && npm run dev

ui-build:
	cd frontend && npm run build

ui-preview:
	cd frontend && npm run preview

ui-test:
	@echo "Testing Memory Graph UI..."
	@cd frontend && npm run build > /dev/null 2>&1 && echo "✅ UI build successful" || (echo "❌ UI build failed" && exit 1)
