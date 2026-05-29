.PHONY: install dev test lint fmt type check migrate revision

PY ?= python3
VENV ?= .venv
BIN := $(VENV)/bin

install:
	$(PY) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e ".[dev]"

dev:
	$(BIN)/uvicorn app.main:app --reload --port 8000

test:
	$(BIN)/pytest

lint:
	$(BIN)/ruff check .

fmt:
	$(BIN)/ruff format .

type:
	$(BIN)/mypy app

check: lint type test

migrate:
	$(BIN)/alembic upgrade head

revision:
	$(BIN)/alembic revision --autogenerate -m "$(m)"
