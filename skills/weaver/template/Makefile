# =============================================================================
# {{PROJECT_NAME}} — Makefile
# =============================================================================
#
# Common development targets. The deployment agent and PR checks workflows
# reference these targets when available.
#
# =============================================================================

.PHONY: help build test lint fmt up down logs health

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

build: ## Build all services
	docker compose build

# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

test: ## Run all tests
	@echo "Add your test commands here"
	# Example:
	# cd services/api && go test ./... -race
	# cd services/worker && pytest
	# cd services/ui && pnpm test

lint: ## Run linters
	@echo "Add your lint commands here"
	# Example:
	# cd services/api && golangci-lint run
	# cd services/worker && ruff check . && ruff format --check .
	# cd services/ui && pnpm lint

fmt: ## Format code
	@echo "Add your format commands here"
	# Example:
	# cd services/api && gofmt -w .
	# cd services/worker && ruff format .
	# cd services/ui && pnpm format

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

up: ## Start all services
	docker compose up -d

down: ## Stop all services
	docker compose down

logs: ## Tail service logs
	docker compose logs -f --tail=50

health: ## Check service health
	docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

health-check: ## Run pipeline health checks
	python3 -m healthcheck

health-check-heal: ## Run pipeline health checks with self-healing
	python3 -m healthcheck --heal
