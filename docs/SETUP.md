# Setup Guide

## Prerequisites

- Docker and Docker Compose installed
- Stripe account with API keys
- Basic knowledge of PostgreSQL

## Initial Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd stripe
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```bash
DATABASE_URL=postgresql://postgres:postgres@db:5432/billing
REDIS_URL=redis://redis:6379/0
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
RECONCILIATION_ENABLED=true
RECONCILIATION_SCHEDULE_HOUR=2
RECONCILIATION_DAYS_BACK=7
```

Replace with your actual Stripe keys.

### 3. Build and Start Services

```bash
# Build Docker images
docker compose build

# Start services
docker compose up -d

# Verify services are running
docker compose ps
```

### 4. Run Database Migrations

```bash
docker compose run --rm app make migrate
```

### 5. Verify Installation

```bash
# Check health endpoint
curl http://localhost:8000/health

# Should return: {"status":"ok"}
```

## Development Workflow

### Running Tests

```bash
# Run all tests
docker compose run --rm app make test

# Run specific test file
docker compose run --rm app poetry run pytest tests/test_webhooks.py

# Run with coverage
docker compose run --rm app poetry run pytest --cov=src --cov-report=html
```

### Linting and Type Checking

```bash
# Run linter
docker compose run --rm app make lint

# Run type checker
docker compose run --rm app make typecheck

# Run both
docker compose run --rm app make lint typecheck
```

### Accessing Database

```bash
# Connect to PostgreSQL
docker compose exec db psql -U postgres billing

# Or use a GUI tool connecting to:
# Host: localhost
# Port: 5432
# Database: billing
# User: postgres
# Password: postgres
```

### Accessing Application Shell

```bash
docker compose run --rm app make shell
```

## Creating Test Data

### Create a Project

```sql
INSERT INTO projects (name, active) VALUES ('test_project', true);
```

### Create an App

```sql
INSERT INTO apps (project_id, name, api_key, active)
VALUES (1, 'test_app', 'test_api_key_123', true);
```

### Create a User

```sql
INSERT INTO users (project_id, external_user_id, email)
VALUES (1, 'user_123', 'user@example.com');
```

## Testing Stripe Integration

### Test Mode

The service uses Stripe test mode by default. Use test API keys:
- Test secret key: `sk_test_...`
- Test webhook secret: `whsec_test_...`

### Test Cards

Use Stripe test cards:
- Success: `4242 4242 4242 4242`
- Decline: `4000 0000 0000 0002`
- 3D Secure: `4000 0025 0000 3155`

### Testing Webhooks Locally

1. Install Stripe CLI: https://stripe.com/docs/stripe-cli
2. Login: `stripe login`
3. Forward webhooks: `stripe listen --forward-to http://localhost:8000/api/v1/webhooks/stripe`
4. Trigger test events: `stripe trigger payment_intent.succeeded`

## API Testing

### Create Checkout Session

```bash
curl -X POST http://localhost:8000/api/v1/checkout/session \
  -H "X-API-Key: test_api_key_123" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "project_id": 1,
    "price_id": "price_test123",
    "mode": "payment",
    "success_url": "https://example.com/success",
    "cancel_url": "https://example.com/cancel"
  }'
```

### Create Portal Session

```bash
curl -X POST http://localhost:8000/api/v1/portal/session \
  -H "X-API-Key: test_api_key_123" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "project_id": 1,
    "return_url": "https://example.com/billing"
  }'
```

## Common Issues

### Port Already in Use

If port 8000 is already in use, modify `docker-compose.yml`:

```yaml
ports:
  - "8001:8000"  # Change 8001 to any available port
```

### Database Connection Errors

1. Ensure database service is running: `docker compose ps db`
2. Check database logs: `docker compose logs db`
3. Verify `DATABASE_URL` in `.env` file

### Migration Errors

1. Check database is accessible
2. Verify Alembic configuration in `alembic.ini`
3. Check migration files in `alembic/versions/`

### Webhook Signature Verification Fails

1. Verify `STRIPE_WEBHOOK_SECRET` matches Stripe dashboard
2. Ensure webhook endpoint is accessible from Stripe
3. Check webhook signature format in logs

## Next Steps

1. Set up Stripe webhook endpoint in Stripe Dashboard
2. Configure production environment variables
3. Set up monitoring and alerting
4. Review security best practices
5. Plan for scaling and high availability

## Additional Resources

- [Stripe API Documentation](https://stripe.com/docs/api)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
