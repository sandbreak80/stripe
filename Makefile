.PHONY: help build up down logs lint typecheck test clean migrate shell

help:
	@echo "Available targets:"
	@echo "  build       - Build Docker images"
	@echo "  up          - Start all services"
	@echo "  down        - Stop all services"
	@echo "  logs        - Show service logs"
	@echo "  lint        - Run ruff linter"
	@echo "  typecheck   - Run mypy type checker"
	@echo "  test        - Run pytest tests"
	@echo "  migrate     - Run database migrations"
	@echo "  shell       - Open shell in app container"
	@echo "  clean       - Remove containers and volumes"

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f app

lint:
	docker compose exec -T app python -m ruff check src/ tests/

typecheck:
	docker compose exec -T app python -m mypy src/

test:
	docker compose exec -T app pytest tests/ -v --cov=src/billing_service --cov-report=html --cov-report=term --cov-report=json:artifacts/coverage.json

migrate:
	docker compose exec app alembic upgrade head

shell:
	docker compose exec app /bin/bash

clean:
	docker compose down -v
	docker compose rm -f
