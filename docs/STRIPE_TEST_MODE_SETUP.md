# Stripe Test Mode Setup

## Important: Raw Card Data in Test Mode

Stripe has notified us that passing full credit card numbers to their API, even in test mode, is discouraged. However, for integration testing, you may need to enable "Test mode card data" in your Stripe Dashboard.

## Recommended Setup

### Option 1: Enable Test Mode Card Data (For Integration Tests)

If you need to run integration tests that create PaymentMethods:

1. Log into Stripe Dashboard: https://dashboard.stripe.com/test/settings/integrations
2. Navigate to: **Settings > Integrations**
3. Scroll to **API settings**
4. Enable **"Test mode card data"**
5. Save changes

**Why this is needed**: Integration tests that create payment methods directly (e.g., `stripe.PaymentMethod.create()`) require this setting to use test card numbers.

**Security Note**: This only affects test mode. Your live mode remains secure. Stripe still recommends using Stripe Elements or other secure collection methods in production.

**Reference**: https://support.stripe.com/questions/enabling-access-to-raw-card-data-apis

### Option 2: Skip Payment Method Tests

If you prefer not to enable this setting:

- Tests using `stripe_payment_method` fixture will automatically skip
- Other integration tests (products, prices, customers, checkout sessions) will still run
- You can still test your application's payment flow using Stripe Elements

## Test Card Numbers

When "Test mode card data" is enabled, you can use these official Stripe test cards:

- **Visa (success)**: `4242 4242 4242 4242`
- **Visa (decline)**: `4000 0000 0000 0002`
- **Mastercard**: `5555 5555 5555 4444`
- See full list: https://stripe.com/docs/testing#cards

## Best Practices

1. **Production**: Always use Stripe Elements or other secure collection methods
2. **Development**: Use Stripe's test mode with test card numbers
3. **CI/CD**: Consider mocking Stripe API calls or using test mode with enabled card data
4. **Security**: Never commit real API keys or card numbers to version control

## Troubleshooting

### Error: "Sending credit card numbers directly to the Stripe API is generally unsafe"

**Solution**: Enable "Test mode card data" in Stripe Dashboard (see Option 1 above)

### Tests Skipping

If payment method tests are being skipped, check:
- Is `USE_REAL_STRIPE=true` set?
- Is "Test mode card data" enabled in Stripe Dashboard?
- Are you using test mode API keys (starting with `sk_test_`)?

### Alternative: Mock Stripe Calls

For unit tests, consider mocking Stripe API calls instead of using real API:

```python
@patch('stripe.PaymentMethod.create')
def test_payment_method_creation(mock_create):
    mock_create.return_value = Mock(id='pm_test123')
    # Test your code
```

## Questions?

- Stripe Support: https://support.stripe.com
- Stripe Testing Docs: https://stripe.com/docs/testing
- This Project: See `tests/README_STRIPE_INTEGRATION.md`

