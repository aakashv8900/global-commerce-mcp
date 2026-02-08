"""Alert repository for alert subscriptions and events."""

import uuid
import json
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AlertSubscription, AlertEvent


class AlertRepository:
    """Repository for alert subscriptions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_subscription(
        self,
        user_id: str,
        alert_type: str,
        product_id: uuid.UUID | None = None,
        brand_id: uuid.UUID | None = None,
        category: str | None = None,
        platform: str = "amazon_us",
        threshold_value: Decimal | None = None,
        threshold_percent: float | None = None,
        notification_channel: str = "mcp",
        webhook_url: str | None = None,
    ) -> AlertSubscription:
        """Create a new alert subscription."""
        subscription = AlertSubscription(
            user_id=user_id,
            alert_type=alert_type,
            product_id=product_id,
            brand_id=brand_id,
            category=category,
            platform=platform,
            threshold_value=threshold_value,
            threshold_percent=threshold_percent,
            notification_channel=notification_channel,
            webhook_url=webhook_url,
            is_active=True,
        )
        self.session.add(subscription)
        await self.session.flush()
        return subscription

    async def get_by_id(self, subscription_id: uuid.UUID) -> AlertSubscription | None:
        """Get subscription by ID."""
        result = await self.session.execute(
            select(AlertSubscription).where(AlertSubscription.id == subscription_id)
        )
        return result.scalar_one_or_none()

    async def get_user_subscriptions(
        self,
        user_id: str,
        active_only: bool = True,
    ) -> list[AlertSubscription]:
        """Get all subscriptions for a user."""
        query = select(AlertSubscription).where(AlertSubscription.user_id == user_id)

        if active_only:
            query = query.where(AlertSubscription.is_active == True)

        query = query.order_by(AlertSubscription.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_active_by_type(
        self,
        alert_type: str,
        platform: str | None = None,
    ) -> list[AlertSubscription]:
        """Get all active subscriptions of a type."""
        query = select(AlertSubscription).where(
            and_(
                AlertSubscription.alert_type == alert_type,
                AlertSubscription.is_active == True
            )
        )

        if platform:
            query = query.where(AlertSubscription.platform == platform)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_product_subscriptions(
        self,
        product_id: uuid.UUID,
    ) -> list[AlertSubscription]:
        """Get all active subscriptions for a product."""
        result = await self.session.execute(
            select(AlertSubscription).where(
                and_(
                    AlertSubscription.product_id == product_id,
                    AlertSubscription.is_active == True
                )
            )
        )
        return list(result.scalars().all())

    async def deactivate(self, subscription_id: uuid.UUID) -> bool:
        """Deactivate a subscription."""
        result = await self.session.execute(
            update(AlertSubscription)
            .where(AlertSubscription.id == subscription_id)
            .values(is_active=False)
        )
        return result.rowcount > 0

    async def delete(self, subscription_id: uuid.UUID) -> bool:
        """Delete a subscription."""
        subscription = await self.get_by_id(subscription_id)
        if subscription:
            await self.session.delete(subscription)
            return True
        return False


class AlertEventRepository:
    """Repository for alert events."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        subscription_id: uuid.UUID,
        event_type: str,
        event_data: dict,
        previous_value: str | None = None,
        current_value: str | None = None,
    ) -> AlertEvent:
        """Create a new alert event."""
        event = AlertEvent(
            subscription_id=subscription_id,
            event_type=event_type,
            event_data=json.dumps(event_data),
            previous_value=previous_value,
            current_value=current_value,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_by_id(self, event_id: uuid.UUID) -> AlertEvent | None:
        """Get event by ID."""
        result = await self.session.execute(
            select(AlertEvent).where(AlertEvent.id == event_id)
        )
        return result.scalar_one_or_none()

    async def get_subscription_events(
        self,
        subscription_id: uuid.UUID,
        limit: int = 50,
        unacknowledged_only: bool = False,
    ) -> list[AlertEvent]:
        """Get events for a subscription."""
        query = select(AlertEvent).where(AlertEvent.subscription_id == subscription_id)

        if unacknowledged_only:
            query = query.where(AlertEvent.acknowledged == False)

        query = query.order_by(AlertEvent.triggered_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_user_events(
        self,
        user_id: str,
        limit: int = 100,
        unacknowledged_only: bool = False,
    ) -> list[AlertEvent]:
        """Get all events for a user's subscriptions."""
        query = (
            select(AlertEvent)
            .join(AlertSubscription)
            .where(AlertSubscription.user_id == user_id)
        )

        if unacknowledged_only:
            query = query.where(AlertEvent.acknowledged == False)

        query = query.order_by(AlertEvent.triggered_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def acknowledge(self, event_id: uuid.UUID) -> bool:
        """Acknowledge an event."""
        result = await self.session.execute(
            update(AlertEvent)
            .where(AlertEvent.id == event_id)
            .values(acknowledged=True, acknowledged_at=datetime.utcnow())
        )
        return result.rowcount > 0

    async def acknowledge_all(self, subscription_id: uuid.UUID) -> int:
        """Acknowledge all events for a subscription."""
        result = await self.session.execute(
            update(AlertEvent)
            .where(
                and_(
                    AlertEvent.subscription_id == subscription_id,
                    AlertEvent.acknowledged == False
                )
            )
            .values(acknowledged=True, acknowledged_at=datetime.utcnow())
        )
        return result.rowcount

    async def get_recent_count(
        self,
        subscription_id: uuid.UUID,
        hours: int = 24,
    ) -> int:
        """Get count of recent events for rate limiting."""
        since = datetime.utcnow() - timedelta(hours=hours)
        result = await self.session.execute(
            select(func.count(AlertEvent.id))
            .where(
                and_(
                    AlertEvent.subscription_id == subscription_id,
                    AlertEvent.triggered_at >= since
                )
            )
        )
        return result.scalar() or 0


from datetime import timedelta
