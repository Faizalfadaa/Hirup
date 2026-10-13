# Hirup root Makefile. Run `make help` for the list of targets.
# Recipes use bash (Git Bash on Windows).
SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

COMPOSE := docker compose -f infra/docker-compose.yml
PRISM_VERSION := 5.12.0
MOCK_PORT := 4010

.PHONY: help setup lint format typecheck test api mock

help: ## List available targets
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | sort -u | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

setup: ## Install Python 3.12 deps (uv sync)
	uv sync --locked

lint: ## Ruff lint and format check
	uv run ruff check .
	uv run ruff format --check .

format: ## Apply ruff fixes and formatting
	uv run ruff check --fix .
	uv run ruff format .

typecheck: ## Mypy (strict) on services
	uv run mypy services

test: ## Unit tests (integration tests excluded)
	uv run pytest -q -m "not integration"

api: ## Run the API locally with reload on :8000
	uv run uvicorn services.api.main:app --reload --port 8000

mock: ## Prism mock server from contracts/openapi.yaml on :4010
	@test -f contracts/openapi.yaml || { echo "contracts/openapi.yaml not found (created in T1)"; exit 1; }
	npx --yes @stoplight/prism-cli@$(PRISM_VERSION) mock contracts/openapi.yaml -p $(MOCK_PORT)

# infra/Makefile (P1 infra lane) owns up/down/logs once it exists; these are fallbacks.
ifeq ($(wildcard infra/Makefile),)
.PHONY: up down logs
up: ## Start the Docker stack (OTP, OSRM, API)
	$(COMPOSE) up -d

down: ## Stop the Docker stack
	$(COMPOSE) down

logs: ## Follow Docker stack logs
	$(COMPOSE) logs -f
endif

-include infra/Makefile
