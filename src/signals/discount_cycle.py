"""Discount cycle prediction module.

Analyzes historical price patterns to predict future discount cycles.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import mean, stdev

from src.db.models import DailyMetric


@dataclass
class DiscountEvent:
    """A detected discount event."""

    date: date
    original_price: Decimal
    discounted_price: Decimal
    discount_percent: float


@dataclass
class DiscountCyclePrediction:
    """Discount cycle prediction result."""

    avg_cycle_days: float | None
    next_predicted_discount: date | None
    confidence: float
    historical_discounts: list[DiscountEvent]
    typical_discount_percent: float
    interpretation: str


class DiscountCyclePredictor:
    """Predictor for product discount cycles."""

    # Minimum discount to be considered significant
    MIN_DISCOUNT_THRESHOLD = 0.05  # 5%

    def predict(self, metrics: list[DailyMetric]) -> DiscountCyclePrediction:
        """Predict discount cycles from price history."""
        if len(metrics) < 14:
            return DiscountCyclePrediction(
                avg_cycle_days=None,
                next_predicted_discount=None,
                confidence=0.0,
                historical_discounts=[],
                typical_discount_percent=0.0,
                interpretation="Insufficient price history (need 14+ days)",
            )

        sorted_metrics = sorted(metrics, key=lambda m: m.date)

        # Detect discount events
        discounts = self._detect_discounts(sorted_metrics)

        if len(discounts) < 2:
            return DiscountCyclePrediction(
                avg_cycle_days=None,
                next_predicted_discount=None,
                confidence=0.1,
                historical_discounts=discounts,
                typical_discount_percent=self._avg_discount(discounts),
                interpretation="Not enough discount events to detect a cycle",
            )

        # Calculate cycle length
        cycle_days, cycle_std = self._calculate_cycle(discounts)

        # Predict next discount
        last_discount = discounts[-1]
        next_predicted = last_discount.date + timedelta(days=int(cycle_days))

        # Calculate confidence
        confidence = self._calculate_confidence(len(discounts), cycle_std, cycle_days)

        typical_discount = self._avg_discount(discounts)

        interpretation = self._interpret(
            cycle_days, next_predicted, typical_discount, confidence
        )

        return DiscountCyclePrediction(
            avg_cycle_days=round(cycle_days, 1),
            next_predicted_discount=next_predicted,
            confidence=confidence,
            historical_discounts=discounts,
            typical_discount_percent=typical_discount,
            interpretation=interpretation,
        )

    def _detect_discounts(self, metrics: list[DailyMetric]) -> list[DiscountEvent]:
        """Detect significant discount events in the price history."""
        discounts = []

        # Calculate the moving average price as baseline
        if len(metrics) < 7:
            return discounts

        for i in range(7, len(metrics)):
            # Use 7-day trailing average as baseline
            baseline_prices = [float(m.price) for m in metrics[i - 7:i]]
            baseline = mean(baseline_prices)

            current = float(metrics[i].price)

            if baseline > 0:
                discount_pct = (baseline - current) / baseline

                # Check if this is a significant discount
                if discount_pct >= self.MIN_DISCOUNT_THRESHOLD:
                    # Check if this is a new event (not continuation of previous discount)
                    if not discounts or (metrics[i].date - discounts[-1].date).days > 3:
                        discounts.append(DiscountEvent(
                            date=metrics[i].date,
                            original_price=Decimal(str(baseline)),
                            discounted_price=metrics[i].price,
                            discount_percent=round(discount_pct * 100, 1),
                        ))

        return discounts

    def _calculate_cycle(
        self, discounts: list[DiscountEvent]
    ) -> tuple[float, float]:
        """Calculate average cycle length and standard deviation."""
        if len(discounts) < 2:
            return 0.0, 0.0

        gaps = []
        for i in range(1, len(discounts)):
            gap = (discounts[i].date - discounts[i - 1].date).days
            gaps.append(gap)

        avg_gap = mean(gaps)
        std_gap = stdev(gaps) if len(gaps) > 1 else 0.0

        return avg_gap, std_gap

    def _calculate_confidence(
        self, num_events: int, cycle_std: float, cycle_avg: float
    ) -> float:
        """Calculate confidence in the prediction."""
        # Base confidence from number of events
        if num_events >= 5:
            base = 0.7
        elif num_events >= 3:
            base = 0.5
        else:
            base = 0.3

        # Adjust for consistency (lower std relative to avg = higher confidence)
        if cycle_avg > 0:
            consistency_factor = 1.0 - min(cycle_std / cycle_avg, 0.5)
        else:
            consistency_factor = 0.5

        return min(base * consistency_factor + 0.2, 0.95)

    def _avg_discount(self, discounts: list[DiscountEvent]) -> float:
        """Calculate average discount percentage."""
        if not discounts:
            return 0.0
        return mean([d.discount_percent for d in discounts])

    def _interpret(
        self,
        cycle_days: float,
        next_predicted: date,
        typical_discount: float,
        confidence: float,
    ) -> str:
        """Generate human-readable interpretation."""
        days_until = (next_predicted - date.today()).days

        if days_until < 0:
            timing = "may have already started or is imminent"
        elif days_until <= 7:
            timing = f"expected within {days_until} days"
        elif days_until <= 30:
            timing = f"expected in ~{days_until // 7} weeks"
        else:
            timing = f"expected around {next_predicted.strftime('%b %d')}"

        conf_text = (
            "High confidence" if confidence > 0.7
            else "Moderate confidence" if confidence > 0.4
            else "Low confidence"
        )

        return (
            f"{conf_text}: ~{cycle_days:.0f}-day discount cycle detected. "
            f"Next discount ({typical_discount:.0f}% typical) {timing}."
        )
