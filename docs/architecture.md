# Architecture Documentation

**Version:** 1.0  
**Last Updated:** November 11, 2025  
**Service:** Centralized Billing & Entitlements Service

## Overview

The Billing Service is a centralized FastAPI application that handles payments, subscriptions, and entitlements for multiple Python micro-applications. It integrates with Stripe for payment processing and maintains an authoritative record of user entitlements.

## System Architecture

### High-Level Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────┐
│  Micro-Apps     │────────▶│  Billing Service │────────▶│   Stripe    │
│  (10-20 apps)   │  REST   │   (FastAPI)      │  API    │   (Payment  │
│                 │  API    │                  │  Calls  │   Processor)│
└─────────────────┘         └──────────────────┘         └─────────────┘
                                      │
                                      │ Webhooks
                                      ▼
                            ┌──────────────────┐
                            │   PostgreSQL     │
                            │   (Database)    │
                            └──────────────────┘
                                      │
                                      │ Cache
                                      ▼
                            ┌──────────────────┐
                            │      Redis       │
                            │   (Cache/Queue)  │
                            └──────────────────┘
```

## Component Architecture

### Core Components

1. **API Layer** (`checkout_api.py`, `entitlements_api.py`, `portal_api.py`, `webhooks.py`)
   - RESTful endpoints for micro-apps
   - Webhook endpoint for Stripe events
   - Authentication middleware

2. **Business Logic Layer**
   - **Entitlements Engine** (`entitlements.py`): Computes user entitlements from subscriptions, purchases, and manual grants
   - **Event Processors** (`event_processors.py`): Process Stripe webhook events and update internal state
   - **Stripe Service** (`stripe_service.py`): Wrapper for Stripe API interactions

3. **Data Layer**
   - **Models** (`models.py`): SQLAlchemy ORM models
   - **Database** (`database.py`): Connection and session management
   - **Cache** (`cache.py`): Redis-based caching for entitlements and event deduplication

4. **Infrastructure Layer**
   - **Authentication** (`auth.py`): API key validation
   - **Configuration** (`config.py`): Environment-based settings
   - **Webhook Verification** (`webhook_verification.py`): Stripe signature verification

## Data Flow

### Checkout Flow

1. Micro-app calls `POST /api/v1/checkout/create`
2. Service validates API key and creates Stripe checkout session
3. Returns checkout URL to micro-app
4. User completes payment on Stripe
5. Stripe sends `checkout.session.completed` webhook
6. Service processes webhook, creates subscription/purchase record
7. Service recomputes entitlements and stores in database
8. Service invalidates Redis cache

### Entitlements Query Flow

1. Micro-app calls `GET /api/v1/entitlements?user_id=X`
2. Service validates API key
3. Service checks Redis cache first
4. If cache miss, queries database for computed entitlements
5. Returns entitlements to micro-app
6. Caches result in Redis

### Webhook Processing Flow

1. Stripe sends webhook to `POST /api/v1/webhooks/stripe`
2. Service verifies webhook signature
3. Service checks Redis for event deduplication
4. Event router dispatches to appropriate processor
5. Processor updates database state
6. Processor recomputes entitlements
7. Processor invalidates cache
8. Service returns 200 OK to Stripe

## Database Schema

### Core Entities

- **Project**: Represents a micro-application
- **Product**: Sellable capability with feature codes
- **Price**: Commercial terms (amount, interval) linked to Stripe
- **Subscription**: Recurring billing arrangement
- **Purchase**: One-time payment transaction
- **ManualGrant**: Administrative entitlement override
- **Entitlement**: Computed access rights (denormalized for fast queries)

### Relationships

- Project → Products (1:N)
- Product → Prices (1:N)
- Price → Subscriptions (1:N)
- Price → Purchases (1:N)
- Project → Subscriptions (1:N)
- Project → Purchases (1:N)
- Project → ManualGrants (1:N)
- Project → Entitlements (1:N)

## Entitlements Computation Logic

Entitlements are computed from three sources:

1. **Active Subscriptions**: Subscriptions with status `ACTIVE` or `TRIALING` grant entitlements until `current_period_end`
2. **Succeeded Purchases**: Purchases with status `SUCCEEDED` grant entitlements (lifetime or time-limited)
3. **Active Manual Grants**: Non-revoked grants within validity period

Computation rules:
- Multiple sources can provide the same feature (union semantics)
- Entitlements are recomputed after every state change
- Results are stored in `entitlements` table for fast queries
- Cache is invalidated after recomputation

## Event Processing

### Supported Stripe Events

1. `checkout.session.completed`: Creates subscription or purchase
2. `invoice.payment_succeeded`: Updates subscription period (renewal)
3. `customer.subscription.updated`: Updates subscription status/metadata
4. `customer.subscription.deleted`: Marks subscription as canceled
5. `charge.refunded`: Marks purchase as refunded

### Idempotency

- Events are deduplicated using Redis (24-hour TTL)
- Database operations use unique constraints to prevent duplicates
- Processors check for existing records before creating new ones

## Caching Strategy

- **Entitlements Cache**: Key format `entitlements:{project_id}:{user_id}`, TTL 5 minutes (300 seconds)
- **Event Deduplication**: Key format `webhook:{event_id}`, TTL 24 hours
- Cache invalidation occurs after every state change
- Fail-open: Cache failures don't block operations

## Security

- **API Authentication**: Project-scoped API keys (SHA-256 hashed)
- **Admin Authentication**: Separate admin API key for privileged operations
- **Webhook Verification**: Stripe signature verification using webhook secret
- **Database**: Connection pooling, parameterized queries
- **CORS**: Configurable (currently permissive for development)

## Deployment Architecture

- **Containerization**: Docker multi-stage build
- **Orchestration**: Docker Compose for local development
- **Database**: PostgreSQL 15 (external or containerized)
- **Cache**: Redis 7 (external or containerized)
- **Web Server**: Uvicorn (ASGI)
- **Health Checks**: `/healthz`, `/ready`, `/live` endpoints

## Scalability Considerations

- Stateless API layer (horizontal scaling possible)
- Database connection pooling
- Redis caching reduces database load
- Event processing is asynchronous (webhook handlers)
- Idempotent operations allow safe retries

## Technology Stack

- **Framework**: FastAPI 0.104+
- **Database**: PostgreSQL 15, SQLAlchemy 2.0+
- **Cache**: Redis 5.0+
- **Payment**: Stripe 7.0+
- **Validation**: Pydantic 2.5+
- **Migrations**: Alembic 1.12+
- **Testing**: pytest 7.4+, pytest-cov
- **Linting**: ruff 0.1+
- **Type Checking**: mypy 1.7+

## Monitoring & Observability

- Health check endpoints for load balancer integration
- Structured logging (Python logging module)
- Database connection health checks
- Error tracking via exception handlers
- Metrics collection ready (Prometheus client included)

## Future Enhancements

- Metrics export (Prometheus)
- Structured logging (structlog)
- Event streaming (Kafka/RabbitMQ)
- Multi-region support
- Advanced reconciliation jobs
- Admin API for manual operations
