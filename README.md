# Centralized Billing & Entitlements Service

A centralized service for handling payments, subscriptions, and entitlements for 10-20 Python micro-applications using Stripe.

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Make

### Setup

1. Copy environment variables:
```bash
cp .env.example .env
```

2. Build and start services (override host ports if needed, e.g. `export APP_HOST_PORT=18000 POSTGRES_HOST_PORT=55432 REDIS_HOST_PORT=16379`):
```bash
make build
make up
```

3. Run migrations:
```bash
make migrate
```

4. Check health:
```bash
curl http://localhost:8000/healthz
```

## Development

### Running Tests
```bash
make test
```

### Linting
```bash
make lint
```

### Type Checking
```bash
make typecheck
```

### View Logs
```bash
make logs
```

## Documentation

See `docs/` directory for:
- Architecture overview
- API reference
- Operations guide
- Setup instructions

## Project Snapshot (2025-11-11)

- **What it is:** A centralized Stripe billing, subscription, and entitlements service that every micro-app integrates with instead of re‑implementing payments.
- **What it does:** Creates checkout and portal sessions, ingests five critical Stripe webhooks with idempotency, computes and caches entitlements, exposes project-level metrics, and runs scheduled reconciliation jobs—all from within Dockerized infrastructure.
- **Why it exists:** To stop duplicate Stripe integrations across 10–20 Python micro-apps, protect revenue, enforce consistent access control, and cut integration time from days to hours while improving compliance and auditability.
- **What’s working:** Core APIs, webhook processors, reconciliation scheduler, Prometheus `/metrics`, Redis caching, and documentation are production-ready; critical logic like `entitlements.py` sits at 80% coverage.
- **What’s missing / how to improve:** Test coverage is only 67.3% overall (spec requires ≥85% unit / ≥70% integration); event processors, admin endpoints, and webhook routes lack direct tests; load/performance testing for the <100 ms entitlement SLA is absent; lint/type gates still show 200+ style issues and 30 SQLAlchemy typing errors; cache TTL docs conflict with the 5-minute implementation.
- **Critical blockers:** 18 failing tests stem from brittle async/mocking infrastructure (Stripe client, Redis, settings patching) that also blocks new coverage; performance validation cannot proceed until the test harness is stabilized.
- **Configuration reminders:** Populate `.env` with Stripe keys, database, Redis, and `ADMIN_API_KEY` before `docker compose up`; run `docker compose exec app alembic upgrade head` after deployment; ensure webhook signing secret matches Stripe dashboard.
- **Next actions:** Refactor test fixtures to unblock async mocking, backfill coverage for event processors/webhooks/admin APIs, run load tests once harness is solid, align cache TTL documentation with code, and clean up lint/type debt as part of CI hardening.
