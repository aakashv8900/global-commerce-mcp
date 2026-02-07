"""Alert trigger definitions."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional, Any

from src.db.models import DailyMetric, AlertSubscription


@dataclass
class TriggerResult:
    """Result of evaluating an alert trigger."""
    triggered: bool
    event_type: str
    event_data: dict
    previous_value: str | None
    current_value: str | None
    message: str


class AlertTrigger(ABC):
    """Base class for alert triggers."""

    @property
    @abstractmethod
    def trigger_type(self) -> str:
        """Return the type of this trigger."""
        pass

    @abstractmethod
    def evaluate(
        self,
        subscription: AlertSubscription,
        current_metric: DailyMetric,
        previous_metric: DailyMetric | None,
    ) -> TriggerResult | None:
        """
        Evaluate if the trigger condition is met.

        Returns TriggerResult if triggered, None otherwise.
        """
        pass


class PriceDropTrigger(AlertTrigger):
    """Trigger when price drops below threshold or by percentage."""

    @property
    def trigger_type(self) -> str:
        return "price_drop"

    def evaluate(
        self,
        subscription: AlertSubscription,
        current_metric: DailyMetric,
        previous_metric: DailyMetric | None,
    ) -> TriggerResult | None:
        current_price = float(current_metric.price)

        # Check absolute threshold
        if subscription.threshold_value:
            threshold = float(subscription.threshold_value)
            if current_price <= threshold:
                return TriggerResult(
                    triggered=True,
                    event_type="price_below_threshold",
                    event_data={
                        "current_price": current_price,
                        "threshold": threshold,
                        "product_id": str(current_metric.product_id),
                    },
                    previous_value=None,
                    current_value=f"${current_price:.2f}",
                    message=f"💰 Price dropped to ${current_price:.2f} (below ${threshold:.2f} threshold)",
                )

        # Check percentage drop
        if previous_metric and subscription.threshold_percent:
            previous_price = float(previous_metric.price)
            if previous_price > 0:
                drop_percent = ((previous_price - current_price) / previous_price) * 100
                if drop_percent >= subscription.threshold_percent:
                    return TriggerResult(
                        triggered=True,
                        event_type="price_drop_percent",
                        event_data={
                            "current_price": current_price,
                            "previous_price": previous_price,
                            "drop_percent": drop_percent,
                            "product_id": str(current_metric.product_id),
                        },
                        previous_value=f"${previous_price:.2f}",
                        current_value=f"${current_price:.2f}",
                        message=f"📉 Price dropped {drop_percent:.1f}% from ${previous_price:.2f} to ${current_price:.2f}",
                    )

        return None


class StockoutTrigger(AlertTrigger):
    """Trigger when product goes out of stock."""

    @property
    def trigger_type(self) -> str:
        return "stockout"

    def evaluate(
        self,
        subscription: AlertSubscription,
        current_metric: DailyMetric,
        previous_metric: DailyMetric | None,
    ) -> TriggerResult | None:
        if not current_metric.in_stock:
            # Only trigger if it was previously in stock
            if previous_metric is None or previous_metric.in_stock:
                return TriggerResult(
                    triggered=True,
                    event_type="stockout",
                    event_data={
                        "product_id": str(current_metric.product_id),
                        "last_price": float(current_metric.price),
                    },
                    previous_value="In Stock",
                    current_value="Out of Stock",
                    message="🔴 Product is now OUT OF STOCK",
                )

        # Back in stock notification
        if current_metric.in_stock and previous_metric and not previous_metric.in_stock:
            return TriggerResult(
                triggered=True,
                event_type="back_in_stock",
                event_data={
                    "product_id": str(current_metric.product_id),
                    "current_price": float(current_metric.price),
                },
                previous_value="Out of Stock",
                current_value="In Stock",
                message=f"🟢 Product is BACK IN STOCK at ${current_metric.price}",
            )

        return None


class TrendChangeTrigger(AlertTrigger):
    """Trigger on significant trend changes (rank improvements/declines)."""

    @property
    def trigger_type(self) -> str:
        return "trend_change"

    def evaluate(
        self,
        subscription: AlertSubscription,
        current_metric: DailyMetric,
        previous_metric: DailyMetric | None,
    ) -> TriggerResult | None:
        if not previous_metric:
            return None

        current_rank = current_metric.rank
        previous_rank = previous_metric.rank

        if not current_rank or not previous_rank:
            return None

        # Calculate rank change percentage
        rank_change = previous_rank - current_rank  # Positive = improvement
        change_percent = (rank_change / previous_rank) * 100

        threshold_percent = subscription.threshold_percent or 20.0

        if abs(change_percent) >= threshold_percent:
            if rank_change > 0:
                event_type = "rank_improving"
                emoji = "🚀"
                direction = "improved"
            else:
                event_type = "rank_declining"
                emoji = "📉"
                direction = "declined"

            return TriggerResult(
                triggered=True,
                event_type=event_type,
                event_data={
                    "current_rank": current_rank,
                    "previous_rank": previous_rank,
                    "change_percent": change_percent,
                    "product_id": str(current_metric.product_id),
                },
                previous_value=f"#{previous_rank:,}",
                current_value=f"#{current_rank:,}",
                message=f"{emoji} Rank {direction} by {abs(change_percent):.1f}% (#{previous_rank:,} → #{current_rank:,})",
            )

        return None


class ArbitrageTrigger(AlertTrigger):
    """Trigger when arbitrage opportunity is detected."""

    @property
    def trigger_type(self) -> str:
        return "arbitrage"

    def evaluate(
        self,
        subscription: AlertSubscription,
        current_metric: DailyMetric,
        previous_metric: DailyMetric | None,
    ) -> TriggerResult | None:
        # This trigger requires cross-platform data
        # The AlertEngine will need to provide additional context
        # For now, return None - implementation needs arbitrage analyzer integration
        return None

    def evaluate_arbitrage(
        self,
        subscription: AlertSubscription,
        source_price_usd: float,
        target_price_usd: float,
        estimated_fees_usd: float,
    ) -> TriggerResult | None:
        """
        Evaluate arbitrage opportunity between platforms.

        Args:
            source_price_usd: Buy price in USD
            target_price_usd: Sell price in USD
            estimated_fees_usd: Estimated shipping + import fees
        """
        margin = target_price_usd - source_price_usd - estimated_fees_usd
        margin_percent = (margin / source_price_usd) * 100 if source_price_usd > 0 else 0

        threshold_percent = subscription.threshold_percent or 15.0

        if margin_percent >= threshold_percent:
            return TriggerResult(
                triggered=True,
                event_type="arbitrage_opportunity",
                event_data={
                    "source_price": source_price_usd,
                    "target_price": target_price_usd,
                    "fees": estimated_fees_usd,
                    "margin": margin,
                    "margin_percent": margin_percent,
                },
                previous_value=None,
                current_value=f"{margin_percent:.1f}% margin",
                message=f"🌍 Arbitrage opportunity: {margin_percent:.1f}% margin (${margin:.2f} profit)",
            )

        return None


class RankChangeTrigger(AlertTrigger):
    """Trigger when rank crosses specific thresholds."""

    THRESHOLDS = [100, 500, 1000, 5000, 10000, 50000, 100000]

    @property
    def trigger_type(self) -> str:
        return "rank_change"

    def evaluate(
        self,
        subscription: AlertSubscription,
        current_metric: DailyMetric,
        previous_metric: DailyMetric | None,
    ) -> TriggerResult | None:
        if not previous_metric:
            return None

        current_rank = current_metric.rank
        previous_rank = previous_metric.rank

        if not current_rank or not previous_rank:
            return None

        # Check if we crossed any threshold
        for threshold in self.THRESHOLDS:
            if previous_rank > threshold >= current_rank:
                # Entered top N
                return TriggerResult(
                    triggered=True,
                    event_type="entered_top_rank",
                    event_data={
                        "current_rank": current_rank,
                        "threshold": threshold,
                        "product_id": str(current_metric.product_id),
                    },
                    previous_value=f"#{previous_rank:,}",
                    current_value=f"#{current_rank:,}",
                    message=f"🏆 Entered Top {threshold:,}! (Rank #{current_rank:,})",
                )
            elif previous_rank < threshold <= current_rank:
                # Dropped out of top N
                return TriggerResult(
                    triggered=True,
                    event_type="exited_top_rank",
                    event_data={
                        "current_rank": current_rank,
                        "threshold": threshold,
                        "product_id": str(current_metric.product_id),
                    },
                    previous_value=f"#{previous_rank:,}",
                    current_value=f"#{current_rank:,}",
                    message=f"📉 Dropped out of Top {threshold:,} (Rank #{current_rank:,})",
                )

        return None


# Factory for creating triggers by type
TRIGGER_REGISTRY: dict[str, type[AlertTrigger]] = {
    "price_drop": PriceDropTrigger,
    "stockout": StockoutTrigger,
    "trend_change": TrendChangeTrigger,
    "arbitrage": ArbitrageTrigger,
    "rank_change": RankChangeTrigger,
}


def get_trigger(alert_type: str) -> AlertTrigger | None:
    """Get trigger instance by type."""
    trigger_class = TRIGGER_REGISTRY.get(alert_type)
    if trigger_class:
        return trigger_class()
    return None
