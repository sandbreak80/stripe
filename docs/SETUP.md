# Setup Guide

**Version:** 1.0  
**Last Updated:** November 11, 2025  
**Service:** Centralized Billing & Entitlements Service

## Prerequisites

Before setting up the Billing Service, ensure you have:

- **Docker** 20.10+ and **Docker Compose** 2.0+
- **Stripe Account** with API keys (test mode keys are fine for development)
- **PostgreSQL** 15+ (or use Docker container)
- **Redis** 7+ (or use Docker container)
- **Git** (for cloning the repository)

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd stripe
```

### 2. Configure Environment Variables

Copy the example environment file and edit it:

```bash
cp .env.example .env
```

Edit `.env` and set the following variables:

```bash
# Database (defaults work for Docker Compose)
DATABASE_URL=postgresql://billing_user:billing_pass@postgres:5432/billing_db

# Redis (defaults work for Docker Compose)
REDIS_URL=redis://redis:6379/0

# Stripe - Get these from https://dashboard.stripe.com/test/apikeys
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...  # Get from Stripe Dashboard > Webhooks

# Admin API Key (change in production!)
ADMIN_API_KEY=admin_key_change_in_production
```

### 3. Build and Start Services

```bash
# Build Docker images
make build

# Start all services (PostgreSQL, Redis, App)
make up

# Run database migrations
make migrate

# Check service status
docker compose ps
```

### 4. Verify Installation

```bash
# Check health endpoint
curl http://localhost:8000/healthz

# Should return: {"status":"healthy"}

# Check readiness (requires database)
curl http://localhost:8000/ready

# Should return: {"status":"ready"}
```

### 5. View Logs

```bash
# View all logs
make logs

# View specific service logs
docker compose logs -f app
docker compose logs -f postgres
docker compose logs -f redis
```

## Stripe Configuration

### 1. Get Stripe API Keys

1. Go to [Stripe Dashboard](https://dashboard.stripe.com/test/apikeys)
2. Copy your **Secret key** (`sk_test_...`)
3. Copy your **Publishable key** (`pk_test_...`)
4. Add them to your `.env` file

### 2. Configure Webhooks

1. Go to [Stripe Dashboard > Webhooks](https://dashboard.stripe.com/test/webhooks)
2. Click "Add endpoint"
3. Set endpoint URL to: `http://localhost:8000/api/v1/webhooks/stripe` (for local development)
4. Select events to listen for:
   - `checkout.session.completed`
   - `invoice.payment_succeeded`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `charge.refunded`
5. Copy the **Signing secret** (`whsec_...`) and add it to your `.env` file

