# Architecture Documentation

## Overview

The Centralized Billing & Entitlements Service is a FastAPI-based microservice that handles payments, subscriptions, and entitlements for multiple micro-applications. It integrates with Stripe for payment processing and maintains an authoritative record of user entitlements.

## System Architecture

### Components

1. **API Layer** (`src/billing_service/main.py`)
   - FastAPI application with health, readiness, and liveness endpoints
   - Routes payment and webhook requests to appropriate handlers

2. **Payment Module** (`src/billing_service/payments.py`)
   - Creates Stripe checkout sessions for one-time and recurring purchases
   - Creates Stripe billing portal sessions for customer self-service
   - Manages user and Stripe customer mappings

3. **Webhook Module** (`src/billing_service/webhooks.py`)
   - Receives and verifies Stripe webhook events
   - Stores raw events for audit and idempotency
   - Routes events to appropriate processors

4. **Webhook Processors** (`src/billing_service/webhook_processors.py`)
   - Process payment lifecycle events (succeeded, failed, refunded)
   - Process subscription lifecycle events (created, updated, deleted)
   - Process invoice events (payment succeeded, payment failed)
   - Update purchase and subscription records idempotently
   - Trigger entitlement recomputation and cache invalidation

5. **Entitlements Engine** (`src/billing_service/entitlements.py`)
   - Computes effective entitlements from subscriptions, purchases, and manual grants
   - Handles validity windows and precedence rules
   - Stores computed entitlements in database for fast retrieval

6. **Entitlements API** (`src/billing_service/entitlements_api.py`)
   - Exposes `GET /api/v1/entitlements` endpoint
   - Integrates with Redis cache for low-latency responses
   - Falls back to database computation when cache miss

7. **Cache Layer** (`src/billing_service/cache.py`)
   - Redis-based caching for entitlements
   - Cache invalidation on entitlement changes
   - TTL-based expiration

8. **Administrative Functions** (`src/billing_service/admin.py`)
   - Manual grant/revoke endpoints
   - Audit trail for administrative actions
   - Triggers entitlement recomputation

9. **Metrics** (`src/billing_service/metrics.py`)
   - Active subscription counts per project
   - Revenue indicators per project

10. **Reconciliation** (`src/billing_service/reconciliation.py`)
    - Scheduled job to reconcile Stripe data with local database
    - Detects and corrects data drift
    - Triggers entitlement recomputation on corrections

11. **Scheduler** (`src/billing_service/scheduler.py`)
    - Automated scheduling system using APScheduler
    - Runs daily reconciliation at configurable time (default: 2 AM UTC)
    - Configurable via environment variables
    - Starts automatically on application startup

12. **Authentication** (`src/billing_service/auth.py`)
    - API key-based authentication for micro-apps
    - Project-scoped access control

13. **Data Models** (`src/billing_service/models.py`)
    - `Project`: Represents a micro-application
    - `App`: Client integration with API key
    - `User`: End user within a project (unique constraint on `project_id` + `external_user_id`)
    - `StripeCustomer`: Mapping between users and Stripe customers
    - `Product`: Sellable products within a project
    - `Price`: Commercial terms for products (monthly, yearly, one-time)
    - `Purchase`: One-time purchase records
    - `Subscription`: Recurring subscription records
    - `Entitlement`: Computed entitlements by user and project
    - `ManualGrant`: Manual grant/revoke records with audit trail
    - `WebhookEvent`: Raw webhook events for audit and idempotency

7. **Database** (`src/billing_service/database.py`)
   - SQLAlchemy ORM setup
   - PostgreSQL database for persistent storage
   - Alembic for database migrations

## Data Flow

### Checkout Flow
1. Micro-app calls `POST /api/v1/checkout/session` with user ID, project ID, and price ID
2. Service creates or retrieves Stripe customer
3. Service creates Stripe checkout session with metadata
4. Service returns checkout URL to micro-app
5. User completes payment on Stripe
6. Stripe sends webhook events (checkout.session.completed, payment_intent.succeeded)
7. Service processes webhooks and creates purchase/subscription records

### Webhook Processing Flow
1. Stripe sends webhook event to `POST /api/v1/webhooks/stripe`
2. Service verifies webhook signature
3. Service checks if event already processed (idempotency check)
4. Service stores raw event in `webhook_events` table
5. Service routes event to appropriate processor
6. Processor updates purchase/subscription records
7. Service marks event as processed

### Portal Flow
1. Micro-app calls `POST /api/v1/portal/session` with user ID and project ID
2. Service retrieves Stripe customer
3. Service creates Stripe billing portal session
4. Service returns portal URL to micro-app
5. User manages subscription/payment methods on Stripe
6. Stripe sends webhook events for changes
7. Service processes webhooks and updates records
8. Service recomputes entitlements and invalidates cache

### Entitlement Retrieval Flow
1. Micro-app calls `GET /api/v1/entitlements` with user ID and project ID
2. Service checks Redis cache for cached entitlements
3. If cache hit, return cached entitlements
4. If cache miss, compute entitlements from database
5. Store computed entitlements in cache
6. Return entitlements to micro-app

### Administrative Grant/Revoke Flow
1. Admin calls `POST /api/v1/admin/grant` or `POST /api/v1/admin/revoke`
2. Service validates API key and project authorization
3. Service creates `ManualGrant` record with audit trail
4. Service recomputes entitlements for user
5. Service invalidates cache for user
6. Service returns updated entitlement status

### Reconciliation Flow
1. Scheduled job runs reconciliation (e.g., daily)
2. Service queries Stripe for recent subscriptions/purchases
3. Service compares Stripe data with local database records
4. Service detects drift (status mismatches, period end differences)
5. Service updates local records to match Stripe
6. Service recomputes entitlements for affected users
7. Service invalidates cache for affected users
8. Service logs reconciliation results

## Idempotency

All webhook handlers are idempotent:
- Events are stored with unique Stripe event ID
- Processors check for existing records before creating new ones
- Duplicate events are detected and skipped
- Failed events can be retried without side effects

## Security

- Webhook signature verification using Stripe webhook secret
- API key authentication for micro-app endpoints
- Project-scoped access control
- No raw card data stored (Stripe handles PCI compliance)

## Caching Strategy

- Entitlements are cached in Redis with TTL (default: 1 hour)
- Cache keys: `entitlements:{user_id}:{project_id}`
- Cache invalidation occurs on:
  - Webhook events (payment succeeded/failed, subscription created/updated/deleted)
  - Manual grant/revoke operations
  - Reconciliation corrections
- Cache miss triggers database computation and cache update

## Entitlement Computation

Entitlements are computed from three sources:
1. **Active Subscriptions**: Features from active/trialing subscriptions with valid period end
2. **Successful Purchases**: Features from one-time purchases (lifetime or time-boxed)
3. **Manual Grants**: Administrative overrides (can override or complement paid access)

Precedence rules:
- Manual grants take precedence over subscriptions/purchases
- Manual revokes override all sources
- Latest grant/revoke wins for same feature code

## Technology Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Cache**: Redis
- **Migrations**: Alembic
- **Payment Processing**: Stripe API
- **Testing**: pytest with pytest-cov
- **Linting**: Ruff
- **Type Checking**: MyPy
- **Containerization**: Docker and Docker Compose
