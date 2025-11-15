# Testing Guide

**⚠️ IMPORTANT: All tests MUST run inside Docker containers. Never run pytest directly on the host system.**

## Running Tests

All tests run inside Docker containers using the `app` service defined in `docker-compose.yml`.

### Quick Start

```bash
# Build and start containers
docker compose up -d

# Run all tests (unit tests with mocks)
make test

# Run Stripe integration tests (requires USE_REAL_STRIPE=true)
make test-stripe

# Run all tests including Stripe integration
make test-all
```

## Test Types

### Unit Tests (Default)
- Use mocked Stripe API calls
- Fast execution
- No external dependencies
- Run with: `make test`

### Stripe Integration Tests
- Use real Stripe API (test mode only)
- Validates actual API integration
- Requires `USE_REAL_STRIPE=true` in `.env` or environment
- Run with: `make test-stripe`

## Environment Variables

Tests read configuration from:
1. `.env` file (loaded by docker-compose)
2. Environment variables passed to container

Key variables:
- `USE_REAL_STRIPE`: Set to `true` to enable real Stripe API tests
- `STRIPE_SECRET_KEY`: Stripe test secret key (must start with `sk_test_`)
- `STRIPE_PUBLISHABLE_KEY`: Stripe test publishable key

## Running Tests Manually (Inside Docker)

All commands must run inside the Docker container:

```bash
# Enter the container shell
docker compose exec app /bin/bash

# Inside container, run tests
pytest tests/ -v

# Run specific test file
pytest tests/test_api.py -v

# Run with markers
pytest tests/ -v -m integration_stripe

# Run with coverage
pytest tests/ -v --cov=src/billing_service --cov-report=term
```

## Test Markers

- `@pytest.mark.unit`: Unit tests (mocked)
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.integration_stripe`: Stripe API integration tests
- `@pytest.mark.slow`: Slow-running tests

## Docker-Only Testing

**Why Docker-only?**
1. Consistent environment across all developers
2. Matches production deployment
3. Isolated dependencies (PostgreSQL, Redis, Python packages)
4. No host system pollution
5. Reproducible test runs

**Never run:**
- ❌ `pytest` on host
- ❌ `python -m pytest` on host
- ❌ Direct Python execution on host

**Always use:**
- ✅ `docker compose exec app pytest`
- ✅ `make test`
- ✅ Commands inside container shell

## Troubleshooting

### Tests not finding Stripe keys
Ensure `.env` file exists and has valid keys:
```bash
docker compose exec app python -c "from billing_service.config import settings; print('Keys loaded:', bool(settings.stripe_secret_key))"
```

### Stripe integration tests skipped
Check `USE_REAL_STRIPE` is set:
```bash
docker compose exec app env | grep USE_REAL_STRIPE
```

### Container not running
Start containers first:
```bash
docker compose up -d
docker compose ps  # Verify all services are running
```
