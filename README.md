# Centralized Billing & Entitlements Service (Stripe)

## What & Why

Teams were hand-rolling Stripe integrations, duplicating billing logic, and disagreeing on who was entitled to which features. This project creates **one shared service** that:

- Brokers all Stripe checkout, subscription, and customer-portal flows for every micro-application.
- Stores the authoritative record of entitlements (who can use what) so individual apps can just ask a single API.
- Provides operators with a consistent way to replay webhooks, reconcile Stripe vs. database state, and grant exceptions.

**Problems it solves**
- Eliminates bespoke billing code in each micro-app.
- Guarantees consistent paywall behaviour after subscription changes or refunds.
- Centralises operational tooling (webhook storage, reconciliation, metrics, admin overrides).

## How It Works (High-Level)

1. **API Service (FastAPI)**  
   Exposes versioned REST endpoints for checkout, portal links, entitlements, admin overrides, metrics, and health probes. Requests are authenticated with per-app API keys.

2. **Stripe Integration**  
   `stripe_service` helper module creates customers, checkout sessions, and portal sessions using the configured Stripe secret key. Stripe webhooks post back to `/api/v1/webhooks/stripe`, are signature-verified, stored, and processed idempotently.

3. **Database Layer (PostgreSQL via SQLAlchemy)**  
   Tracks projects, apps, users, Stripe customers, products, prices, purchases, subscriptions, entitlements, manual grants, and stored webhook events. Alembic migrations seed the schema.

4. **Caching & Reconciliation**  
   Redis caches entitlement responses. APScheduler periodically runs reconciliation tasks (Stripe vs. DB) when enabled.

5. **Admin & Metrics**  
   Manual grant/revoke endpoints recompute entitlements and invalidate cache entries. Metrics endpoints summarize active subscriptions and revenue per project.

## Repository Tour

```
src/billing_service/          # FastAPI app, routers, business logic, webhook processors
alembic/                      # Database migrations
docs/                         # Architecture, integration guide, ops guide, etc.
tests/                        # Unit & integration tests (pytest + coverage)
artifacts/                    # Test/lint/typecheck/build logs and coverage reports
Makefile                      # Docker-based build/lint/typecheck/test/up/down helpers
docker-compose.yml            # Postgres, Redis, API containers for local dev
docs/integration_guide.md     # Hands-on usage guide (API examples, Stripe setup)
```

## Getting Started

1. **Clone & configure**
   ```
   git clone <repo-url>
   cd stripe
   cp .env.example .env      # or create .env with DB/Redis/Stripe keys
   ```

2. **Install prerequisites**
   - Docker & Docker Compose
   - Make
   - (Optional) Stripe CLI for webhook testing

3. **Run mandatory gates**
   ```
   make build
   make lint
   make typecheck
   make test
   ```
   Logs land in `artifacts/`.

4. **Launch the stack**
   ```
   make up
   docker compose exec app poetry run alembic upgrade head  # run once per environment
   curl http://localhost:8000/health
   ```

5. **Use the APIs**
   - Follow the detailed walkthrough in `docs/integration_guide.md`.
   - Key endpoints:
     - `POST /api/v1/checkout/session`
     - `POST /api/v1/portal/session`
     - `GET  /api/v1/entitlements`
     - `POST /api/v1/admin/grant`
     - `POST /api/v1/admin/revoke`
     - `GET  /api/v1/metrics/project/{id}/subscriptions`
     - `GET  /api/v1/metrics/project/{id}/revenue`
     - `POST /api/v1/webhooks/stripe`
     - Health: `/health`, `/ready`, `/live`

6. **Shut down**
   ```
   make down
   ```

## What’s Built

- ✅ Dockerised FastAPI service with lint/type/test automation (`make` targets).
- ✅ Database schema + Alembic migration covering projects/apps/users/purchases/subscriptions/entitlements/manual grants/webhook events.
- ✅ Checkout & portal flows with Stripe SDK integration and API key enforcement.
- ✅ Webhook receiver with signature verification, raw event storage, idempotent processors, entitlement recompute, and cache invalidation.
- ✅ Redis-backed entitlement caching + admin grant/revoke endpoints.
- ✅ Metrics endpoints summarising subscription counts and revenue.
- ✅ Comprehensive test suite (59 tests, 89.56% coverage).
- ✅ Operations, architecture, and integration documentation.

## Known Gaps & To‑Dos

| Area | Status | Notes |
|------|--------|-------|
| Migrations on startup | 🚧 TODO | Running `alembic upgrade head` is a manual step; wire it into startup/`make up`. |
| Observability | 🚧 TODO | Add structured logging conventions, metrics for webhook processing latency, scheduler health, etc. |
| Scheduler hardening | 🚧 TODO | Surface reconciliation results to logs/metrics and expose a control endpoint. |
| Stripe metadata sync | 🚧 ENH | Provide tooling/docs to sync price metadata from source control to Stripe automatically. |
| API docs on Swagger/ReDoc | ✅ | FastAPI auto-docs available at `/docs` and `/redoc` when running locally. |
| Security hardening | 🚧 ENH | Document HTTPS termination, API key rotation, secret management practices. |
| Portal eligibility helper | 🚧 ENH | Consider endpoint for micro-apps to determine if a user can open the portal before showing the UI. |

### Open Bugs

- **DB migrations not automatic:** Without running Alembic upgrade first, webhook ingestion hits `ProgrammingError: relation "webhook_events" does not exist`. Short-term workaround documented; long-term fix is automating migrations.

### Open Enhancements

- Automate reconciliation observability (emit metrics/alerts).
- Provide seed scripts for creating sample projects/apps/prices/users.
- Add load-test/benchmark guidance for entitlement cache hit rate.
- Publish a Python SDK package (we have internal client logic; package & release it).

## Usage Cheat Sheet

- Replay Stripe webhooks locally using the embedded script snippet in `docs/integration_guide.md`.
- Manual entitlements immediately recompute stored entitlements and clear cache entries—no additional action required.
- Health endpoints:  
  - `/health` – process up  
  - `/ready` – database connectivity check  
  - `/live` – liveness probe

## Contributing & Issue Tracking

- Follow the `make build`, `make lint`, `make typecheck`, `make test` contract before sending changes.
- Log new bugs/ideas in the **Open Bugs** / **Open Enhancements** sections (or convert them into GitHub issues once published).
- Use Alembic for schema changes (`docker compose exec app poetry run alembic revision --autogenerate -m "..."`).
- Update `docs/` (architecture, integration guide, operations) whenever the API or flows change.

## Ready for GitHub

- ✅ CI-like gates (lint/type/test) encapsulated in `make` targets.
- ✅ Documentation for setup, architecture, operations, integration, and status.
- ✅ Clear backlog of bugs/enhancements for future contributors.
- ✅ Artifacts folder capturing build/test logs for compliance or CI uploads.

Have fun monetizing all the things—and if you find a better way to ride the Stripe rocket, document it so the next traveler benefits! 🚀


