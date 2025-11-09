"""Webhook endpoint for Stripe events."""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from billing_service.config import settings
from billing_service.database import get_db
from billing_service.models import WebhookEvent
from billing_service.webhook_processors import EVENT_PROCESSORS
from billing_service.webhook_verification import get_stripe_signature, verify_stripe_signature

router = APIRouter(prefix="/api/v1", tags=["webhooks"])


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Receive and process Stripe webhook events."""
    # Get raw payload
    payload = await request.body()

    # Get signature from headers
    signature = get_stripe_signature(request)
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing stripe-signature header",
        )

    # Verify signature
    if not verify_stripe_signature(payload, signature, settings.stripe_webhook_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    # Parse event data
    try:
        event_data = json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    event_id = event_data.get("id")
    event_type = event_data.get("type")

    if not event_id or not event_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing event id or type",
        )

    # Check if event already processed (idempotency)
    existing_event = db.query(WebhookEvent).filter(WebhookEvent.stripe_event_id == event_id).first()

    if existing_event:
        # Event already processed, return success
        if existing_event.processed:
            return {"status": "ok", "message": "Event already processed"}
        # If previously failed, try again
        # (This allows retry of failed events)

    # Store raw event
    webhook_event = WebhookEvent(
        stripe_event_id=event_id,
        event_type=event_type,
        raw_payload=payload.decode("utf-8"),
        processed=False,
    )
    db.add(webhook_event)
    db.commit()
    db.refresh(webhook_event)

    # Process event if we have a processor
    processor = EVENT_PROCESSORS.get(event_type)
    if processor:
        try:
            processor(event_data, db)
            webhook_event.processed = True  # type: ignore[assignment]
            webhook_event.processed_at = datetime.utcnow()  # type: ignore[assignment]
            webhook_event.error_message = None  # type: ignore[assignment]
            db.commit()
        except Exception as e:
            # Store error but don't fail the webhook (allows retry)
            webhook_event.error_message = str(e)  # type: ignore[assignment]
            db.commit()
            # Log error but return 200 to Stripe (we'll retry later)
            # In production, you might want to raise here or use a dead letter queue
    else:
        # Unknown event type, mark as processed to avoid reprocessing
        webhook_event.processed = True  # type: ignore[assignment]
        webhook_event.processed_at = datetime.utcnow()  # type: ignore[assignment]
        db.commit()

    return {"status": "ok"}
