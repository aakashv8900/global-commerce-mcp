"""Notification channels for alert delivery."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
import logging
from typing import Any

import httpx

from src.db.models import AlertEvent, AlertSubscription


logger = logging.getLogger(__name__)


@dataclass
class NotificationPayload:
    """Payload for notifications."""
    subscription_id: str
    event_id: str
    event_type: str
    message: str
    event_data: dict
    timestamp: str


class NotificationChannelBase(ABC):
    """Base class for notification channels."""

    @property
    @abstractmethod
    def channel_type(self) -> str:
        """Return the channel type identifier."""
        pass

    @abstractmethod
    async def send(
        self,
        subscription: AlertSubscription,
        event: AlertEvent,
        message: str,
    ) -> bool:
        """
        Send notification via this channel.

        Returns True if successful, False otherwise.
        """
        pass


class WebhookChannel(NotificationChannelBase):
    """Send notifications via HTTP webhook."""

    def __init__(self, timeout: float = 10.0, retries: int = 3):
        self.timeout = timeout
        self.retries = retries

    @property
    def channel_type(self) -> str:
        return "webhook"

    async def send(
        self,
        subscription: AlertSubscription,
        event: AlertEvent,
        message: str,
    ) -> bool:
        if not subscription.webhook_url:
            logger.warning(f"No webhook URL for subscription {subscription.id}")
            return False

        payload = NotificationPayload(
            subscription_id=str(subscription.id),
            event_id=str(event.id),
            event_type=event.event_type,
            message=message,
            event_data=json.loads(event.event_data),
            timestamp=event.triggered_at.isoformat(),
        )

        for attempt in range(self.retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        subscription.webhook_url,
                        json={
                            "subscription_id": payload.subscription_id,
                            "event_id": payload.event_id,
                            "event_type": payload.event_type,
                            "message": payload.message,
                            "data": payload.event_data,
                            "timestamp": payload.timestamp,
                        },
                        headers={"Content-Type": "application/json"},
                    )

                    if response.status_code < 300:
                        logger.info(f"Webhook sent successfully to {subscription.webhook_url}")
                        return True
                    else:
                        logger.warning(
                            f"Webhook returned {response.status_code}: {response.text[:100]}"
                        )

            except httpx.RequestError as e:
                logger.error(f"Webhook request failed (attempt {attempt + 1}): {e}")

            except Exception as e:
                logger.error(f"Unexpected error sending webhook: {e}")
                break

        return False


class MCPChannel(NotificationChannelBase):
    """
    Send notifications via MCP protocol.

    This stores alerts for retrieval via MCP tools.
    """

    # In-memory alert queue (would be Redis in production)
    _pending_alerts: dict[str, list[NotificationPayload]] = {}

    @property
    def channel_type(self) -> str:
        return "mcp"

    async def send(
        self,
        subscription: AlertSubscription,
        event: AlertEvent,
        message: str,
    ) -> bool:
        try:
            payload = NotificationPayload(
                subscription_id=str(subscription.id),
                event_id=str(event.id),
                event_type=event.event_type,
                message=message,
                event_data=json.loads(event.event_data),
                timestamp=event.triggered_at.isoformat(),
            )

            user_id = subscription.user_id
            if user_id not in self._pending_alerts:
                self._pending_alerts[user_id] = []

            self._pending_alerts[user_id].append(payload)
            logger.info(f"MCP alert queued for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to queue MCP alert: {e}")
            return False

    @classmethod
    def get_pending_alerts(cls, user_id: str) -> list[NotificationPayload]:
        """Get pending alerts for a user."""
        return cls._pending_alerts.get(user_id, [])

    @classmethod
    def clear_alerts(cls, user_id: str) -> int:
        """Clear pending alerts for a user. Returns count cleared."""
        count = len(cls._pending_alerts.get(user_id, []))
        cls._pending_alerts[user_id] = []
        return count

    @classmethod
    def get_alert_count(cls, user_id: str) -> int:
        """Get count of pending alerts for a user."""
        return len(cls._pending_alerts.get(user_id, []))


class EmailChannel(NotificationChannelBase):
    """
    Send notifications via email (placeholder implementation).

    Would integrate with SendGrid, SES, etc. in production.
    """

    @property
    def channel_type(self) -> str:
        return "email"

    async def send(
        self,
        subscription: AlertSubscription,
        event: AlertEvent,
        message: str,
    ) -> bool:
        # Placeholder - would integrate with email service
        logger.info(f"Email notification would be sent: {message[:100]}")
        return True


# Channel registry
CHANNEL_REGISTRY: dict[str, type[NotificationChannelBase]] = {
    "webhook": WebhookChannel,
    "mcp": MCPChannel,
    "email": EmailChannel,
}


def get_channel(channel_type: str) -> NotificationChannelBase | None:
    """Get channel instance by type."""
    channel_class = CHANNEL_REGISTRY.get(channel_type)
    if channel_class:
        return channel_class()
    return None
