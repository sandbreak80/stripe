# Stripe Security Notification - Raw Card Data in Test Mode

## Summary

Stripe has sent a notification indicating that full credit card numbers are being passed to their API in test mode. This is a security best practice reminder from Stripe.

## What Happened

When running integration tests that create PaymentMethods, the code passes test card numbers (like `4242424242424242`) directly to Stripe's API. Even though these are test cards and test mode is safe, Stripe discourages this practice because:

1. It can expose sensitive data if mishandled
2. It requires meeting PCI compliance requirements
3. It makes fraud protection harder

## Solution Implemented

### 1. Error Handling
The `stripe_payment_method` fixture now:
- Catches `CardError` and `InvalidRequestError` exceptions related to raw card data
- Automatically skips tests with a helpful message if "Test mode card data" is not enabled
- Provides clear instructions on how to enable it

### 2. Documentation
- Added `docs/STRIPE_TEST_MODE_SETUP.md` with detailed setup instructions
- Updated `tests/README_STRIPE_INTEGRATION.md` with requirements
- Updated `docs/SETUP.md` with setup steps

## What You Need to Do

### Option 1: Enable Test Mode Card Data (Recommended for Integration Tests)

If you want to run integration tests that create PaymentMethods:

1. Go to [Stripe Dashboard > Settings > Integrations](https://dashboard.stripe.com/test/settings/integrations)
2. Scroll to **API settings**
3. Enable **"Test mode card data"**
4. Save changes

**Security Note**: This only affects test mode. Your live/production mode remains completely secure.

### Option 2: Skip Payment Method Tests

If you prefer not to enable this setting:
- Tests using `stripe_payment_method` fixture will automatically skip
- Other integration tests (products, prices, customers, checkout sessions) will still run
- You can still test your application using Stripe Elements or other secure methods

### Option 3: Use Stripe Elements (Production Best Practice)

For production applications, always use:
- Stripe Elements (secure frontend card collection)
- Stripe.js (secure tokenization)
- Payment Intents API (modern payment flow)

**Never pass raw card numbers in production.**

## Files Changed

- `tests/conftest_stripe.py`: Added error handling and documentation
- `tests/README_STRIPE_INTEGRATION.md`: Added setup requirements
- `docs/SETUP.md`: Added setup steps
- `docs/STRIPE_TEST_MODE_SETUP.md`: Created detailed guide (new file)

## References

- Stripe Support: https://support.stripe.com/questions/enabling-access-to-raw-card-data-apis
- Stripe Testing Guide: https://stripe.com/docs/testing
- Stripe Elements: https://stripe.com/docs/payments/accept-a-payment
- PCI Compliance: https://stripe.com/docs/security/guide

## Status

✅ **Fixed**: Code now handles Stripe's requirements gracefully
✅ **Documented**: Setup instructions added to all relevant docs
✅ **User-Friendly**: Tests skip automatically with helpful messages if setting not enabled

---

**Note**: This is Stripe's first-time notification. They won't email you again about this. The code is now compliant with their recommendations while still allowing integration tests to run when properly configured.

