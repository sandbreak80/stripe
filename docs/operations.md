# Operations Guide

**Version:** 1.0  
**Last Updated:** November 11, 2025  
**Service:** Centralized Billing & Entitlements Service

## Overview

This guide covers operational procedures for running, monitoring, and troubleshooting the Billing Service.

## Deployment

### Prerequisites

- Docker and Docker Compose installed
- PostgreSQL 15+ database
- Redis 7+ instance
- Stripe account with API keys

### Environment Variables

Create a `.env` file with the following variables:

```bash
# Database
DATABASE_URL=postgresql://billing_user:billing_pass@postgres:5432/billing_db

# Redis
REDIS_URL=redis://redis:6379/0

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# API Keys
ADMIN_API_KEY=admin_key_here
```

### Starting the Service

```bash
# Build images
docker compose build

# Start services
docker compose up -d

# Run migrations
docker compose exec app alembic upgrade head

# Check logs
docker compose logs -f app
```

### Stopping the Service

```bash
docker compose down
```

## Monitoring

### Health Checks

The service provides three health check endpoints:

- `/healthz`: Basic health check (always returns 200 if service is running)
- `/ready`: Readiness check (verifies database connectivity)
- `/live`: Liveness check (always returns 200)

Configure your load balancer to use `/ready` for health checks.

### Logging

Logs are written to stdout/stderr and can be viewed via:

```bash
docker compose logs -f app
```

Log levels:
- `INFO`: Normal operations
- `WARNING`: Non-critical issues
- `ERROR`: Errors requiring attention
- `CRITICAL`: Critical failures

### Metrics

Currently, basic metrics are available via health endpoints. Future versions will include Prometheus metrics export.

## Database Operations

### Running Migrations

```bash
# Create a new migration
docker compose exec app alembic revision --autogenerate -m "description"

# Apply migrations
docker compose exec app alembic upgrade head

# Rollback one migration
docker compose exec app alembic downgrade -1

# Rollback to specific revision
docker compose exec app alembic downgrade <revision>
```

### Database Backup

```bash
# Backup database
docker compose exec postgres pg_dump -U billing_user billing_db > backup.sql

# Restore database
docker compose exec -T postgres psql -U billing_user billing_db < backup.sql
```

### Database Maintenance

```bash
# Connect to database
docker compose exec postgres psql -U billing_user billing_db

# Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## Cache Operations

### Redis Connection

```bash
# Connect to Redis
docker compose exec redis redis-cli

# Check cache keys
docker compose exec redis redis-cli KEYS "entitlements:*"
docker compose exec redis redis-cli KEYS "webhook:*"

# Clear all cache
docker compose exec redis redis-cli FLUSHDB

# Check Redis memory usage
docker compose exec redis redis-cli INFO memory
```

### Cache Invalidation

Cache is automatically invalidated when entitlements change. To manually invalidate:

```bash
# Invalidate specific user's entitlements
docker compose exec redis redis-cli DEL "entitlements:user_123:project_456"

# Invalidate all entitlements for a project
docker compose exec redis redis-cli --scan --pattern "entitlements:*:project_456" | xargs redis-cli DEL
```

## Troubleshooting

### Service Won't Start

1. Check Docker logs: `docker compose logs app`
2. Verify environment variables: `docker compose exec app env | grep -E "(DATABASE|REDIS|STRIPE)"`
3. Check database connectivity: `docker compose exec app python -c "from billing_service.database import check_db_connection; print(check_db_connection())"`
4. Verify Redis connectivity: `docker compose exec redis redis-cli PING`

### Database Connection Issues

1. Verify PostgreSQL is running: `docker compose ps postgres`
2. Check database credentials in `.env`
3. Test connection: `docker compose exec postgres psql -U billing_user billing_db -c "SELECT 1"`
4. Check database logs: `docker compose logs postgres`

### Webhook Processing Issues

1. Check webhook logs: `docker compose logs app | grep webhook`
2. Verify webhook secret matches Stripe Dashboard
3. Check event deduplication: `docker compose exec redis redis-cli KEYS "webhook:*"`
4. Review Stripe Dashboard for webhook delivery status

### Entitlements Not Updating

1. Check if webhooks are being received: `docker compose logs app | grep "checkout.session.completed"`
2. Verify entitlements computation: Query `entitlements` table directly
3. Check cache: `docker compose exec redis redis-cli GET "entitlements:user_123:project_456"`
4. Manually recompute entitlements (requires admin API):
   ```python
   from billing_service.entitlements import recompute_and_store_entitlements
   recompute_and_store_entitlements(db, "user_123", project_id)
   ```

### High Database Load

1. Check active connections: `docker compose exec postgres psql -U billing_user billing_db -c "SELECT count(*) FROM pg_stat_activity"`
2. Review slow queries: Enable `log_min_duration_statement` in PostgreSQL
3. Check cache hit rate: Monitor Redis cache usage
4. Consider increasing connection pool size in `database.py`

## Maintenance Tasks

### Daily Tasks

- Monitor health check endpoints
- Review error logs for anomalies
- Check Stripe webhook delivery status

### Weekly Tasks

- Review database size and growth
- Check Redis memory usage
- Review slow query logs
- Verify backup procedures

### Monthly Tasks

- Run database VACUUM ANALYZE
- Review and optimize indexes
- Audit API key usage
- Review security logs

## Scaling

### Horizontal Scaling

The API layer is stateless and can be scaled horizontally:

1. Run multiple app containers behind a load balancer
2. Ensure all containers share the same database and Redis instance
3. Configure load balancer health checks to use `/ready` endpoint

### Database Scaling

- Use read replicas for read-heavy workloads
- Consider connection pooling (PgBouncer) for high connection counts
- Monitor query performance and optimize slow queries

### Cache Scaling

- Use Redis Cluster for high availability
- Configure appropriate memory limits
- Monitor cache hit rates

## Security

### API Key Management

- Rotate API keys periodically
- Use different keys for different environments
- Never commit API keys to version control
- Use environment variables or secret management systems

### Database Security

- Use strong passwords
- Restrict network access to database
- Enable SSL/TLS for database connections
- Regularly update PostgreSQL

### Webhook Security

- Always verify webhook signatures
- Use HTTPS for webhook endpoints
- Rotate webhook secrets if compromised
- Monitor for suspicious webhook activity

## Disaster Recovery

### Backup Strategy

1. **Database Backups**: Daily automated backups, retain 30 days
2. **Configuration**: Version control for all configuration files
3. **Secrets**: Store in secure secret management system

### Recovery Procedures

1. **Database Recovery**:
   ```bash
   # Stop service
   docker compose down
   
   # Restore database
   docker compose exec -T postgres psql -U billing_user billing_db < backup.sql
   
   # Restart service
   docker compose up -d
   ```

2. **Cache Recovery**: Cache will repopulate automatically from database queries

3. **Stripe Reconciliation**: Run reconciliation job to sync with Stripe if needed

## Performance Tuning

### Database Optimization

- Add indexes for frequently queried columns
- Use connection pooling
- Monitor query performance
- Consider partitioning large tables

### Cache Optimization

- Adjust cache TTL based on usage patterns
- Monitor cache hit rates
- Use appropriate Redis eviction policies

### Application Optimization

- Enable gzip compression
- Use CDN for static assets (if applicable)
- Monitor response times
- Profile slow endpoints

## Support

For issues or questions:

1. Check logs: `docker compose logs app`
2. Review this operations guide
3. Check Stripe Dashboard for payment issues
4. Contact support team with relevant logs and error messages
