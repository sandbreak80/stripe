"""Stripe webhook event processors."""

import logging
import uuid
from datetime import datetime

import stripe
from sqlalchemy.orm import Session

from billing_service.cache import invalidate_entitlements_cache
from billing_service.config import settings
from billing_service.database import SessionLocal
from billing_service.entitlements import recompute_and_store_entitlements
from billing_service.models import (
    Price,
    Project,
    Purchase,
    PurchaseStatus,
    Subscription,
    SubscriptionStatus,
)
from billing_service.webhook_processors import BaseEventProcessor

logger = logging.getLogger(__name__)


class CheckoutSessionCompletedProcessor(BaseEventProcessor):
    """Process checkout.session.completed events."""

    def get_event_type(self) -> str:
        """Return event type."""
        return "checkout.session.completed"

    def process(self, event: stripe.Event) -> None:
        """Process checkout.session.completed event."""
        session_obj = event.data.object
        db = SessionLocal()

        try:
            # Extract metadata - Stripe objects can be accessed as attributes
            metadata = getattr(session_obj, "metadata", {})
            if isinstance(metadata, dict):
                user_id = metadata.get("user_id")
                project_id_str = metadata.get("project_id")
            else:
                # Stripe object with metadata attributes
                user_id = getattr(metadata, "user_id", None) if metadata else None
                project_id_str = getattr(metadata, "project_id", None) if metadata else None

            if not user_id or not project_id_str:
                logger.error(
                    "Missing user_id or project_id in checkout session metadata",
                    extra={"event_id": event.id, "session_id": getattr(session_obj, "id", "unknown")},
                )
                return

            # Find project
            project = db.query(Project).filter(Project.project_id == project_id_str).first()
            if not project:
                logger.error(
                    f"Project not found: {project_id_str}",
                    extra={"event_id": event.id},
                )
                return

            mode = getattr(session_obj, "mode", None)
            if mode == "subscription":
                self._process_subscription(session_obj, user_id, project.id, db)  # type: ignore[arg-type]
            elif mode == "payment":
                self._process_payment(session_obj, user_id, project.id, db)  # type: ignore[arg-type]
            else:
                logger.warning(
                    f"Unknown checkout mode: {mode}",
                    extra={"event_id": event.id},
                )

        finally:
            db.close()

    def _process_subscription(
        self,
        session_obj: stripe.checkout.Session,
        user_id: str,
        project_id: uuid.UUID,
        db: Session,
    ) -> None:
        """Process subscription checkout."""
        subscription_id = getattr(session_obj, "subscription", None)
        if not subscription_id:
            session_id = getattr(session_obj, "id", "unknown")
            logger.error("No subscription ID in checkout session", extra={"session_id": session_id})
            return

        # Check if subscription already exists (idempotency)
        existing = (
            db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == subscription_id)
            .first()
        )
        if existing:
            logger.info(f"Subscription {subscription_id} already exists, skipping")
            return

        # Retrieve subscription from Stripe
        stripe.api_key = settings.stripe_secret_key
        try:
            stripe_subscription = stripe.Subscription.retrieve(subscription_id)
        except Exception as e:
            logger.error(f"Failed to retrieve subscription from Stripe: {e}")
            raise

        # Find price
        price_stripe_id = stripe_subscription.items.data[0].price.id
        price = db.query(Price).filter(Price.stripe_price_id == price_stripe_id).first()
        if not price:
            logger.error(f"Price not found: {price_stripe_id}")
            return

        # Map Stripe status to our enum
        status_map = {
            "active": SubscriptionStatus.ACTIVE,
            "trialing": SubscriptionStatus.TRIALING,
            "past_due": SubscriptionStatus.PAST_DUE,
            "canceled": SubscriptionStatus.CANCELED,
            "unpaid": SubscriptionStatus.UNPAID,
        }
        stripe_status = getattr(stripe_subscription, "status", "active")
        status = status_map.get(stripe_status, SubscriptionStatus.ACTIVE)

        # Create subscription
        # Handle canceled_at carefully - it can be None, int timestamp, or missing
        canceled_at_attr = getattr(stripe_subscription, "canceled_at", None)
        canceled_at_dt = None
        if canceled_at_attr is not None:
            # Only convert to datetime if canceled_at is a valid timestamp (int/float)
            try:
                canceled_at_dt = datetime.fromtimestamp(int(canceled_at_attr))
            except (ValueError, TypeError, OSError):
                # If conversion fails (None, invalid value, etc.), leave as None
                canceled_at_dt = None
        
        # Handle cancel_at_period_end - ensure it's a boolean
        cancel_at_period_end_attr = getattr(stripe_subscription, "cancel_at_period_end", False)
        cancel_at_period_end = bool(cancel_at_period_end_attr) if cancel_at_period_end_attr is not None else False
        
        subscription = Subscription(
            stripe_subscription_id=subscription_id,
            user_id=user_id,
            project_id=project_id,
            price_id=price.id,  # type: ignore[arg-type]
            status=status,
            current_period_start=datetime.fromtimestamp(getattr(stripe_subscription, "current_period_start", 0)),  # type: ignore[arg-type]
            current_period_end=datetime.fromtimestamp(getattr(stripe_subscription, "current_period_end", 0)),  # type: ignore[arg-type]
            cancel_at_period_end=cancel_at_period_end,
            canceled_at=canceled_at_dt,
        )

        db.add(subscription)
        db.commit()

        # Recompute entitlements
        recompute_and_store_entitlements(db, user_id, project_id)

        # Invalidate entitlements cache
        invalidate_entitlements_cache(user_id, str(project_id))

        logger.info(
            f"Created subscription {subscription_id} for user {user_id}",
            extra={"subscription_id": subscription_id, "user_id": user_id},
        )

    def _process_payment(
        self,
        session_obj: stripe.checkout.Session,
        user_id: str,
        project_id: uuid.UUID,
        db: Session,
    ) -> None:
        """Process one-time payment checkout."""
        payment_intent_id = getattr(session_obj, "payment_intent", None)
        if not payment_intent_id:
            session_id = getattr(session_obj, "id", "unknown")
            logger.error("No payment_intent in checkout session", extra={"session_id": session_id})
            return

        # Retrieve payment intent from Stripe
        stripe.api_key = settings.stripe_secret_key
        try:
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        except Exception as e:
            logger.error(f"Failed to retrieve payment intent from Stripe: {e}")
            raise

        # Get charge ID - payment_intent is a Stripe object
        charges = getattr(payment_intent.charges, "data", []) if hasattr(payment_intent, "charges") else []
        if not charges:
            logger.error(f"No charges found in payment intent {payment_intent_id}")
            return

        charge_id = charges[0].id

        # Check if purchase already exists (idempotency)
        existing = db.query(Purchase).filter(Purchase.stripe_charge_id == charge_id).first()
        if existing:
            logger.info(f"Purchase {charge_id} already exists, skipping")
            return

        # Find price from line items
        # For checkout sessions, we need to expand line items
        session_id = getattr(session_obj, "id", None)
        if not session_id:
            logger.error("No session ID found")
            return

        try:
            expanded_session = stripe.checkout.Session.retrieve(
                session_id,
                expand=["line_items"],
            )
            line_items = expanded_session.line_items.data if expanded_session.line_items else []
        except Exception as e:
            logger.error(f"Failed to retrieve checkout session: {e}")
            return

        if not line_items:
            logger.error("No line items in checkout session")
            return

        price_stripe_id = line_items[0].price.id
        price = db.query(Price).filter(Price.stripe_price_id == price_stripe_id).first()
        if not price:
            logger.error(f"Price not found: {price_stripe_id}")
            return

        # Determine status
        payment_status = getattr(payment_intent, "status", "pending")
        status = PurchaseStatus.SUCCEEDED if payment_status == "succeeded" else PurchaseStatus.PENDING

        # Create purchase
        purchase = Purchase(
            stripe_charge_id=charge_id,
            user_id=user_id,
            project_id=project_id,
            price_id=price.id,  # type: ignore[arg-type,union-attr]  # Price is guaranteed to exist after check
            amount=getattr(payment_intent, "amount", 0),
            currency=getattr(payment_intent, "currency", "usd"),
            status=status,
            valid_from=datetime.utcnow(),
            valid_to=None,  # Lifetime by default, can be set based on product config
        )

        db.add(purchase)
        db.commit()

        # Recompute entitlements
        recompute_and_store_entitlements(db, user_id, project_id)

        # Invalidate entitlements cache
        invalidate_entitlements_cache(user_id, str(project_id))

        logger.info(
            f"Created purchase {charge_id} for user {user_id}",
            extra={"charge_id": charge_id, "user_id": user_id},
        )


