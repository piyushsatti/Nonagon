DOCKER ?= docker
DOCKER_COMPOSE ?= docker compose
IMAGE ?= nonagon
TAG ?= latest
FULL_IMAGE := $(IMAGE):$(TAG)

.PHONY: help setup hooks lint test check build up down restart logs shell docker-build docker-push docker-release docker-run docker-stop compose-build compose-restart

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | sort | \
	awk 'BEGIN {FS = ":.*##"} {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

setup: ## Install dev dependencies and pre-commit hooks
	python -m pip install --upgrade pip
	pip install -e .[dev]
	pre-commit install

hooks: ## Re-install hooks and update hook versions
	pre-commit install
	pre-commit autoupdate || true

lint: ## Run linters via pre-commit
	pre-commit run -a

test: ## Execute test suite
	pytest -q

check: ## Run lint then test (CI parity)
	$(MAKE) lint
	$(MAKE) test

build: ## Alias for compose build
	$(DOCKER_COMPOSE) build

up: ## Start stack in background (expects services already built as needed)
	$(DOCKER_COMPOSE) up -d

down: ## Stop stack and remove containers
	$(DOCKER_COMPOSE) down

restart: ## Restart stack without triggering a rebuild
	$(DOCKER_COMPOSE) down
	$(DOCKER_COMPOSE) up -d

logs: ## Tail compose service logs
	$(DOCKER_COMPOSE) logs -f --tail=200
