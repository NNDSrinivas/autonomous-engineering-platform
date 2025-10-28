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

test:
	pytest -q

# PR-17: Memory Graph & Temporal Reasoning
CORE ?= http://localhost:8000

pr17-seed:
	python scripts/seed_graph_fixture.py data/seed/pr17_fixture.json

pr17-smoke:
	bash scripts/smoke_pr17.sh

graph-rebuild:
	curl -s -X POST "$(CORE)/api/memory/graph/rebuild" \
	  -H "Content-Type: application/json" \
	  -H "X-Org-Id: default" \
	  -d '{"org_id":"default","since":"30d"}' | jq .

pr17-test:
	pytest tests/test_graph_edges_accuracy.py tests/test_timeline_order.py tests/test_explain_paths.py tests/test_rbac_isolation.py -v

pr17-all: pr17-seed pr17-smoke pr17-test
	@echo "✅ PR-17 full validation complete"

# PR-18: Memory Graph UI
ui-dev:
	cd frontend && npm run dev

ui-build:
	cd frontend && npm run build

ui-preview:
	cd frontend && npm run preview

ui-test:
	@echo "Testing Memory Graph UI..."
	@cd frontend && npm run build > /dev/null 2>&1 && echo "✅ UI build successful" || (echo "❌ UI build failed" && exit 1)

pr18-dev: dev ui-dev

pr18-all: ui-test
	@echo "✅ PR-18 UI validation complete"

# PR-19: Live Plan Mode + Real-Time Collaboration
pr19-dev:
	uvicorn backend.api.main:app --reload --port 8000

pr19-migrate:
	alembic upgrade head

pr19-test:
	pytest tests/test_plan_api.py -v

pr19-smoke:
	@bash scripts/pr19_smoke_test.sh

ui-plan-dev:
	cd frontend && npm run dev

pr19-all: pr19-migrate pr19-test pr19-smoke
	@echo "✅ PR-19 full validation complete"