class InvoicePaymentSucceededProcessor(BaseEventProcessor):
    """Process invoice.payment_succeeded events."""

    def get_event_type(self) -> str:
        """Return event type."""
        return "invoice.payment_succeeded"

    def process(self, event: stripe.Event) -> None:
        """Process invoice.payment_succeeded event."""
        invoice = event.data.object
        db = SessionLocal()

        try:
            subscription_id = getattr(invoice, "subscription", None)
            if not subscription_id:
                logger.warning("Invoice has no subscription, skipping")
                return

            # Find subscription
            subscription = (
                db.query(Subscription)
                .filter(Subscription.stripe_subscription_id == subscription_id)
                .first()
            )

            if not subscription:
                logger.warning(f"Subscription not found: {subscription_id}")
                return

            # Update subscription period
            period_start = datetime.fromtimestamp(getattr(invoice, "period_start", 0))
            period_end = datetime.fromtimestamp(getattr(invoice, "period_end", 0))

            subscription.current_period_start = period_start  # type: ignore[assignment]
            subscription.current_period_end = period_end  # type: ignore[assignment]
            subscription.status = SubscriptionStatus.ACTIVE  # type: ignore[assignment]

            db.commit()

            # Recompute entitlements
            recompute_and_store_entitlements(db, str(subscription.user_id), subscription.project_id)  # type: ignore[arg-type]

            # Invalidate entitlements cache
            invalidate_entitlements_cache(str(subscription.user_id), str(subscription.project_id))

            logger.info(
                f"Updated subscription {subscription_id} period",
                extra={"subscription_id": subscription_id},
            )

        finally:
            db.close()


