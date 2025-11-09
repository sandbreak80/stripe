.PHONY: build lint typecheck test up down clean logs shell lint-internal typecheck-internal test-internal

# Build Docker images
build:
	docker compose build

# Run linting (host)
lint:
	docker compose run --rm app make lint-internal

# Run linting (container)
lint-internal:
	poetry run ruff check --fix src/ tests/ || true
	poetry run ruff format src/ tests/ || true
	poetry run ruff check src/ tests/ || true
	poetry run ruff format --check src/ tests/ || true

# Run type checking (host)
typecheck:
	docker compose run --rm app make typecheck-internal

# Run type checking (container)
typecheck-internal:
	poetry run mypy src/

# Run tests (host)
test:
	docker compose run --rm app make test-internal

# Run tests (container)
test-internal:
	poetry run pytest tests/ -v --cov=src --cov-report=html --cov-report=term --cov-report=json:artifacts/coverage.json

# Start services
up:
	docker compose up -d

# Stop services
down:
	docker compose down

# Clean up containers and volumes
clean:
	docker compose down -v
	docker compose rm -f

# View logs
logs:
	docker compose logs -f app

# Shell into app container
shell:
	docker compose exec app bash

# Run migrations
migrate:
	docker compose run --rm app poetry run alembic upgrade head

# Create new migration
migration:
	docker compose run --rm app poetry run alembic revision --autogenerate -m "$(msg)"
