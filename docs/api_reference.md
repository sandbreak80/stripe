# API Reference

**Version:** 1.0  
**Last Updated:** November 11, 2025  
**Base URL:** `https://billing.example.com` (production) / `http://localhost:8000` (development)

## Authentication

All API endpoints (except health checks and webhooks) require authentication using a project-scoped API key.

### Authentication Header

```
Authorization: Bearer <project_api_key>
```

The API key is provided when a project is created. It should be kept secure and not exposed in client-side code.

## Endpoints

### Health Checks

#### GET /healthz

Health check endpoint for load balancers.

**Response:**
```json
{
  "status": "healthy"
}
```

**Status Codes:**
- `200 OK`: Service is healthy

#### GET /ready

Readiness check endpoint. Verifies database connectivity.

**Response:**
```json
{
  "status": "ready"
}
```

**Status Codes:**
- `200 OK`: Service is ready
- `503 Service Unavailable`: Database connection failed

#### GET /live

Liveness check endpoint.

**Response:**
```json
{
  "status": "alive"
}
```

**Status Codes:**
- `200 OK`: Service is alive

---

### Checkout

#### POST /api/v1/checkout/create

Create a Stripe checkout session for a subscription or one-time payment.

**Authentication:** Required (Project API Key)

**Request Body:**
```json
{
  "user_id": "user_12345",
  "price_id": "550e8400-e29b-41d4-a716-446655440000",
  "mode": "subscription",
  "success_url": "https://yourapp.com/success?session_id={CHECKOUT_SESSION_ID}",
  "cancel_url": "https://yourapp.com/pricing"
}
```

**Parameters:**
- `user_id` (string, required): User identifier from your micro-app
- `price_id` (UUID, required): Price UUID to purchase (must belong to your project)
- `mode` (string, required): Either `"subscription"` or `"payment"`
- `success_url` (string, required): URL to redirect after successful payment
- `cancel_url` (string, required): URL to redirect if payment is cancelled

**Response:**
```json
{
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_abc123...",
  "session_id": "cs_test_abc123",
  "expires_at": "2025-11-11T14:30:00Z"
}
```

**Status Codes:**
- `200 OK`: Checkout session created successfully
- `400 Bad Request`: Invalid request (e.g., archived price)
- `401 Unauthorized`: Invalid or missing API key
- `404 Not Found`: Price not found
- `500 Internal Server Error`: Stripe API error

**Example:**
```bash
curl -X POST https://billing.example.com/api/v1/checkout/create \
  -H "Authorization: Bearer proj_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_12345",
    "price_id": "550e8400-e29b-41d4-a716-446655440000",
    "mode": "subscription",
    "success_url": "https://yourapp.com/success",
    "cancel_url": "https://yourapp.com/pricing"
  }'
```

---

### Entitlements

#### GET /api/v1/entitlements

Query entitlements for a user in your project.

**Authentication:** Required (Project API Key)

**Query Parameters:**
- `user_id` (string, required): User identifier

**Response:**
```json
{
  "user_id": "user_12345",
  "project_id": "my-project",
  "entitlements": [
    {
      "feature_code": "premium_export",
      "is_active": true,
      "valid_from": "2025-11-01T00:00:00Z",
      "valid_to": "2025-12-01T00:00:00Z",
      "source": "subscription"
    },
    {
      "feature_code": "api_access",
      "is_active": true,
      "valid_from": "2025-10-15T00:00:00Z",
      "valid_to": null,
      "source": "purchase"
    }
  ],
  "checked_at": "2025-11-11T14:30:00Z"
}
```

**Response Fields:**
- `user_id`: User identifier
- `project_id`: Project identifier
- `entitlements`: Array of entitlement objects
  - `feature_code`: Feature identifier (e.g., "premium_export")
  - `is_active`: Whether entitlement is currently active
  - `valid_from`: Access start timestamp
  - `valid_to`: Access end timestamp (null = indefinite/lifetime)
  - `source`: Source of entitlement (`"subscription"`, `"purchase"`, or `"manual"`)
- `checked_at`: Timestamp when entitlements were checked

**Status Codes:**
- `200 OK`: Entitlements retrieved successfully
- `401 Unauthorized`: Invalid or missing API key
- `500 Internal Server Error`: Database error