class CustomerSubscriptionUpdatedProcessor(BaseEventProcessor):
    """Process customer.subscription.updated events."""

    def get_event_type(self) -> str:
        """Return event type."""
        return "customer.subscription.updated"

    def process(self, event: stripe.Event) -> None:
        """Process customer.subscription.updated event."""
        stripe_subscription = event.data.object
        db = SessionLocal()

        try:
            subscription_id = getattr(stripe_subscription, "id", None)
            if not subscription_id:
                logger.error("Subscription ID not found in event")
                return

            # Find subscription
            subscription = (
                db.query(Subscription)
                .filter(Subscription.stripe_subscription_id == subscription_id)
                .first()
            )

            if not subscription:
                logger.warning(f"Subscription not found: {subscription_id}")
                return

            # Map Stripe status to our enum
            status_map = {
                "active": SubscriptionStatus.ACTIVE,
                "trialing": SubscriptionStatus.TRIALING,
                "past_due": SubscriptionStatus.PAST_DUE,
                "canceled": SubscriptionStatus.CANCELED,
                "unpaid": SubscriptionStatus.UNPAID,
            }
            stripe_status = getattr(stripe_subscription, "status", "active")
            status = status_map.get(stripe_status, SubscriptionStatus.ACTIVE)

            # Update subscription
            subscription.status = status  # type: ignore[assignment]
            subscription.current_period_start = datetime.fromtimestamp(getattr(stripe_subscription, "current_period_start", 0))  # type: ignore[assignment]
            subscription.current_period_end = datetime.fromtimestamp(getattr(stripe_subscription, "current_period_end", 0))  # type: ignore[assignment]
            subscription.cancel_at_period_end = getattr(stripe_subscription, "cancel_at_period_end", False) or False  # type: ignore[assignment]
            canceled_at_ts = getattr(stripe_subscription, "canceled_at", None)
            subscription.canceled_at = datetime.fromtimestamp(canceled_at_ts) if canceled_at_ts else None  # type: ignore[assignment]

            db.commit()

            # Recompute entitlements
            recompute_and_store_entitlements(db, str(subscription.user_id), subscription.project_id)  # type: ignore[arg-type]

            # Invalidate entitlements cache
            invalidate_entitlements_cache(str(subscription.user_id), str(subscription.project_id))

            logger.info(
                f"Updated subscription {subscription_id}",
                extra={"subscription_id": subscription_id, "status": status.value},
            )

        finally:
            db.close()


