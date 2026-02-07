"""Demand score calculation module.

Demand Score Formula:
    demand_score = (
        normalized_review_velocity * 0.4 +
        normalized_rank_improvement * 0.3 +
        stockout_frequency * 0.2 +
        price_increase_signal * 0.1
    )
"""

from dataclasses import dataclass
from decimal import Decimal

from src.db.models import DailyMetric


@dataclass
class DemandSignals:
    """Raw signals used for demand calculation."""

    review_velocity: float  # Reviews per day
    rank_improvement: float  # % improvement in rank
    stockout_frequency: float  # % of days out of stock
    price_increase: float  # % price increase


@dataclass
class DemandResult:
    """Demand calculation result."""

    score: float  # 0-100
    signals: DemandSignals
    interpretation: str


class DemandCalculator:
    """Calculator for product demand score."""

    # Normalization constants (based on typical ranges)
    MAX_REVIEW_VELOCITY = 50.0  # 50 reviews/day is exceptional
    MAX_RANK_IMPROVEMENT = 0.5  # 50% rank improvement is exceptional
    MAX_STOCKOUT_FREQ = 0.3  # 30% stockout indicates high demand
    MAX_PRICE_INCREASE = 0.2  # 20% price increase is significant

    # Weights
    WEIGHT_REVIEW_VELOCITY = 0.4
    WEIGHT_RANK_IMPROVEMENT = 0.3
    WEIGHT_STOCKOUT_FREQUENCY = 0.2
    WEIGHT_PRICE_INCREASE = 0.1

    def calculate(
        self,
        metrics: list[DailyMetric],
        days: int = 30,
    ) -> DemandResult:
        """Calculate demand score from metrics history."""
        if len(metrics) < 2:
            return DemandResult(
                score=0.0,
                signals=DemandSignals(0.0, 0.0, 0.0, 0.0),
                interpretation="Insufficient data for demand calculation",
            )

        # Sort by date
        sorted_metrics = sorted(metrics, key=lambda m: m.date)

        # Calculate raw signals
        review_velocity = self._calculate_review_velocity(sorted_metrics)
        rank_improvement = self._calculate_rank_improvement(sorted_metrics)
        stockout_freq = self._calculate_stockout_frequency(sorted_metrics)
        price_increase = self._calculate_price_increase(sorted_metrics)

        signals = DemandSignals(
            review_velocity=review_velocity,
            rank_improvement=rank_improvement,
            stockout_frequency=stockout_freq,
            price_increase=price_increase,
        )

        # Normalize to 0-1 range
        norm_review = min(review_velocity / self.MAX_REVIEW_VELOCITY, 1.0)
        norm_rank = min(max(rank_improvement, 0) / self.MAX_RANK_IMPROVEMENT, 1.0)
        norm_stockout = min(stockout_freq / self.MAX_STOCKOUT_FREQ, 1.0)
        norm_price = min(max(price_increase, 0) / self.MAX_PRICE_INCREASE, 1.0)

        # Calculate weighted score
        score = (
            norm_review * self.WEIGHT_REVIEW_VELOCITY
            + norm_rank * self.WEIGHT_RANK_IMPROVEMENT
            + norm_stockout * self.WEIGHT_STOCKOUT_FREQUENCY
            + norm_price * self.WEIGHT_PRICE_INCREASE
        ) * 100

        interpretation = self._interpret_score(score, signals)

        return DemandResult(
            score=round(score, 1),
            signals=signals,
            interpretation=interpretation,
        )

    def _calculate_review_velocity(self, metrics: list[DailyMetric]) -> float:
        """Calculate reviews per day."""
        if len(metrics) < 2:
            return 0.0

        oldest = metrics[0]
        newest = metrics[-1]
        day_diff = (newest.date - oldest.date).days

        if day_diff == 0:
            return 0.0

        return (newest.reviews - oldest.reviews) / day_diff

    def _calculate_rank_improvement(self, metrics: list[DailyMetric]) -> float:
        """Calculate rank improvement percentage."""
        if len(metrics) < 2:
            return 0.0

        oldest = metrics[0]
        newest = metrics[-1]

        if oldest.rank is None or newest.rank is None or oldest.rank == 0:
            return 0.0

        # Positive = improvement (lower rank is better)
        return (oldest.rank - newest.rank) / oldest.rank

    def _calculate_stockout_frequency(self, metrics: list[DailyMetric]) -> float:
        """Calculate percentage of days out of stock."""
        if not metrics:
            return 0.0

        out_of_stock = sum(1 for m in metrics if not m.in_stock)
        return out_of_stock / len(metrics)

    def _calculate_price_increase(self, metrics: list[DailyMetric]) -> float:
        """Calculate percentage price increase."""
        if len(metrics) < 2:
            return 0.0

        oldest = metrics[0]
        newest = metrics[-1]

        if oldest.price == 0:
            return 0.0

        return float((newest.price - oldest.price) / oldest.price)

    def _interpret_score(self, score: float, signals: DemandSignals) -> str:
        """Generate human-readable interpretation."""
        if score >= 80:
            level = "Very High Demand"
        elif score >= 60:
            level = "High Demand"
        elif score >= 40:
            level = "Moderate Demand"
        elif score >= 20:
            level = "Low Demand"
        else:
            level = "Very Low Demand"

        insights = []
        if signals.review_velocity > 10:
            insights.append(f"Strong review velocity ({signals.review_velocity:.1f}/day)")
        if signals.rank_improvement > 0.1:
            insights.append(f"Rank improving ({signals.rank_improvement * 100:.1f}%)")
        if signals.stockout_frequency > 0.1:
            insights.append("Frequent stockouts indicate demand")
        if signals.price_increase > 0.05:
            insights.append("Price trending up")

        insight_text = ". ".join(insights) if insights else "Normal demand indicators"
        return f"{level}. {insight_text}."
