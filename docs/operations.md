# Operations Guide

## Environment Setup

### Required Environment Variables

- `DATABASE_URL`: PostgreSQL connection string (e.g., `postgresql://user:pass@db:5432/billing`)
- `REDIS_URL`: Redis connection string (e.g., `redis://redis:6379/0`)
- `STRIPE_SECRET_KEY`: Stripe secret API key
- `STRIPE_WEBHOOK_SECRET`: Stripe webhook signing secret

### Docker Compose Services

- `app`: Main application service
- `db`: PostgreSQL database
- `redis`: Redis cache (for future use)

## Running the Service

### Development

```bash
# Build containers
docker compose build

# Start services
docker compose up -d

# Run migrations
docker compose run --rm app make migrate

# View logs
docker compose logs -f app
```

### Production

1. Set environment variables in production environment
2. Build Docker image: `docker compose build app`
3. Deploy to container orchestration platform
4. Run migrations: `docker compose run --rm app make migrate`
5. Start services: `docker compose up -d`

## Scheduled Reconciliation

The service includes built-in automated reconciliation scheduling using APScheduler. Reconciliation runs daily to detect and correct data drift between Stripe and the local database.

### Configuration

Configure reconciliation via environment variables:

- `RECONCILIATION_ENABLED`: Enable/disable scheduled reconciliation (default: `true`)
- `RECONCILIATION_SCHEDULE_HOUR`: Hour of day to run reconciliation in UTC (default: `2`)
- `RECONCILIATION_DAYS_BACK`: Number of days to look back when reconciling (default: `7`)

### Manual Reconciliation

Reconciliation can also be triggered manually via the reconciliation API endpoints (if implemented) or by calling the reconciliation functions directly.

### Monitoring Reconciliation

Check application logs for reconciliation execution:

```bash
docker compose logs app | grep -i reconciliation
```

Reconciliation logs include:
- Start time
- Number of subscriptions and purchases checked
- Number of drift issues detected and corrected
- Any errors encountered

## Database Migrations

### Create Migration

```bash
docker compose run --rm app make migration MESSAGE="description"
```

### Apply Migrations

```bash
docker compose run --rm app make migrate
```

### Rollback Migration

```bash
docker compose run --rm app poetry run alembic downgrade -1
```

## Monitoring

### Health Checks

- `/health`: Basic health check
- `/ready`: Readiness check (checks database connectivity)
- `/live`: Liveness check

### Logs

Application logs are written to stdout/stderr. In Docker:

```bash
docker compose logs -f app
```

### Metrics

The service exposes basic metrics endpoints:

- `GET /api/v1/metrics/project/{project_id}/subscriptions`: Active subscription count
- `GET /api/v1/metrics/project/{project_id}/revenue`: Total revenue from successful purchases

These endpoints require API key authentication and project authorization.

## Webhook Configuration

### Stripe Webhook Setup

1. In Stripe Dashboard, go to Developers > Webhooks
2. Add endpoint: `https://your-domain.com/api/v1/webhooks/stripe`
3. Select events to listen for:
   - `checkout.session.completed`
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
   - `charge.refunded`
4. Copy webhook signing secret to `STRIPE_WEBHOOK_SECRET` environment variable

### Testing Webhooks Locally

Use Stripe CLI to forward webhooks:

```bash
stripe listen --forward-to http://localhost:8000/api/v1/webhooks/stripe
```

## Troubleshooting

### Webhook Events Not Processing

1. Check webhook signature verification: Ensure `STRIPE_WEBHOOK_SECRET` matches Stripe dashboard
2. Check database: Verify events are being stored in `webhook_events` table
3. Check logs: Look for error messages in `error_message` column
4. Retry failed events: Manually trigger reprocessing if needed

### Database Connection Issues

1. Verify `DATABASE_URL` is correct
2. Check database is running: `docker compose ps db`
3. Check database logs: `docker compose logs db`

### API Key Issues

1. Verify API key exists in `apps` table
2. Check API key is active (`active = true`)
3. Verify API key matches project ID in request

## Backup and Recovery

### Database Backup

```bash
docker compose exec db pg_dump -U postgres billing > backup.sql
```

### Database Restore

```bash
docker compose exec -T db psql -U postgres billing < backup.sql
```

## Scaling

### Horizontal Scaling

The service is stateless and can be scaled horizontally:
- Run multiple instances behind a load balancer
- Ensure all instances share the same database
- Webhook endpoints should be accessible from Stripe

### Database Scaling

- Use read replicas for read-heavy workloads
- Consider connection pooling (PgBouncer) for high connection counts

## Security

### API Keys

- Rotate API keys regularly
- Use strong, randomly generated keys
- Store keys securely (environment variables, secrets manager)

### Webhook Security

- Always verify webhook signatures
- Use HTTPS for webhook endpoints
- Monitor for suspicious webhook activity

### Database Security

- Use strong database passwords
- Restrict database access to application only
- Enable SSL/TLS for database connections in production

## Maintenance

### Regular Tasks

1. Monitor webhook processing failures
2. Review and clean up old webhook events (if needed)
3. Monitor database size and performance
4. Review application logs for errors
5. Update dependencies regularly

### Reconciliation

The reconciliation system (`src/billing_service/reconciliation.py`) automatically detects and corrects data drift between Stripe and local database.

**Running Reconciliation:**

```bash
# Run reconciliation manually (inside container)
docker compose run --rm app poetry run python -c "
from billing_service.database import get_db
from billing_service.reconciliation import reconcile_all
db = next(get_db())
result = reconcile_all(db, days_back=7)
print(result)
"
```

**Scheduling Reconciliation:**

Set up a cron job or scheduled task to run reconciliation daily:

```bash
# Example cron entry (runs daily at 2 AM)
0 2 * * * cd /path/to/stripe && docker compose run --rm app poetry run python -c "from billing_service.database import get_db; from billing_service.reconciliation import reconcile_all; db = next(get_db()); reconcile_all(db, days_back=7)"
```

**Reconciliation Process:**

1. Queries Stripe for recent subscriptions (last 7 days by default)
2. Compares subscription status and period end with local records
3. Queries Stripe for recent purchases (last 7 days by default)
4. Compares purchase status with local records
5. Updates local records to match Stripe when drift detected
6. Recomputes entitlements for affected users
7. Invalidates cache for affected users
8. Returns summary with drift counts

**Monitoring Reconciliation:**

Check logs for reconciliation results:
- `subscriptions_checked`: Number of subscriptions verified
- `purchases_checked`: Number of purchases verified
- `drift_detected`: Number of discrepancies found
- `corrected`: Number of records corrected
