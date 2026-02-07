"""Trend score calculation module.

Trend Score Formula:
    trend_score = (
        review_velocity_growth_rate * 0.5 +
        rank_acceleration * 0.3 +
        price_growth * 0.2
    )
"""

from dataclasses import dataclass
from decimal import Decimal

from src.db.models import DailyMetric


@dataclass
class TrendSignals:
    """Raw signals used for trend calculation."""

    review_velocity_growth: float  # % change in review velocity
    rank_acceleration: float  # Rate of rank improvement acceleration
    price_growth: float  # % price change


@dataclass
class TrendResult:
    """Trend calculation result."""

    score: float  # -100 to +100 (negative = declining)
    trend_direction: str  # "Accelerating", "Stable", "Declining"
    signals: TrendSignals
    interpretation: str


class TrendCalculator:
    """Calculator for product trend score."""

    # Weights
    WEIGHT_REVIEW_GROWTH = 0.5
    WEIGHT_RANK_ACCEL = 0.3
    WEIGHT_PRICE_GROWTH = 0.2

    def calculate(self, metrics: list[DailyMetric]) -> TrendResult:
        """Calculate trend score from metrics history."""
        if len(metrics) < 14:  # Need at least 2 weeks of data
            return TrendResult(
                score=0.0,
                trend_direction="Unknown",
                signals=TrendSignals(0.0, 0.0, 0.0),
                interpretation="Insufficient data (need 14+ days)",
            )

        sorted_metrics = sorted(metrics, key=lambda m: m.date)

        # Split into first half and second half for comparison
        mid = len(sorted_metrics) // 2
        first_half = sorted_metrics[:mid]
        second_half = sorted_metrics[mid:]

        # Calculate signals
        review_growth = self._calculate_review_velocity_growth(first_half, second_half)
        rank_accel = self._calculate_rank_acceleration(first_half, second_half)
        price_growth = self._calculate_price_growth(sorted_metrics)

        signals = TrendSignals(
            review_velocity_growth=review_growth,
            rank_acceleration=rank_accel,
            price_growth=price_growth,
        )

        # Calculate weighted score (-100 to +100)
        # Normalize each signal to roughly -1 to +1 range
        norm_review = self._normalize_growth(review_growth, max_val=2.0)
        norm_rank = self._normalize_growth(rank_accel, max_val=1.0)
        norm_price = self._normalize_growth(price_growth, max_val=0.5)

        score = (
            norm_review * self.WEIGHT_REVIEW_GROWTH
            + norm_rank * self.WEIGHT_RANK_ACCEL
            + norm_price * self.WEIGHT_PRICE_GROWTH
        ) * 100

        trend_direction = self._determine_direction(score)
        interpretation = self._interpret_trend(score, signals)

        return TrendResult(
            score=round(score, 1),
            trend_direction=trend_direction,
            signals=signals,
            interpretation=interpretation,
        )

    def _calculate_review_velocity_growth(
        self, first_half: list[DailyMetric], second_half: list[DailyMetric]
    ) -> float:
        """Calculate growth in review velocity between periods."""
        v1 = self._velocity(first_half)
        v2 = self._velocity(second_half)

        if v1 == 0:
            return 1.0 if v2 > 0 else 0.0

        return (v2 - v1) / abs(v1)

    def _velocity(self, metrics: list[DailyMetric]) -> float:
        """Calculate review velocity for a period."""
        if len(metrics) < 2:
            return 0.0

        oldest = metrics[0]
        newest = metrics[-1]
        days = (newest.date - oldest.date).days

        if days == 0:
            return 0.0

        return (newest.reviews - oldest.reviews) / days

    def _calculate_rank_acceleration(
        self, first_half: list[DailyMetric], second_half: list[DailyMetric]
    ) -> float:
        """Calculate acceleration in rank improvement."""
        r1 = self._rank_improvement_rate(first_half)
        r2 = self._rank_improvement_rate(second_half)

        # If first period had no change, return second period rate
        if r1 == 0:
            return r2

        return (r2 - r1) / abs(r1)

    def _rank_improvement_rate(self, metrics: list[DailyMetric]) -> float:
        """Calculate daily rank improvement rate."""
        if len(metrics) < 2:
            return 0.0

        ranks = [m.rank for m in metrics if m.rank is not None]
        if len(ranks) < 2:
            return 0.0

        days = (metrics[-1].date - metrics[0].date).days
        if days == 0:
            return 0.0

        # Positive = improving (rank decreasing)
        return (ranks[0] - ranks[-1]) / (ranks[0] * days) if ranks[0] else 0.0

    def _calculate_price_growth(self, metrics: list[DailyMetric]) -> float:
        """Calculate overall price growth."""
        if len(metrics) < 2:
            return 0.0

        oldest = metrics[0]
        newest = metrics[-1]

        if oldest.price == 0:
            return 0.0

        return float((newest.price - oldest.price) / oldest.price)

    def _normalize_growth(self, value: float, max_val: float) -> float:
        """Normalize growth value to -1 to +1 range."""
        return max(-1.0, min(1.0, value / max_val))

    def _determine_direction(self, score: float) -> str:
        """Determine trend direction from score."""
        if score > 20:
            return "Accelerating"
        elif score < -20:
            return "Declining"
        else:
            return "Stable"

    def _interpret_trend(self, score: float, signals: TrendSignals) -> str:
        """Generate human-readable interpretation."""
        if score > 50:
            desc = "Strong upward momentum"
        elif score > 20:
            desc = "Positive trend detected"
        elif score > -20:
            desc = "Relatively stable performance"
        elif score > -50:
            desc = "Showing signs of decline"
        else:
            desc = "Significant downward trend"

        details = []
        if signals.review_velocity_growth > 0.2:
            details.append(f"+{signals.review_velocity_growth * 100:.0f}% review velocity")
        elif signals.review_velocity_growth < -0.2:
            details.append(f"{signals.review_velocity_growth * 100:.0f}% review velocity")

        if signals.price_growth > 0.05:
            details.append(f"+{signals.price_growth * 100:.1f}% price")
        elif signals.price_growth < -0.05:
            details.append(f"{signals.price_growth * 100:.1f}% price")

        detail_text = f" ({', '.join(details)})" if details else ""
        return f"{desc}{detail_text}."
