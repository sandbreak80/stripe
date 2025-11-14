"""Stripe webhook endpoint."""

import logging

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from billing_service.webhook_processors import event_router
from billing_service.webhook_verification import (
    get_webhook_payload,
    get_webhook_signature,
    verify_stripe_signature,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/stripe")
async def stripe_webhook(request: Request) -> JSONResponse:
    """
    Handle Stripe webhook events.

    This endpoint:
    1. Verifies the webhook signature
    2. Checks for duplicate events (idempotency)
    3. Routes event to appropriate processor
    4. Returns 200 OK immediately

    Stripe will retry failed webhooks automatically.
    """
    try:
        # Get signature and payload
        signature = await get_webhook_signature(request)
        payload = await get_webhook_payload(request)

        # Verify signature and construct event
        event = verify_stripe_signature(payload, signature)

        if not event:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to verify webhook signature",
            )

        # Log event received
        logger.info(
            "Stripe webhook received",
            extra={
                "event_id": event.id,
                "event_type": event.type,
                "livemode": event.livemode,
            },
        )

        # Process event (idempotent)
        try:
            event_router.process_event(event)
        except ValueError as e:
            # Permanent error (e.g., invalid data, missing required fields)
            # Mark as processed to prevent retry storms
            logger.error(
                f"Permanent error processing event {event.id}: {e}",
                extra={"event_id": event.id, "error": str(e)},
                exc_info=True,
            )
            from billing_service.cache import mark_event_processed
            mark_event_processed(event.id)
            # Return 200 to acknowledge receipt and prevent retries
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"received": True, "event_id": event.id, "error": "Event processing failed permanently"},
            )
        except Exception as e:
            # Transient error (e.g., database connection, external service)
            # Don't mark as processed - allow Stripe retry
            logger.error(
                f"Transient error processing event {event.id}: {e}",
                extra={"event_id": event.id, "error": str(e)},
                exc_info=True,
            )
            # Return 500 to trigger Stripe retry for transient errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing event: {str(e)}",
            ) from e

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"received": True, "event_id": event.id},
        )

    except HTTPException:
        # Re-raise HTTP exceptions (already properly formatted)
        raise
    except Exception as e:
        # Log unexpected errors
        logger.error(
            "Unexpected error processing webhook",
            extra={"error": str(e)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error processing webhook",
        ) from e
