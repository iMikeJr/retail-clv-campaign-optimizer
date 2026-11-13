# Convenience targets. Run `make help` for a summary.
# Unit tests use local virtual environments (see `make venv`); Docker targets
# read credentials from .env (copy .env.example first).

PYTHON     ?= .venv/bin/python
API_PYTHON ?= .venv-api/bin/python
COMPOSE    ?= docker compose

.PHONY: help up down etl model venv test test-etl test-model test-api lint

help:
	@echo "up        Build and start all services in the background"
	@echo "down      Stop services (keeps the database volume)"
	@echo "etl       Re-run the ETL job once"
	@echo "model     Re-run the model batch once (ETL must have completed)"
	@echo "venv      Create local virtual environments for the unit tests (needs uv)"
	@echo "test      Run ETL, model and API unit tests locally"
	@echo "lint      Validate the Compose file and byte-compile all Python sources"

up:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

etl:
	$(COMPOSE) run --rm etl

model:
	$(COMPOSE) run --rm --no-deps model

venv:
	uv venv --python 3.12 .venv
	uv pip install --python .venv/bin/python -r services/etl/requirements-dev.txt -r services/model/requirements-dev.txt
	uv venv --python 3.12 .venv-api
	uv pip install --python .venv-api/bin/python -r services/api/requirements-dev.txt

test: test-etl test-model test-api

test-etl:
	$(PYTHON) -m pytest services/etl/tests -q

test-model:
	$(PYTHON) -m pytest services/model/tests -q

test-api:
	$(API_PYTHON) -m pytest services/api/tests -q

lint:
	$(COMPOSE) --env-file .env.example config -q
	$(PYTHON) -m compileall -q services