class CustomerSubscriptionDeletedProcessor(BaseEventProcessor):
    """Process customer.subscription.deleted events."""

    def get_event_type(self) -> str:
        """Return event type."""
        return "customer.subscription.deleted"

    def process(self, event: stripe.Event) -> None:
        """Process customer.subscription.deleted event."""
        stripe_subscription = event.data.object
        db = SessionLocal()

        try:
            subscription_id = getattr(stripe_subscription, "id", None)
            if not subscription_id:
                logger.error("Subscription ID not found in event")
                return

            # Find subscription
            subscription = (
                db.query(Subscription)
                .filter(Subscription.stripe_subscription_id == subscription_id)
                .first()
            )

            if not subscription:
                logger.warning(f"Subscription not found: {subscription_id}")
                return

            user_id = str(subscription.user_id)
            project_id = subscription.project_id

            # Mark as canceled
            subscription.status = SubscriptionStatus.CANCELED  # type: ignore[assignment]
            subscription.canceled_at = datetime.utcnow()  # type: ignore[assignment]
            subscription.cancel_at_period_end = False  # type: ignore[assignment]

            db.commit()

            # Recompute entitlements
            recompute_and_store_entitlements(db, user_id, project_id)  # type: ignore[arg-type]

            # Invalidate entitlements cache
            invalidate_entitlements_cache(user_id, str(project_id))

            logger.info(
                f"Marked subscription {subscription_id} as canceled",
                extra={"subscription_id": subscription_id},
            )

        finally:
            db.close()


class ChargeRefundedProcessor(BaseEventProcessor):
    """Process charge.refunded events."""

    def get_event_type(self) -> str:
        """Return event type."""
        return "charge.refunded"

    def process(self, event: stripe.Event) -> None:
        """Process charge.refunded event."""
        charge = event.data.object
        db = SessionLocal()

        try:
            charge_id = getattr(charge, "id", None)
            if not charge_id:
                logger.error("Charge ID not found in event")
                return

            # Find purchase
            purchase = db.query(Purchase).filter(Purchase.stripe_charge_id == charge_id).first()

            if not purchase:
                logger.warning(f"Purchase not found for charge: {charge_id}")
                return

            # Update purchase status
            purchase.status = PurchaseStatus.REFUNDED  # type: ignore[assignment]
            purchase.refunded_at = datetime.utcnow()  # type: ignore[assignment]

            db.commit()

            # Recompute entitlements
            recompute_and_store_entitlements(db, str(purchase.user_id), purchase.project_id)  # type: ignore[arg-type]

            # Invalidate entitlements cache
            invalidate_entitlements_cache(str(purchase.user_id), str(purchase.project_id))

            logger.info(
                f"Marked purchase {charge_id} as refunded",
                extra={"charge_id": charge_id},
            )

        finally:
            db.close()
