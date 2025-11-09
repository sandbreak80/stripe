# Integration Guide — Centralized Billing & Entitlements Service

Welcome aboard the billing rocket ship! This guide walks you through spinning up the stack, poking the APIs, wiring everything into your Stripe account, and keeping tabs on what’s left on our shared to‑do list. Grab a favorite beverage and let’s have some fun building serious infrastructure.

## 1. System Quickstart

**Prerequisites**
- Docker + Docker Compose
- Make (for the helper targets)
- Stripe test account credentials

**Environment variables**
Create `.env` in the repo root (the app loads it via `pydantic-settings`):
```
DATABASE_URL=postgresql://billing_user:billing_pass@db:5432/billing_db
REDIS_URL=redis://redis:6379/0
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
ENVIRONMENT=development
RECONCILIATION_ENABLED=true
RECONCILIATION_SCHEDULE_HOUR=2
RECONCILIATION_DAYS_BACK=7
```

**Build, lint, typecheck, test**
```
make build
make lint
make typecheck
make test
```
Artifacts live under `artifacts/` for easy evidence gathering.

**Run the stack**
```
make up
docker compose exec app poetry run alembic upgrade head   # run migrations once
curl http://localhost:8000/health                        # expect {"status":"ok"}
```
Shut things down when you’re done:
```
make down
```

## 2. API Authentication & Project Setup

All API routes (except `/health`, `/ready`, `/live`) expect an `X-API-Key` header. Keys are defined in the `apps` table and scoped to a single project.

Create a project + app record (using psql inside the DB container):
```
docker compose exec db psql -U billing_user -d billing_db <<'SQL'
INSERT INTO projects (name) VALUES ('space_journal') RETURNING id;
-- note the returned project id (e.g. 1)
INSERT INTO apps (project_id, name, api_key)
VALUES (1, 'space_journal_backend', 'sk_demo_space_journal');
SQL
```

Use the `api_key` value (`sk_demo_space_journal` above) in every API request header:
```
-H "X-API-Key: sk_demo_space_journal"
```

## 3. API Playground

### 3.1 Checkout Session
```
curl -X POST http://localhost:8000/api/v1/checkout/session \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk_demo_space_journal" \
  -d '{
        "user_id": "user_42",
        "project_id": 1,
        "price_id": "price_123",
        "mode": "subscription",
        "success_url": "https://app.local/success",
        "cancel_url": "https://app.local/cancel"
      }'
```
Response:
```
{"checkout_url":"https://checkout.stripe.com/pay/..."}
```

### 3.2 Customer Portal
```
curl -X POST http://localhost:8000/api/v1/portal/session \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk_demo_space_journal" \
  -d '{
        "user_id": "user_42",
        "project_id": 1,
        "return_url": "https://app.local/account"
      }'
```
Response: `{"portal_url":"https://billing.stripe.com/session/..."}`

### 3.3 Entitlements
```
curl "http://localhost:8000/api/v1/entitlements?user_id=user_42&project_id=1" \
  -H "X-API-Key: sk_demo_space_journal"
```
Response:
```
{
  "entitlements": [
    {
      "feature_code": "pro",
      "active": true,
      "source": "subscription",
      "source_id": 12,
      "valid_from": "2025-11-09T06:00:00",
      "valid_to": "2025-12-09T06:00:00"
    }
  ]
}
```

### 3.4 Admin Overrides
Grant manual access:
```
curl -X POST http://localhost:8000/api/v1/admin/grant \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk_demo_space_journal" \
  -d '{
        "user_id": "user_42",
        "project_id": 1,
        "feature_code": "labs",
        "granted_by": "support@spacehq",
        "reason": "VIP pilot",
        "valid_to": "2026-01-01T00:00:00Z"
      }'
```
Revoke with the `/api/v1/admin/revoke` twin.

### 3.5 Metrics Snapshot
```
curl http://localhost:8000/api/v1/metrics/project/1/subscriptions \
  -H "X-API-Key: sk_demo_space_journal"
curl http://localhost:8000/api/v1/metrics/project/1/revenue \
  -H "X-API-Key: sk_demo_space_journal"
```

