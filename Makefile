.PHONY: up down restart logs status chaos-errors chaos-latency chaos-cpu chaos-full chaos-reset health incidents analysis

APP_URL     ?= http://localhost:5000
REMEDY_URL  ?= http://localhost:8085
AI_URL      ?= http://localhost:9000

## ── Stack Control ─────────────────────────────────────────────────────────
up:
	docker compose up --build -d
	@echo ""
	@echo "  TechStream AIOps Stack is starting…"
	@echo ""
	@echo "  Grafana       → http://localhost:3000   (admin / techstream)"
	@echo "  Prometheus    → http://localhost:9090"
	@echo "  AlertManager  → http://localhost:9093"
	@echo "  App           → http://localhost:5000"
	@echo "  Remediation   → http://localhost:8080"
	@echo "  AI Analyzer   → http://localhost:9000"
	@echo ""

down:
	docker compose down -v

restart:
	docker compose restart web_app

logs:
	docker compose logs -f --tail=50

logs-app:
	docker compose logs -f web_app

logs-remedy:
	docker compose logs -f remediation

logs-ai:
	docker compose logs -f ai_analyzer

status:
	docker compose ps

## ── Health Checks ─────────────────────────────────────────────────────────
health:
	@echo "--- App Health ---"
	@curl -s $(APP_URL)/health | python3 -m json.tool
	@echo ""
	@echo "--- Remediation Health ---"
	@curl -s $(REMEDY_URL)/health | python3 -m json.tool
	@echo ""
	@echo "--- AI Analyzer Health ---"
	@curl -s $(AI_URL)/health | python3 -m json.tool

## ── Chaos Engineering ─────────────────────────────────────────────────────
chaos-errors:
	@echo "Injecting HTTP 500 errors (80% rate)..."
	@curl -s -X POST $(APP_URL)/chaos/errors/start \
	  -H "Content-Type: application/json" \
	  -d '{"error_rate": 0.8}' | python3 -m json.tool

chaos-latency:
	@echo "Injecting 2s artificial latency..."
	@curl -s -X POST $(APP_URL)/chaos/latency/start \
	  -H "Content-Type: application/json" \
	  -d '{"latency_ms": 2000}' | python3 -m json.tool

chaos-cpu:
	@echo "Starting CPU spike..."
	@curl -s -X POST $(APP_URL)/chaos/cpu/start \
	  -H "Content-Type: application/json" | python3 -m json.tool

chaos-full:
	@echo "Starting full incident (errors + latency + CPU)..."
	@curl -s -X POST $(APP_URL)/chaos/errors/start \
	  -H "Content-Type: application/json" -d '{"error_rate": 0.8}' | python3 -m json.tool
	@curl -s -X POST $(APP_URL)/chaos/latency/start \
	  -H "Content-Type: application/json" -d '{"latency_ms": 1500}' | python3 -m json.tool
	@curl -s -X POST $(APP_URL)/chaos/cpu/start \
	  -H "Content-Type: application/json" | python3 -m json.tool
	@echo "All chaos active. Watch Grafana → Golden Signals dashboard."

chaos-reset:
	@echo "Resetting all chaos..."
	@curl -s -X POST $(APP_URL)/chaos/reset | python3 -m json.tool

chaos-status:
	@curl -s $(APP_URL)/chaos/status | python3 -m json.tool

## ── Monitoring ────────────────────────────────────────────────────────────
incidents:
	@echo "--- Recent Incidents & Remediations ---"
	@curl -s "$(REMEDY_URL)/incidents?limit=20" | python3 -m json.tool

analysis:
	@echo "--- AI Analysis History ---"
	@curl -s "$(AI_URL)/history?limit=5" | python3 -m json.tool

manual-remediate:
	@curl -s -X POST $(REMEDY_URL)/remediate/manual \
	  -H "Content-Type: application/json" \
	  -d '{"alert_name": "ManualTest"}' | python3 -m json.tool

## ── Load Generation ───────────────────────────────────────────────────────
load-test:
	@echo "Generating traffic for 60s at ~5 req/s..."
	@python3 chaos/chaos_script.py traffic --rps 5 --duration 60

## ── Demo Sequence ─────────────────────────────────────────────────────────
demo: up
	@echo ""
	@echo "Waiting 15s for stack to stabilise..."
	@sleep 15
	@echo ""
	@echo "Step 1: Verify baseline health"
	@$(MAKE) health
	@echo ""
	@echo "Step 2: Inject full chaos (60 seconds)"
	@$(MAKE) chaos-full
	@echo ""
	@echo "Step 3: Watch Grafana at http://localhost:3000"
	@echo "        Alerts should fire within ~30s"
	@echo "        Remediation service will auto-reset chaos"
	@sleep 60
	@echo ""
	@echo "Step 4: Check incident log"
	@$(MAKE) incidents
	@echo ""
	@echo "Step 5: Check AI analysis"
	@$(MAKE) analysis
