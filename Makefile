SHELL := /bin/sh

.PHONY: setup hooks lint test

setup:
	python -m pip install --upgrade pip
	pip install -e .[dev]
	pre-commit install
	@echo "Pre-commit installed. Run 'pre-commit run -a' to check all files."

hooks:
	pre-commit install
	pre-commit autoupdate || true

lint:
	pre-commit run -a || true

test:
	pytest -q
