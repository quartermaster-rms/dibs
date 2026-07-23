# dibs — make targets are the tests (IMPLEMENTATION-GUIDE §7).
# CI is a thin wrapper that only invokes these targets.

ifeq ($(OS),Windows_NT)
  PY := .venv/Scripts/python.exe
  VENV_PY := .venv/Scripts/python.exe
else
  PY := .venv/bin/python
  VENV_PY := .venv/bin/python
endif

export PYTHON := $(PY)

.DEFAULT_GOAL := help

.PHONY: help
help:  ## List targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN{FS=":.*?## "}{printf "  %-20s %s\n", $$1, $$2}'

.PHONY: venv
venv:  ## Create the virtualenv
	python -m venv .venv

.PHONY: install
install: venv  ## Install backend (dev) and frontend deps
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"
	cd frontend && npm ci

.PHONY: lint
lint:  ## Lint backend (ruff + mypy) and frontend
	$(PY) -m ruff check src tests
	$(PY) -m ruff format --check src tests
	$(PY) -m mypy src
	cd frontend && npm run lint

.PHONY: fmt
fmt:  ## Auto-format
	$(PY) -m ruff format src tests
	$(PY) -m ruff check --fix src tests

.PHONY: init-db
init-db:  ## Create the schema on $DATABASE_URL (idempotent)
	$(PY) -m dibs.schema

.PHONY: test
test:  ## Run the full test suite (backend + frontend); the binding gate
	bash scripts/run-tests.sh

.PHONY: test-backend
test-backend:  ## Backend tests only
	DIBS_SKIP_FRONTEND=1 bash scripts/run-tests.sh

.PHONY: coverage-security
coverage-security:  ## Enforce 100% branch coverage on security-sensitive paths
	$(PY) scripts/check_security_coverage.py

.PHONY: test-deploy
test-deploy:  ## Verify the production image + deploy flow end to end
	bash scripts/test-deploy.sh

.PHONY: test-deploy-linux
test-deploy-linux:  ## Run test-deploy inside Linux dind (faithful bind-mount perms on non-Linux hosts)
	bash scripts/verify-deploy-linux.sh

.PHONY: build
build:  ## Build all production images
	docker compose -f deploy/docker-compose.yml build

.PHONY: up
up:  ## Bring the stack up (needs deploy/host.env)
	docker compose -f deploy/docker-compose.yml --env-file deploy/host.env up -d

.PHONY: deploy
deploy:  ## Deploy with bounded failed-deploy recovery (needs deploy/host.env)
	bash deploy/deploy.sh

.PHONY: down
down:  ## Tear the stack down
	docker compose -f deploy/docker-compose.yml down

.PHONY: ci
ci: lint test  ## What CI runs (thin wrapper)
