# Run from the repository root, including in Git Bash on Windows.
SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c

.PHONY: infra-help data-routing graphs up down smoke infra-config infra-check infra-logs logs
.PHONY: active-graph active-benchmark
.PHONY: backend-api golden-od
BACKEND_HOST_PORT ?= 8002

infra-help:
	@echo "data-routing  Download OSM/GTFS and clip OSM to the buffered pilot"
	@echo "graphs        Build car, motorcycle, and OTP graphs sequentially"
	@echo "up / down     Start healthy routing services / stop the stack"
	@echo "smoke         Print Lebak Bulus to Bundaran HI durations"
	@echo "infra-config  Validate Docker Compose configuration"
	@echo "infra-check   Run lint, type checks, and small local tests"
	@echo "infra-logs    Show recent routing service logs"
	@echo "active-graph  Build the walk/bike graph once from pilot OSM"
	@echo "active-benchmark  Run latency benchmark with explicit synthetic AQ arguments"
	@echo "backend-api   Run the T5 backend locally on :8002 without access logs"
	@echo "golden-od     Run the 30-OD HTTP-to-dose checks with explicit demo arguments"

data-routing:
	bash "infra/scripts/fetch_osm.sh"
	bash "infra/scripts/fetch_gtfs.sh"

graphs:
	bash "infra/scripts/build_graphs.sh"

up:
	bash "infra/scripts/stack.sh" up

down:
	bash "infra/scripts/stack.sh" down

smoke:
	bash "infra/scripts/smoke.sh"

infra-config:
	bash "infra/scripts/stack.sh" config

infra-check:
	uv run --project infra ruff check infra/scripts tests/infra
	uv run --project infra ruff format --check infra/scripts tests/infra
	uv run --project infra mypy --config-file infra/pyproject.toml infra/scripts tests/infra
	uv run --project infra python -m pytest -c infra/pyproject.toml -q tests/infra
	@for script in infra/scripts/*.sh; do bash -n "$$script"; done

infra-logs:
	bash "infra/scripts/stack.sh" logs

logs: infra-logs

active-graph:
	bash "infra/scripts/build_active_graph.sh"

active-benchmark:
	uv run python -m services.routing.benchmark_active $(BENCHMARK_ARGS)

backend-api: ## Run the backend locally on :8002 without access logs
	uv run uvicorn services.api.main:app --host 127.0.0.1 --port $(BACKEND_HOST_PORT) --no-access-log

golden-od: ## Check 30 OD requests with explicit synthetic AQ arguments
	uv run python tests/integration/golden_runner.py $(GOLDEN_ARGS)
