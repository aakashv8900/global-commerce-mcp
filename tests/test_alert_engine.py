"""Tests for Alert Engine module."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch
import uuid


class TestAlertTriggers:
    """Tests for alert trigger classes."""

    def test_price_drop_trigger_activated(self):
        """Test price drop trigger activation."""
        from src.alerts.triggers import PriceDropTrigger

        trigger = PriceDropTrigger(threshold_percent=10.0)

        # Current price dropped 15%
        current_metrics = MagicMock(price=Decimal("85.00"))
        previous_metrics = MagicMock(price=Decimal("100.00"))

        result = trigger.evaluate(current_metrics, previous_metrics)

        assert result.triggered is True
        assert result.alert_type == "price_drop"
        assert "15" in str(result.message) or "price" in result.message.lower()

    def test_price_drop_trigger_not_activated(self):
        """Test price drop trigger when threshold not met."""
        from src.alerts.triggers import PriceDropTrigger

        trigger = PriceDropTrigger(threshold_percent=10.0)

        # Only 5% drop
        current_metrics = MagicMock(price=Decimal("95.00"))
        previous_metrics = MagicMock(price=Decimal("100.00"))

        result = trigger.evaluate(current_metrics, previous_metrics)

        assert result.triggered is False

    def test_stockout_trigger_activated(self):
        """Test stockout trigger when out of stock."""
        from src.alerts.triggers import StockoutTrigger

        trigger = StockoutTrigger()

        current_metrics = MagicMock(in_stock=False)
        previous_metrics = MagicMock(in_stock=True)

        result = trigger.evaluate(current_metrics, previous_metrics)

        assert result.triggered is True
        assert result.alert_type == "stockout"

    def test_stockout_trigger_not_activated(self):
        """Test stockout trigger when still in stock."""
        from src.alerts.triggers import StockoutTrigger

        trigger = StockoutTrigger()

        current_metrics = MagicMock(in_stock=True)
        previous_metrics = MagicMock(in_stock=True)

        result = trigger.evaluate(current_metrics, previous_metrics)

        assert result.triggered is False

    def test_rank_change_trigger_improvement(self):
        """Test rank change trigger on significant improvement."""
        from src.alerts.triggers import RankChangeTrigger

        trigger = RankChangeTrigger(threshold_percent=20.0)

        # Rank improved by 50%
        current_metrics = MagicMock(rank=500)
        previous_metrics = MagicMock(rank=1000)

        result = trigger.evaluate(current_metrics, previous_metrics)

        assert result.triggered is True
        assert result.alert_type == "rank_change"

    def test_trend_change_trigger(self):
        """Test trend change trigger."""
        from src.alerts.triggers import TrendChangeTrigger

        trigger = TrendChangeTrigger()

        # Significant review velocity increase
        current_metrics = MagicMock(
            reviews=1000,
            rating=4.5,
            rank=200,
        )
        previous_metrics = MagicMock(
            reviews=800,
            rating=4.2,
            rank=500,
        )

        result = trigger.evaluate(current_metrics, previous_metrics)

        # Should detect positive trend
        assert result.alert_type == "trend_change"


class TestNotificationChannels:
    """Tests for notification channels."""

    @pytest.mark.asyncio
    async def test_webhook_channel_send(self):
        """Test webhook channel notification."""
        from src.alerts.channels import WebhookChannel

        channel = WebhookChannel(webhook_url="https://example.com/webhook")

        alert_event = MagicMock(
            id=uuid.uuid4(),
            event_type="price_drop",
            event_data='{"price": 85.00, "previous_price": 100.00}',
            triggered_at=datetime.now(),
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

            result = await channel.send(alert_event)

            assert result is True

    @pytest.mark.asyncio
    async def test_mcp_channel_queue(self):
        """Test MCP channel queues notification."""
        from src.alerts.channels import MCPChannel

        channel = MCPChannel()

        alert_event = MagicMock(
            id=uuid.uuid4(),
            event_type="stockout",
            event_data='{"in_stock": false}',
            triggered_at=datetime.now(),
        )

        result = await channel.send(alert_event)

        # MCP channel should always succeed (queues for next request)
        assert result is True


class TestAlertEngine:
    """Tests for AlertEngine processing."""

    @pytest.mark.asyncio
    async def test_process_metrics_triggers_alert(self):
        """Test that processing metrics triggers appropriate alerts."""
        from src.alerts.engine import AlertEngine

        engine = AlertEngine()

        # Mock subscription
        subscription = MagicMock(
            id=uuid.uuid4(),
            alert_type="price_drop",
            threshold_percent=10.0,
            notification_channel="mcp",
            is_active=True,
        )

        current_metrics = MagicMock(
            price=Decimal("80.00"),
            in_stock=True,
            rank=500,
        )

        previous_metrics = MagicMock(
            price=Decimal("100.00"),
            in_stock=True,
            rank=600,
        )

        events = await engine.evaluate_subscription(
            subscription, current_metrics, previous_metrics
        )

        assert len(events) > 0
        assert events[0]["type"] == "price_drop"

    @pytest.mark.asyncio
    async def test_inactive_subscription_skipped(self):
        """Test that inactive subscriptions are skipped."""
        from src.alerts.engine import AlertEngine

        engine = AlertEngine()

        subscription = MagicMock(
            id=uuid.uuid4(),
            alert_type="price_drop",
            threshold_percent=10.0,
            is_active=False,  # Inactive
        )

        current_metrics = MagicMock(price=Decimal("50.00"))
        previous_metrics = MagicMock(price=Decimal("100.00"))

        events = await engine.evaluate_subscription(
            subscription, current_metrics, previous_metrics
        )

        assert len(events) == 0


class TestAlertRepository:
    """Tests for AlertRepository database operations."""

    @pytest.mark.asyncio
    async def test_create_subscription(self):
        """Test creating a new subscription."""
        from src.db.repositories.alert_repository import AlertRepository

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        repo = AlertRepository(mock_session)

        subscription = await repo.create_subscription(
            user_id="user123",
            alert_type="price_drop",
            product_id=uuid.uuid4(),
            platform="amazon_us",
            threshold_percent=15.0,
            notification_channel="webhook",
            webhook_url="https://example.com/hook",
        )

        assert subscription is not None
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_active_subscriptions(self):
        """Test getting active subscriptions."""
        from src.db.repositories.alert_repository import AlertRepository

        mock_session = AsyncMock()
        mock_subscriptions = [
            MagicMock(id=uuid.uuid4(), is_active=True),
            MagicMock(id=uuid.uuid4(), is_active=True),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_subscriptions
        mock_session.execute.return_value = mock_result

        repo = AlertRepository(mock_session)
        result = await repo.get_active_subscriptions("user123")

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_deactivate_subscription(self):
        """Test deactivating a subscription."""
        from src.db.repositories.alert_repository import AlertRepository

        mock_session = AsyncMock()
        mock_subscription = MagicMock(id=uuid.uuid4(), is_active=True)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_subscription
        mock_session.execute.return_value = mock_result

        repo = AlertRepository(mock_session)
        result = await repo.deactivate_subscription(mock_subscription.id)

        assert result is True
        assert mock_subscription.is_active is False
