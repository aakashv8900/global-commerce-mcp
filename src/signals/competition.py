"""Competition score calculation module.

Competition Score Formula:
    competition_score = (
        normalized_seller_count * 0.4 +
        review_concentration_index * 0.3 +
        buybox_volatility * 0.3
    )

Note: Higher score = MORE competition (harder to compete)
"""

from dataclasses import dataclass
from collections import Counter

from src.db.models import DailyMetric


@dataclass
class CompetitionSignals:
    """Raw signals used for competition calculation."""

    avg_seller_count: float
    review_concentration: float  # 0-1, higher = more concentrated (less competition)
    buybox_volatility: float  # 0-1, higher = more volatile (more competition)


@dataclass
class CompetitionResult:
    """Competition calculation result."""

    score: float  # 0-100, higher = more competition
    signals: CompetitionSignals
    interpretation: str
    barrier_to_entry: str  # Low, Medium, High


class CompetitionCalculator:
    """Calculator for product competition score."""

    # Normalization constants
    MAX_SELLER_COUNT = 50  # 50+ sellers is very competitive
    
    # Weights
    WEIGHT_SELLER_COUNT = 0.4
    WEIGHT_REVIEW_CONCENTRATION = 0.3
    WEIGHT_BUYBOX_VOLATILITY = 0.3

    def calculate(self, metrics: list[DailyMetric]) -> CompetitionResult:
        """Calculate competition score from metrics history."""
        if not metrics:
            return CompetitionResult(
                score=50.0,  # Default to moderate
                signals=CompetitionSignals(1.0, 0.5, 0.5),
                interpretation="Insufficient data for competition analysis",
                barrier_to_entry="Unknown",
            )

        # Calculate signals
        avg_sellers = self._calculate_avg_sellers(metrics)
        review_concentration = self._calculate_review_concentration(metrics)
        buybox_volatility = self._calculate_buybox_volatility(metrics)

        signals = CompetitionSignals(
            avg_seller_count=avg_sellers,
            review_concentration=review_concentration,
            buybox_volatility=buybox_volatility,
        )

        # Normalize seller count
        norm_sellers = min(avg_sellers / self.MAX_SELLER_COUNT, 1.0)

        # For competition score:
        # - More sellers = more competition
        # - Lower concentration = more competition (inverted)
        # - Higher buybox volatility = more competition
        norm_concentration_inverted = 1.0 - review_concentration

        score = (
            norm_sellers * self.WEIGHT_SELLER_COUNT
            + norm_concentration_inverted * self.WEIGHT_REVIEW_CONCENTRATION
            + buybox_volatility * self.WEIGHT_BUYBOX_VOLATILITY
        ) * 100

        interpretation = self._interpret_score(score, signals)
        barrier = self._assess_barrier(score, signals)

        return CompetitionResult(
            score=round(score, 1),
            signals=signals,
            interpretation=interpretation,
            barrier_to_entry=barrier,
        )

    def _calculate_avg_sellers(self, metrics: list[DailyMetric]) -> float:
        """Calculate average seller count over period."""
        if not metrics:
            return 1.0
        return sum(m.seller_count for m in metrics) / len(metrics)

    def _calculate_review_concentration(self, metrics: list[DailyMetric]) -> float:
        """
        Calculate review concentration index.
        Higher value = reviews concentrated with top seller = higher barrier.
        
        This is a simplified version - in production, we'd track reviews per seller.
        For now, we use buybox ownership patterns as a proxy.
        """
        if not metrics:
            return 0.5

        # Use buybox ownership as proxy for market concentration
        buybox_owners = [m.buybox_owner for m in metrics if m.buybox_owner]
        if not buybox_owners:
            return 0.5

        # Count ownership frequency
        owner_counts = Counter(buybox_owners)
        total = len(buybox_owners)
        
        # Calculate concentration (Herfindahl-style)
        concentration = sum((count / total) ** 2 for count in owner_counts.values())
        return concentration

    def _calculate_buybox_volatility(self, metrics: list[DailyMetric]) -> float:
        """
        Calculate buybox volatility (how often it changes hands).
        Higher volatility = more competition for the buybox.
        """
        if len(metrics) < 2:
            return 0.5

        buybox_owners = [m.buybox_owner for m in metrics]
        changes = sum(
            1 for i in range(1, len(buybox_owners))
            if buybox_owners[i] != buybox_owners[i - 1]
        )

        # Normalize by number of possible changes
        max_changes = len(metrics) - 1
        if max_changes == 0:
            return 0.5

        return changes / max_changes

    def _interpret_score(self, score: float, signals: CompetitionSignals) -> str:
        """Generate human-readable interpretation."""
        if score >= 80:
            level = "Extremely Competitive"
            desc = "Many sellers actively competing for this product"
        elif score >= 60:
            level = "Highly Competitive"
            desc = "Significant seller competition present"
        elif score >= 40:
            level = "Moderately Competitive"
            desc = "Normal competitive environment"
        elif score >= 20:
            level = "Low Competition"
            desc = "Limited seller competition"
        else:
            level = "Very Low Competition"
            desc = "Dominated by few sellers"

        return f"{level}. {desc}. Average of {signals.avg_seller_count:.1f} sellers."

    def _assess_barrier(self, score: float, signals: CompetitionSignals) -> str:
        """Assess barrier to entry."""
        # High concentration + low score = high barrier (established player dominates)
        # Low concentration + high score = low barrier (many small players)
        
        if signals.review_concentration > 0.7:
            return "High"  # Dominated by established seller
        elif score > 70:
            return "Low"  # Many competitors, easy to enter
        elif score > 40:
            return "Medium"
        else:
            return "High"  # Few sellers but concentrated reviews
