"""Alert processing engine."""

import json
import logging
from datetime import datetime

from src.db.models import AlertSubscription, AlertEvent, DailyMetric
from src.db.repositories.alert_repository import AlertRepository, AlertEventRepository
from src.alerts.triggers import get_trigger, TriggerResult
from src.alerts.channels import get_channel

logger = logging.getLogger(__name__)


class AlertEngine:
    """
    Main alert processing engine.

    Processes metrics, evaluates triggers, and dispatches notifications.
    """

    def __init__(
        self,
        alert_repo: AlertRepository,
        event_repo: AlertEventRepository,
    ):
        self.alert_repo = alert_repo
        self.event_repo = event_repo

    async def process_product_metrics(
        self,
        product_id: str,
        current_metric: DailyMetric,
        previous_metric: DailyMetric | None,
    ) -> list[AlertEvent]:
        """
        Process metrics for a product and trigger any matching alerts.

        Args:
            product_id: Product UUID as string
            current_metric: Latest metric data
            previous_metric: Previous metric data (for comparison)

        Returns:
            List of triggered alert events
        """
        import uuid as uuid_module

        triggered_events = []

        # Get all active subscriptions for this product
        subscriptions = await self.alert_repo.get_product_subscriptions(
            uuid_module.UUID(product_id)
        )

        for subscription in subscriptions:
            event = await self._evaluate_subscription(
                subscription, current_metric, previous_metric
            )
            if event:
                triggered_events.append(event)

        return triggered_events

    async def process_all_subscriptions(
        self,
        metrics_by_product: dict[str, tuple[DailyMetric, DailyMetric | None]],
    ) -> list[AlertEvent]:
        """
        Process all active subscriptions against latest metrics.

        Args:
            metrics_by_product: Dict of product_id -> (current, previous) metrics

        Returns:
            List of all triggered events
        """
        all_events = []

        for product_id, (current, previous) in metrics_by_product.items():
            events = await self.process_product_metrics(product_id, current, previous)
            all_events.extend(events)

        return all_events

    async def _evaluate_subscription(
        self,
        subscription: AlertSubscription,
        current_metric: DailyMetric,
        previous_metric: DailyMetric | None,
    ) -> AlertEvent | None:
        """Evaluate a single subscription against metrics."""
        trigger = get_trigger(subscription.alert_type)
        if not trigger:
            logger.warning(f"Unknown alert type: {subscription.alert_type}")
            return None

        result = trigger.evaluate(subscription, current_metric, previous_metric)
        if not result or not result.triggered:
            return None

        # Create event
        event = await self.event_repo.create(
            subscription_id=subscription.id,
            event_type=result.event_type,
            event_data=result.event_data,
            previous_value=result.previous_value,
            current_value=result.current_value,
        )

        # Send notification
        await self._send_notification(subscription, event, result.message)

        return event

    async def _send_notification(
        self,
        subscription: AlertSubscription,
        event: AlertEvent,
        message: str,
    ) -> bool:
        """Send notification via configured channel."""
        channel = get_channel(subscription.notification_channel)
        if not channel:
            logger.warning(f"Unknown channel: {subscription.notification_channel}")
            return False

        try:
            success = await channel.send(subscription, event, message)
            if success:
                logger.info(
                    f"Alert sent via {subscription.notification_channel}: {message[:50]}"
                )
            return success
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False

    async def get_user_alerts(
        self,
        user_id: str,
        limit: int = 50,
        unacknowledged_only: bool = False,
    ) -> list[dict]:
        """
        Get alerts for a user.

        Returns list of alert dictionaries with subscription and event info.
        """
        events = await self.event_repo.get_user_events(
            user_id, limit, unacknowledged_only
        )

        alerts = []
        for event in events:
            alerts.append({
                "event_id": str(event.id),
                "subscription_id": str(event.subscription_id),
                "event_type": event.event_type,
                "message": self._format_event_message(event),
                "data": json.loads(event.event_data),
                "triggered_at": event.triggered_at.isoformat(),
                "acknowledged": event.acknowledged,
            })

        return alerts

    def _format_event_message(self, event: AlertEvent) -> str:
        """Format event into human-readable message."""
        data = json.loads(event.event_data)

        if event.event_type == "price_below_threshold":
            return f"💰 Price dropped to ${data.get('current_price', 0):.2f}"
        elif event.event_type == "price_drop_percent":
            return f"📉 Price dropped {data.get('drop_percent', 0):.1f}%"
        elif event.event_type == "stockout":
            return "🔴 Product is OUT OF STOCK"
        elif event.event_type == "back_in_stock":
            return f"🟢 Product is BACK IN STOCK at ${data.get('current_price', 0):.2f}"
        elif event.event_type == "rank_improving":
            return f"🚀 Rank improved by {abs(data.get('change_percent', 0)):.1f}%"
        elif event.event_type == "rank_declining":
            return f"📉 Rank declined by {abs(data.get('change_percent', 0)):.1f}%"
        elif event.event_type == "arbitrage_opportunity":
            return f"🌍 Arbitrage: {data.get('margin_percent', 0):.1f}% margin"
        else:
            return f"Alert: {event.event_type}"


class AlertScheduler:
    """Schedules and runs alert processing jobs."""

    def __init__(self, alert_engine: AlertEngine):
        self.engine = alert_engine

    async def run_hourly_check(self) -> dict:
        """
        Run hourly alert check.

        Returns summary of processing results.
        """
        # In production, this would:
        # 1. Fetch latest metrics for all products with active subscriptions
        # 2. Process all subscriptions
        # 3. Return summary

        return {
            "status": "completed",
            "processed_at": datetime.utcnow().isoformat(),
            "subscriptions_checked": 0,
            "alerts_triggered": 0,
        }

    async def run_daily_digest(self) -> dict:
        """
        Send daily digest of alerts to users.

        Returns summary of digests sent.
        """
        # In production, would aggregate daily events and send digest

        return {
            "status": "completed",
            "processed_at": datetime.utcnow().isoformat(),
            "digests_sent": 0,
        }