**Note:** For local development, use [Stripe CLI](https://stripe.com/docs/stripe-cli) to forward webhooks:

```bash
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
```

## Database Setup

### Initial Migration

The database schema is managed by Alembic. Run migrations to create tables:

```bash
make migrate
```

This will create all necessary tables:
- `projects`
- `products`
- `prices`
- `subscriptions`
- `purchases`
- `manual_grants`
- `entitlements`

### Create a Test Project

You'll need to create a project before using the API. Connect to the database:

```bash
docker compose exec postgres psql -U billing_user billing_db
```

Then insert a test project (replace `your_api_key` with a secure key):

```sql
INSERT INTO projects (id, project_id, name, description, api_key_hash, is_active, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    'test-project',
    'Test Project',
    'Test project description',
    encode(digest('your_api_key', 'sha256'), 'hex'),
    true,
    NOW(),
    NOW()
);
```

**Note:** The API key hash is SHA-256 of the plain API key. You'll use the plain key in API requests.

## Development Workflow

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
docker compose exec app pytest tests/test_entitlements.py -v

# Run with coverage
docker compose exec app pytest tests/ -v --cov=src/billing_service --cov-report=term
```

### Linting and Type Checking

```bash
# Run linter
make lint

# Auto-fix linting issues
docker compose exec app python -m ruff check --fix src/ tests/

# Run type checker
make typecheck
```

### Creating Database Migrations

```bash
# Create a new migration
docker compose exec app alembic revision --autogenerate -m "description"

# Review the generated migration file
# Then apply it
make migrate
```

### Accessing the Shell

```bash
# Open shell in app container
make shell

# Or directly
docker compose exec app /bin/bash
```

## Project Structure

```
.
├── alembic/              # Database migrations
│   ├── versions/         # Migration files
│   └── env.py            # Alembic configuration
├── artifacts/            # Build logs, test reports
├── docs/                 # Documentation
│   ├── architecture.md
│   ├── api_reference.md
│   ├── operations.md
│   └── SETUP.md
├── src/
│   └── billing_service/  # Main application code
│       ├── __init__.py
│       ├── auth.py       # Authentication
│       ├── cache.py       # Redis caching
│       ├── checkout_api.py
│       ├── config.py     # Configuration
│       ├── database.py   # Database connection
│       ├── entitlements.py # Entitlements computation
│       ├── entitlements_api.py
│       ├── event_processors.py
│       ├── main.py       # FastAPI app
│       ├── models.py     # SQLAlchemy models
│       ├── portal_api.py
│       ├── schemas.py    # Pydantic schemas
│       ├── stripe_service.py
│       ├── webhook_processors.py
│       ├── webhook_verification.py
│       └── webhooks.py
├── tests/                # Test suite
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_auth.py
│   ├── test_cache.py
│   ├── test_entitlements.py
│   └── test_webhook_verification.py
├── .env.example          # Example environment variables
├── .gitignore
├── Dockerfile            # Docker image definition
├── docker-compose.yml    # Docker Compose configuration
├── Makefile             # Build automation
├── pyproject.toml       # Python project configuration
└── README.md
```

## Common Tasks

### Starting Fresh

```bash
# Stop and remove all containers and volumes
make clean

# Rebuild and start
make build
make up
make migrate
```

### Resetting Database

```bash
# Drop and recreate database
docker compose exec postgres psql -U billing_user -c "DROP DATABASE billing_db;"
docker compose exec postgres psql -U billing_user -c "CREATE DATABASE billing_db;"

# Run migrations
make migrate
```

### Viewing Database

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U billing_user billing_db

# List tables
\dt

# Query projects
SELECT * FROM projects;

# Query entitlements
SELECT * FROM entitlements LIMIT 10;
```

## Troubleshooting

### Port Already in Use

If port 8000 is already in use:

```bash
# Find process using port 8000
lsof -i :8000

# Kill the process or change port in docker-compose.yml
```

### Database Connection Errors

```bash
# Check if PostgreSQL is running
docker compose ps postgres

# Check database logs
docker compose logs postgres

# Test connection
docker compose exec postgres psql -U billing_user billing_db -c "SELECT 1"
```

### Redis Connection Errors

```bash
# Check if Redis is running
docker compose ps redis

# Test Redis connection
docker compose exec redis redis-cli PING
```

### Webhook Not Receiving Events

1. Verify webhook endpoint is configured in Stripe Dashboard
2. For local development, use Stripe CLI:
   ```bash
   stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
   ```
3. Check webhook logs:
   ```bash
   docker compose logs app | grep webhook
   ```

## Production Deployment

For production deployment:

1. **Use production Stripe keys** (not test keys)
2. **Change admin API key** to a strong, random value
3. **Use managed PostgreSQL** (AWS RDS, Google Cloud SQL, etc.)
4. **Use managed Redis** (AWS ElastiCache, Google Cloud Memorystore, etc.)
5. **Enable HTTPS** (use reverse proxy like nginx or Traefik)
6. **Set up monitoring** (Prometheus, Grafana, etc.)
7. **Configure backups** for database
8. **Use secrets management** (AWS Secrets Manager, HashiCorp Vault, etc.)
9. **Set up log aggregation** (ELK stack, CloudWatch, etc.)
10. **Configure webhook endpoint** in Stripe Dashboard to production URL

## Next Steps

After setup:

1. Read [API Reference](api_reference.md) to understand available endpoints
2. Review [Architecture](architecture.md) to understand system design
3. Check [Operations Guide](operations.md) for operational procedures
4. Create your first project and start integrating!

## Getting Help

- Check logs: `make logs`
- Review documentation in `docs/` directory
- Check Stripe Dashboard for payment-related issues
- Review error messages in application logs
