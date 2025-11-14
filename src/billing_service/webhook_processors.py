"""Base event processor and event router."""

import logging
from abc import ABC, abstractmethod

import stripe

from billing_service.cache import is_event_processed, mark_event_processed

logger = logging.getLogger(__name__)


class BaseEventProcessor(ABC):
    """Base class for Stripe event processors."""

    @abstractmethod
    def process(self, event: stripe.Event) -> None:
        """
        Process a Stripe event.

        Args:
            event: Stripe Event object

        Raises:
            Exception: If event processing fails
        """
        pass

    @abstractmethod
    def get_event_type(self) -> str:
        """
        Get the Stripe event type this processor handles.

        Returns:
            Event type string (e.g., "checkout.session.completed")
        """
        pass


class EventRouter:
    """Router for Stripe webhook events."""

    def __init__(self):
        """Initialize event router."""
        self._processors: dict[str, BaseEventProcessor] = {}

    def register_processor(self, processor: BaseEventProcessor) -> None:
        """
        Register an event processor.

        Args:
            processor: Event processor instance
        """
        event_type = processor.get_event_type()
        self._processors[event_type] = processor
        logger.info(f"Registered processor for event type: {event_type}")

    def process_event(self, event: stripe.Event) -> None:
        """
        Process a Stripe event by routing it to the appropriate processor.

        Args:
            event: Stripe Event object

        Raises:
            ValueError: If no processor is registered for the event type
        """
        event_type = event.type
        event_id = event.id

        # Check if event already processed (idempotency)
        if is_event_processed(event_id):
            logger.info(
                f"Event {event_id} already processed, skipping",
                extra={"event_id": event_id, "event_type": event_type},
            )
            return

        # Find processor for this event type
        processor = self._processors.get(event_type)

        if not processor:
            logger.warning(
                f"No processor registered for event type: {event_type}",
                extra={"event_id": event_id, "event_type": event_type},
            )
            # Mark as processed even if no processor (prevent retries)
            mark_event_processed(event_id)
            return

        try:
            # Process event
            logger.info(
                f"Processing event {event_id}",
                extra={"event_id": event_id, "event_type": event_type},
            )
            processor.process(event)

            # Mark as processed after successful processing
            mark_event_processed(event_id)
            logger.info(
                f"Successfully processed event {event_id}",
                extra={"event_id": event_id, "event_type": event_type},
            )

        except Exception as e:
            logger.error(
                f"Error processing event {event_id}",
                extra={
                    "event_id": event_id,
                    "event_type": event_type,
                    "error": str(e),
                },
                exc_info=True,
            )
            # Don't mark as processed on error - allow retry
            raise


# Global event router instance
event_router = EventRouter()
