# Stripe Integration Tests

This directory contains integration tests that use the real Stripe API instead of mocks.

**⚠️ IMPORTANT: All tests run inside Docker containers. Never run tests directly on the host.**

## Setup

1. Ensure your `.env` file has valid Stripe test API keys:
   ```bash
   STRIPE_SECRET_KEY=sk_test_...
   STRIPE_PUBLISHABLE_KEY=pk_test_...
   ```

2. Set `USE_REAL_STRIPE=true` in your `.env` file OR export it before running Docker commands:
   ```bash
   # Option 1: Add to .env file
   echo "USE_REAL_STRIPE=true" >> .env
   
   # Option 2: Export before docker compose commands
   export USE_REAL_STRIPE=true
   ```

3. Start Docker containers:
   ```bash
   docker compose up -d
   ```

## Running Integration Tests (All in Docker)

### Run only Stripe integration tests:
```bash
# If USE_REAL_STRIPE is in .env or exported
make test-stripe

# Or directly:
docker compose exec -T app pytest tests/test_stripe_integration.py -v -m integration_stripe
```

### Run all tests (including Stripe integration):
```bash
# If USE_REAL_STRIPE is in .env or exported
make test-all

# Or directly:
docker compose exec -T app pytest tests/ -v --cov=src/billing_service --cov-report=html --cov-report=term
```

### Run all tests without Stripe integration (default - uses mocks):
```bash
make test
# Or:
docker compose exec -T app pytest tests/ -v
```

## Test Markers

- `@pytest.mark.integration_stripe`: Tests that use real Stripe API
- `@pytest.mark.unit`: Unit tests (mocked)
- `@pytest.mark.integration`: Other integration tests

## Important Notes

1. **Test Data Cleanup**: Integration tests automatically clean up Stripe test data they create (products, prices, customers, etc.)

2. **Rate Limits**: Stripe has rate limits on API calls. If tests fail with rate limit errors, wait a minute and retry.

3. **Test Mode Only**: These tests use Stripe test mode keys (starting with `sk_test_`). Never use production keys.

4. **Test Mode Card Data** (REQUIRED for payment method tests):
   - **Important**: Stripe now requires "Test mode card data" to be enabled in your Stripe Dashboard
   - Go to: **Settings > Integrations > Test mode card data**
   - Enable this setting to allow passing test card numbers in test mode
   - **Note**: Tests using `stripe_payment_method` fixture will automatically skip if this setting is not enabled
   - See: [STRIPE_TEST_MODE_SETUP.md](../docs/STRIPE_TEST_MODE_SETUP.md) for detailed instructions
   - Reference: https://support.stripe.com/questions/enabling-access-to-raw-card-data-apis

5. **Costs**: Stripe test mode is free - no charges are incurred.

6. **Idempotency**: Tests are designed to be idempotent and clean up after themselves, but manual cleanup may be needed if tests are interrupted.

## Fixtures

- `stripe_product`: Creates a real Stripe product (auto-cleanup)
- `stripe_price`: Creates a real Stripe price (auto-cleanup)
- `stripe_customer`: Creates a real Stripe customer (auto-cleanup)
- `stripe_payment_method`: Creates a real payment method (auto-cleanup)
- `stripe_checkout_session`: Creates a real checkout session

All fixtures are in `tests/conftest_stripe.py`.
