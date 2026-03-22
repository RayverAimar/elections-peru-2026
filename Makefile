.PHONY: setup dev dev-frontend db-up db-down migrate build clean help
.PHONY: fetch-candidates collect-content extract-positions pipeline

# ── Setup ──────────────────────────────────────────────────
setup: ## Full setup from scratch
	docker compose up -d
	uv sync
	uv run pre-commit install
	@echo "Waiting for PostgreSQL..."
	@sleep 3
	uv run python scripts/migrate.py
	cd web && npm install && npm run build
	@echo "\n✓ Setup complete. Run 'make dev' to start."

# ── Development ────────────────────────────────────────────
dev: ## Start API server (hot-reload)
	uv run uvicorn main:app --reload

dev-frontend: ## Start frontend dev server
	cd web && npm run dev

# ── Database ───────────────────────────────────────────────
db-up: ## Start PostgreSQL
	docker compose up -d

db-down: ## Stop PostgreSQL
	docker compose down

migrate: ## Run pending database migrations
	uv run python scripts/migrate.py

# ── Data Pipeline ──────────────────────────────────────────
# SCOPE controls what data to fetch/collect:
#   presidential (default) — 36 presidential candidates only
#   formula               — full presidential formula (108 candidates)
#   all                   — all elections (senate, house, andean)
SCOPE ?= presidential

fetch-candidates: ## Fetch candidates from JNE API (SCOPE=presidential|all)
ifeq ($(SCOPE),all)
	uv run python scripts/collect_candidates.py --all
else
	uv run python scripts/collect_candidates.py
endif

collect-content: ## Fetch plans + news + events (SCOPE=presidential|formula)
	uv run python scripts/collect_planes.py
ifeq ($(SCOPE),formula)
	uv run python scripts/collect_news.py --formula --workers 0
else
	uv run python scripts/collect_news.py --workers 0
endif
	uv run python scripts/collect_events.py

extract-positions: ## Extract candidate positions with LLM (costs API credits)
	uv run python scripts/extract_positions.py

pipeline: ## Run full data pipeline (SCOPE=presidential|formula|all)
	@echo "═══ Step 1/3: Fetching candidates ($(SCOPE)) ═══"
	$(MAKE) fetch-candidates SCOPE=$(SCOPE)
	@echo "\n═══ Step 2/3: Collecting content ($(SCOPE)) ═══"
	$(MAKE) collect-content SCOPE=$(SCOPE)
	@echo "\n═══ Step 3/3: Extracting positions ═══"
	$(MAKE) extract-positions
	@echo "\n✓ Pipeline complete."

# ── Frontend ───────────────────────────────────────────────
build: ## Build frontend static site
	cd web && npm run build

# ── Utilities ──────────────────────────────────────────────
clean: ## Remove build artifacts
	rm -rf web/dist web/.astro __pycache__ .ruff_cache

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