**Example:**
```bash
curl -X GET "https://billing.example.com/api/v1/entitlements?user_id=user_12345" \
  -H "Authorization: Bearer proj_your_api_key_here"
```

---

### Customer Portal

#### POST /api/v1/portal/create-session

Create a Stripe Customer Portal session for self-service billing management.

**Authentication:** Required (Project API Key)

**Request Body:**
```json
{
  "user_id": "user_12345",
  "return_url": "https://yourapp.com/billing"
}
```

**Parameters:**
- `user_id` (string, required): User identifier
- `return_url` (string, required): URL to return to after portal session

**Response:**
```json
{
  "portal_url": "https://billing.stripe.com/p/session_abc123...",
  "expires_at": "2025-11-11T15:30:00Z"
}
```

**Status Codes:**
- `200 OK`: Portal session created successfully
- `401 Unauthorized`: Invalid or missing API key
- `404 Not Found`: No active subscription found for user
- `500 Internal Server Error`: Stripe API error

**Example:**
```bash
curl -X POST https://billing.example.com/api/v1/portal/create-session \
  -H "Authorization: Bearer proj_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_12345",
    "return_url": "https://yourapp.com/billing"
  }'
```

---

### Webhooks

#### POST /api/v1/webhooks/stripe

Webhook endpoint for Stripe events. This endpoint is called by Stripe, not by micro-apps.

**Authentication:** Stripe signature verification (not API key)

**Request Headers:**
- `Stripe-Signature`: Stripe webhook signature

**Request Body:**
Raw JSON payload from Stripe

**Status Codes:**
- `200 OK`: Event processed successfully
- `400 Bad Request`: Invalid payload
- `401 Unauthorized`: Invalid signature
- `500 Internal Server Error`: Processing error

**Note:** This endpoint is configured in Stripe Dashboard. Do not call it directly from micro-apps.

---

## Error Responses

All endpoints may return error responses in the following format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common Error Codes

- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Missing or invalid API key
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

## Rate Limiting

Currently, no rate limiting is implemented. Future versions may include rate limiting per API key.

## Versioning

API versioning is handled via URL path (`/api/v1/`). Future breaking changes will increment the version number.

## Webhooks

Stripe webhooks are automatically processed by the service. Configure your webhook endpoint in Stripe Dashboard:

- **Endpoint URL:** `https://billing.example.com/api/v1/webhooks/stripe`
- **Events to listen for:**
  - `checkout.session.completed`
  - `invoice.payment_succeeded`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `charge.refunded`

## Integration Examples

### Python Example

```python
import requests

API_BASE = "https://billing.example.com"
API_KEY = "proj_your_api_key_here"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Create checkout session
response = requests.post(
    f"{API_BASE}/api/v1/checkout/create",
    headers=headers,
    json={
        "user_id": "user_12345",
        "price_id": "550e8400-e29b-41d4-a716-446655440000",
        "mode": "subscription",
        "success_url": "https://yourapp.com/success",
        "cancel_url": "https://yourapp.com/pricing"
    }
)
checkout = response.json()
print(f"Checkout URL: {checkout['checkout_url']}")

# Check entitlements
response = requests.get(
    f"{API_BASE}/api/v1/entitlements",
    headers=headers,
    params={"user_id": "user_12345"}
)
entitlements = response.json()
print(f"User has {len(entitlements['entitlements'])} active entitlements")
```

### JavaScript Example

```javascript
const API_BASE = 'https://billing.example.com';
const API_KEY = 'proj_your_api_key_here';

async function createCheckout(userId, priceId) {
  const response = await fetch(`${API_BASE}/api/v1/checkout/create`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      user_id: userId,
      price_id: priceId,
      mode: 'subscription',
      success_url: 'https://yourapp.com/success',
      cancel_url: 'https://yourapp.com/pricing'
    })
  });
  return response.json();
}

async function checkEntitlements(userId) {
  const response = await fetch(
    `${API_BASE}/api/v1/entitlements?user_id=${userId}`,
    {
      headers: {
        'Authorization': `Bearer ${API_KEY}`
      }
    }
  );
  return response.json();
}
```
