.PHONY: help setup activate deactivate develop examples-deps test perf-test example cli-example fastapi-example strands-shopping-agent docs docs-watch build sdist clean

PYTHON ?= python
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
MATURIN := $(VENV)/bin/maturin
BUILD_ARGS ?= --out dist
SDIST_ARGS ?= --out dist

help:
	@echo "Targets:"
	@echo "  make setup    Create .venv and install dev tools"
	@echo "  make activate  Print the command to activate .venv"
	@echo "  make deactivate  Print the command to deactivate .venv"
	@echo "  make develop  Build/install PyO3 extension in editable mode"
	@echo "  make examples-deps  Install dependencies used by examples"
	@echo "  make test     Run tests"
	@echo "  make perf-test  Run opt-in native-vs-Python performance test"
	@echo "  make example  Run the API example"
	@echo "  make cli-example  Run the dogwood-py CLI example"
	@echo "  make fastapi-example  Run the native-backed FastAPI example"
	@echo "  make strands-shopping-agent  Run the Strands shopping agent example"
	@echo "  make docs     Build Sphinx HTML documentation"
	@echo "  make docs-watch  Rebuild and serve docs while files change"
	@echo "  make build    Build wheel"
	@echo "  make sdist    Build source distribution"
	@echo "  make clean    Remove generated caches and Rust build output"

setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install -U pip
	$(VENV_PYTHON) -m pip install -e '.[dev]'

activate:
	@echo "Run: source $(VENV)/bin/activate"

deactivate:
	@echo "Run: deactivate"

develop: setup
	$(MATURIN) develop

examples-deps: setup
	$(VENV_PYTHON) -m pip install fastapi 'uvicorn[standard]' httpx2

test:
	$(VENV_PYTHON) -m pytest -q

perf-test:
	DOGWOOD_PERF_TESTS=1 $(VENV_PYTHON) -m pytest -q tests/test_performance.py -s

example:
	$(VENV_PYTHON) examples/api_usage.py

cli-example:
	$(VENV)/bin/dogwood-py replay examples/cli/policy.dw --policy-schema examples/cli/schema.cedarschema --trace examples/cli/trace.log

fastapi-example:
	$(VENV_PYTHON) -m uvicorn examples.fastapi_simple.app:app --reload --host 127.0.0.1 --port 8000

strands-shopping-agent:
	PYTHONPATH=src $(VENV_PYTHON) -m examples.strands_shopping_agent.agent $(or $(ARGS),--user alice)

docs:
	$(VENV_PYTHON) -m sphinx -b html docs/source docs/build/html

docs-watch:
	$(VENV_PYTHON) -m sphinx_autobuild docs/source docs/build/html --host 127.0.0.1 --port 8001

build:
	$(MATURIN) build $(BUILD_ARGS)

sdist:
	$(MATURIN) sdist $(SDIST_ARGS)

clean:
	rm -rf .pytest_cache
	rm -rf src/dogwood/__pycache__ tests/__pycache__
	rm -f src/dogwood/_version.py
	rm -rf rust/target
	rm -rf docs/build docs/source/generated
	rm -rf build dist *.egg-info