### 3.6 Webhook Replay
Use the embedded Python helper to send sample events:
```
docker compose exec app python - <<'PY'
import hmac, hashlib, json, time, urllib.request
secret = "whsec_placeholder"  # replace with your signing secret
events = [
    {
        "id": "evt_cli_pi_succeeded",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi_cli_123", "customer": "cus_cli_123", "amount": 1499, "currency": "usd"}}
    }
]
for event in events:
    payload = json.dumps(event).encode()
    ts = str(int(time.time()))
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    req = urllib.request.Request(
        "http://localhost:8000/api/v1/webhooks/stripe",
        data=payload,
        headers={"Content-Type": "application/json", "stripe-signature": f"t={ts},v1={sig}"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        print(event["type"], resp.status, resp.read().decode())
PY
```
Swap in the events you want to test (`customer.subscription.created`, `invoice.payment_succeeded`, etc.).

## 4. Hooking Up Your Stripe Account

1. **Enable test mode** in the Stripe dashboard (top-left switch).
2. **API keys**: Dashboard → Developers → API Keys → reveal your test secret key (`sk_test_...`) and drop it into `.env` as `STRIPE_SECRET_KEY`.
3. **Products & prices**: create catalog items in Stripe, then mirror them in the service database:
   ```
   INSERT INTO products (project_id, name, description)
   VALUES (1, 'Space Journal Pro', 'Unlocks pro writing tools')
   RETURNING id;

   INSERT INTO prices (product_id, stripe_price_id, feature_code, amount, currency, interval)
   VALUES (1, 'price_123', 'pro', 1499, 'usd', 'month');
   ```
   Keep the `feature_code` short and descriptive—this is what entitlement checks return to client apps. (Optional but recommended: duplicate the `project_id` and `feature_code` as metadata on the Stripe price for dashboard clarity.)
4. **Webhook endpoint**: Dashboard → Developers → Webhooks → “Add endpoint”.
   - URL: `https://<your-domain-or-ngrok>/api/v1/webhooks/stripe`
   - Events: `checkout.session.completed`, `payment_intent.succeeded`, `payment_intent.payment_failed`, `customer.subscription.created/updated/deleted`, `invoice.payment_succeeded/failed`, `charge.refunded`.
   - Copy the signing secret (`whsec_...`) into `.env` as `STRIPE_WEBHOOK_SECRET`.
5. **Stripe CLI (optional but delightful)**:
   ```
   stripe login
   stripe listen --forward-to http://localhost:8000/api/v1/webhooks/stripe
   stripe trigger payment_intent.succeeded
   ```
   Watch the app logs light up and cache invalidations fire.

## 5. Operational Tips

- **Scheduler**: The APScheduler job that runs daily reconciliation starts automatically on FastAPI startup. Toggle via `RECONCILIATION_ENABLED`.
- **Logs**: `docker compose logs -f app` keeps you in the loop; webhook diagnostics surface here.
- **Database chores**: use Alembic via `docker compose exec app poetry run alembic revision --autogenerate -m "..."` followed by `upgrade head`.
- **Cache**: Redis stores entitlement responses. Manual grants/revokes and webhook processors automatically invalidate the right keys.

## 6. Outstanding Work (a.k.a. Adventure Hooks)

- **Automate migrations**: wire `poetry run alembic upgrade head` into startup/Make targets so we can drop the manual step.
- **Production hardening**: add HTTPS termination guidance, secret rotation playbooks, and tighten Stripe error monitoring.
- **Portal eligibility UX**: consider creating a helper endpoint that tells the micro-app whether a user qualifies for the billing portal.
- **Scheduler observability**: broadcast reconciliation successes/failures to metrics or alerts.
- **Stripe metadata hygiene**: provide tooling to sync Stripe price metadata from source control to avoid manual drift.
- **Port collisions**: document how to restore any services you stop (e.g., restart `portainer` if you halted it to free port 8000).

Have ideas? Add them here or capture them in the repo TODO board—we love a good quest.

## 7. Troubleshooting Cheat Codes

- `relation "... does not exist"`: run the Alembic upgrade command again—migrations must execute before webhooks hit the DB.
- `401 Unauthorized`: double-check the `X-API-Key` header and that the `apps.active` flag is `true`.
- `403 Project ID does not match`: ensure the `project_id` in your request aligns with the app’s project.
- Stripe portal says “customer not found”: the user must have at least one mapped Stripe customer (complete a checkout first).
- Need to reset the world? `make down` followed by `docker volume rm stripe_postgres_data` gives you a clean slate.

Go forth, build delightful monetization flows, and keep the fun (and logs) rolling! If you discover new tricks, sprinkle them back into this guide so the next traveler gets an even smoother ride.


