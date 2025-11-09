# API Reference

## Base URL

All API endpoints are prefixed with `/api/v1`.

## Authentication

All endpoints (except webhooks) require API key authentication via the `X-API-Key` header.

```
X-API-Key: <your-api-key>
```

## Endpoints

### Health Checks

#### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "ok"
}
```

#### GET /ready
Readiness check endpoint.

**Response:**
```json
{
  "status": "ready"
}
```

#### GET /live
Liveness check endpoint.

**Response:**
```json
{
  "status": "alive"
}
```

### Checkout Session

#### POST /api/v1/checkout/session
Create a Stripe checkout session for one-time or recurring purchases.

**Headers:**
- `X-API-Key`: API key (required)

**Request Body:**
```json
{
  "user_id": "user_123",
  "project_id": 1,
  "price_id": "price_abc123",
  "mode": "payment",
  "success_url": "https://example.com/success",
  "cancel_url": "https://example.com/cancel"
}
```

**Parameters:**
- `user_id` (string, required): External user identifier
- `project_id` (integer, required): Project ID
- `price_id` (string, required): Stripe price ID
- `mode` (string, required): "payment" for one-time or "subscription" for recurring
- `success_url` (string, required): URL to redirect after successful payment
- `cancel_url` (string, required): URL to redirect after cancellation

**Response:**
```json
{
  "checkout_url": "https://checkout.stripe.com/pay/cs_test_..."
}
```

**Status Codes:**
- `200`: Success
- `400`: Bad request (missing or invalid parameters)
- `401`: Unauthorized (invalid API key)
- `404`: User or project not found

### Billing Portal Session

#### POST /api/v1/portal/session
Create a Stripe billing portal session for customer self-service.

**Headers:**
- `X-API-Key`: API key (required)

**Request Body:**
```json
{
  "user_id": "user_123",
  "project_id": 1,
  "return_url": "https://example.com/billing"
}
```

**Parameters:**
- `user_id` (string, required): External user identifier
- `project_id` (integer, required): Project ID
- `return_url` (string, required): URL to redirect after portal session

**Response:**
```json
{
  "portal_url": "https://billing.stripe.com/p/session/..."
}
```

**Status Codes:**
- `200`: Success
- `400`: Bad request (missing or invalid parameters)
- `401`: Unauthorized (invalid API key)
- `404`: User or Stripe customer not found

### Entitlements

#### GET /api/v1/entitlements
Retrieve user entitlements for a project.

**Headers:**
- `X-API-Key`: API key (required)

**Query Parameters:**
- `user_id` (string, required): External user identifier
- `project_id` (integer, required): Project ID

**Response:**
```json
{
  "entitlements": [
    {
      "feature_code": "premium",
      "active": true,
      "source": "subscription",
      "source_id": 1,
      "valid_from": "2024-01-01T00:00:00Z",
      "valid_to": "2024-02-01T00:00:00Z"
    }
  ]
}
```

**Status Codes:**
- `200`: Success
- `401`: Unauthorized (invalid API key)
- `403`: Forbidden (API key not authorized for project)
- `404`: User not found

### Administrative Functions

#### POST /api/v1/admin/grant
Manually grant an entitlement to a user.

**Headers:**
- `X-API-Key`: API key (required)

**Request Body:**
```json
{
  "user_id": "user_123",
  "project_id": 1,
  "feature_code": "premium",
  "valid_from": "2024-01-01T00:00:00Z",
  "valid_to": "2024-12-31T23:59:59Z",
  "reason": "Promotional grant"
}
```

**Parameters:**
- `user_id` (string, required): External user identifier
- `project_id` (integer, required): Project ID
- `feature_code` (string, required): Feature code to grant
- `valid_from` (datetime, optional): Start date (defaults to now)
- `valid_to` (datetime, optional): End date (defaults to null for lifetime)
- `reason` (string, optional): Reason for grant

**Response:**
```json
{
  "status": "granted",
  "entitlement": {
    "feature_code": "premium",
    "active": true,
    "source": "manual",
    "valid_from": "2024-01-01T00:00:00Z",
    "valid_to": "2024-12-31T23:59:59Z"
  }
}
```

**Status Codes:**
- `200`: Success
- `400`: Bad request (missing or invalid parameters)
- `401`: Unauthorized (invalid API key)
- `403`: Forbidden (API key not authorized for project)
- `404`: User not found

#### POST /api/v1/admin/revoke
Manually revoke an entitlement from a user.

**Headers:**
- `X-API-Key`: API key (required)

**Request Body:**
```json
{
  "user_id": "user_123",
  "project_id": 1,
  "feature_code": "premium",
  "reason": "Policy violation"
}
```

**Parameters:**
- `user_id` (string, required): External user identifier
- `project_id` (integer, required): Project ID
- `feature_code` (string, required): Feature code to revoke
- `reason` (string, optional): Reason for revoke

**Response:**
```json
{
  "status": "revoked"
}
```

**Status Codes:**
- `200`: Success
- `400`: Bad request (missing or invalid parameters)
- `401`: Unauthorized (invalid API key)
- `403`: Forbidden (API key not authorized for project)
- `404`: User not found

### Metrics

#### GET /api/v1/metrics/project/{project_id}/subscriptions
Get active subscription count for a project.

**Headers:**
- `X-API-Key`: API key (required)

**Path Parameters:**
- `project_id` (integer, required): Project ID

**Response:**
```json
{
  "project_id": 1,
  "active_subscriptions": 42
}
```

**Status Codes:**
- `200`: Success
- `401`: Unauthorized (invalid API key)
- `403`: Forbidden (API key not authorized for project)

#### GET /api/v1/metrics/project/{project_id}/revenue
Get total revenue for a project (from successful purchases).

**Headers:**
- `X-API-Key`: API key (required)

**Path Parameters:**
- `project_id` (integer, required): Project ID

**Response:**
```json
{
  "project_id": 1,
  "total_revenue": 12500.00,
  "currency": "usd"
}
```

**Status Codes:**
- `200`: Success
- `401`: Unauthorized (invalid API key)
- `403`: Forbidden (API key not authorized for project)

### Webhooks

#### POST /api/v1/webhooks/stripe
Receive and process Stripe webhook events.

**Headers:**
- `stripe-signature`: Stripe webhook signature (required)

**Request Body:**
Raw JSON payload from Stripe (event object).

**Response:**
```json
{
  "status": "ok"
}
```

**Status Codes:**
- `200`: Success (even if processing fails, to allow retry)
- `400`: Bad request (missing signature or invalid JSON)
- `401`: Unauthorized (invalid signature)

**Supported Event Types:**
- `checkout.session.completed`
- `payment_intent.succeeded`
- `payment_intent.payment_failed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_succeeded`
- `invoice.payment_failed`
- `charge.refunded`

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message"
}
```

## Rate Limiting

Currently no rate limiting is implemented. Consider adding rate limiting for production use.

## Versioning

API versioning is handled via URL path (`/api/v1`). Future versions will use `/api/v2`, etc.
