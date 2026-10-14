# Run from the repository root, including in Git Bash on Windows.
SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c

.PHONY: infra-help data-routing graphs up down smoke infra-config infra-check infra-logs logs
.PHONY: active-graph active-benchmark
.PHONY: backend-api golden-od contract-http
.PHONY: ci-config ci-up ci-test ci-down
.PHONY: deploy-image deploy-test-image deploy-config deploy-monitor deploy-release deploy-rollback
.PHONY: deploy-local-test
DEPLOY_API_IMAGE ?= hirup-api:local-review
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
	@echo "contract-http  Check live localhost HTTP against the frozen API contract"
	@echo "ci-config / ci-up / ci-test / ci-down  Validate, start, test and clean an isolated CI stack"
	@echo "deploy-image / deploy-test-image  Build production or fixture-only API image"
	@echo "deploy-config / deploy-monitor / deploy-release / deploy-rollback  VM operations (see runbook)"

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
	uv run --project infra ruff check infra/scripts infra/ci infra/deploy tests/infra
	uv run --project infra ruff format --check infra/scripts infra/ci infra/deploy tests/infra
	uv run --project infra mypy --config-file infra/pyproject.toml infra/scripts infra/ci infra/deploy tests/infra
	uv run --project infra python -m pytest -c infra/pyproject.toml -q tests/infra
	@for script in infra/scripts/*.sh infra/ci/*.sh infra/deploy/*.sh; do bash -n "$$script"; done

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

contract-http: ## Check live HTTP status, media types, headers and schemas
	uv run python -m tests.contract.runner $(CONTRACT_ARGS)

ci-config:
	bash infra/ci/stack.sh config

ci-up:
	bash infra/ci/stack.sh up

ci-test:
	uv run python -m infra.ci.check

ci-down:
	bash infra/ci/stack.sh down

deploy-image:
	docker build --target api -f infra/deploy/API.Dockerfile -t "$(DEPLOY_API_IMAGE)" .

deploy-test-image:
	docker build --target integration -f infra/deploy/API.Dockerfile -t "$(DEPLOY_API_IMAGE)" .

deploy-config:
	python3 infra/deploy/ops.py config $(DEPLOY_ARGS)

deploy-monitor:
	python3 infra/deploy/ops.py monitor $(DEPLOY_ARGS)

deploy-release:
	python3 infra/deploy/ops.py release $(DEPLOY_ARGS)

deploy-rollback:
	python3 infra/deploy/ops.py rollback $(DEPLOY_ARGS)

deploy-local-test:
	uv run python -m tests.integration.deploy_runner
