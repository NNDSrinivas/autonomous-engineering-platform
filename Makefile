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

redis-test:
	REDIS_URL=redis://localhost:6379/0 pytest -q tests/test_broadcast_redis.py

e2e-smoke:
	python3 scripts/smoke_navi_v2_e2e.py --runs 1

e2e-gate:
	python3 scripts/smoke_navi_v2_e2e.py --runs 20

# Real LLM E2E validation (production readiness)
e2e-validation-quick:
	python3 scripts/e2e_real_llm_validation.py --suite quick --report-md --report-html

e2e-validation-medium:
	python3 scripts/e2e_real_llm_validation.py --suite medium --report-md --report-html

e2e-validation-full:
	python3 scripts/e2e_real_llm_validation.py --suite full --report-md --report-html --max-concurrent 3

e2e-validation-benchmark:
	python3 scripts/e2e_real_llm_validation.py --suite full --count 100 --report-md --report-html --max-concurrent 3

# Grafana dashboard management
grafana-import:
	./scripts/import_dashboards.sh

grafana-open:
	@open http://localhost:3001/d/navi-llm/navi-llm-performance-metrics || echo "Visit: http://localhost:3001"

grafana-status:
	@docker ps | grep grafana && echo "✅ Grafana is running at http://localhost:3001" || echo "❌ Grafana is not running"

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

audit-purge:
	python3 backend/scripts/purge_audit_logs.py
