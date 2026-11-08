ROOT := $(CURDIR)
PY := $(ROOT)/backend/.venv/bin/python

.PHONY: install dev migrate test lint format check schema schema-check audit verify

install:
	python3 -m venv backend/.venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r backend/requirements-dev.txt

dev:
	cd backend && $(PY) manage.py runserver

migrate:
	cd backend && $(PY) manage.py migrate

test:
	cd backend && $(PY) -m pytest --cov=apps --cov-report=term-missing --cov-fail-under=85

lint:
	cd backend && $(PY) -m ruff check . && $(PY) -m ruff format --check .

format:
	cd backend && $(PY) -m ruff format .

check:
	cd backend && $(PY) manage.py check
	cd backend && $(PY) manage.py makemigrations --check --dry-run

schema:
	cd backend && $(PY) manage.py spectacular --file $(ROOT)/contracts/openapi.yaml --validate

schema-check:
	cd backend && $(PY) manage.py spectacular --file /tmp/alliance-openapi.yaml --validate
	diff -u $(ROOT)/contracts/openapi.yaml /tmp/alliance-openapi.yaml

audit:
	cd backend && $(PY) manage.py audit_ledger

verify: lint check schema-check test
	@echo "verify passed"
