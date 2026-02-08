"""Risk score calculation module.

Risk Score Formula:
    risk_score = (
        review_spike_anomaly * 0.4 +
        seller_churn_rate * 0.3 +
        rating_volatility * 0.3
    )

Higher score = Higher risk
"""

from dataclasses import dataclass
from statistics import stdev, mean

from src.db.models import DailyMetric


@dataclass
class RiskSignals:
    """Raw signals used for risk calculation."""

    review_spike_detected: bool
    review_spike_magnitude: float
    seller_churn_rate: float
    rating_volatility: float


@dataclass
class RiskFlag:
    """Individual risk flag."""

    category: str  # "review_manipulation", "seller_instability", "quality_issues"
    severity: str  # "low", "medium", "high"
    description: str


@dataclass
class RiskResult:
    """Risk calculation result."""

    score: float  # 0-100, higher = more risk
    risk_level: str  # "Low", "Medium", "High", "Critical"
    signals: RiskSignals
    flags: list[RiskFlag]
    interpretation: str


class RiskCalculator:
    """Calculator for product risk score."""

    # Thresholds
    REVIEW_SPIKE_THRESHOLD = 3.0  # 3x normal velocity = spike
    HIGH_CHURN_THRESHOLD = 0.3  # 30% seller churn
    HIGH_VOLATILITY_THRESHOLD = 0.5  # Rating std dev > 0.5

    # Weights
    WEIGHT_REVIEW_SPIKE = 0.4
    WEIGHT_SELLER_CHURN = 0.3
    WEIGHT_RATING_VOLATILITY = 0.3

    def calculate(self, metrics: list[DailyMetric]) -> RiskResult:
        """Calculate risk score from metrics history."""
        if len(metrics) < 7:
            return RiskResult(
                score=0.0,
                risk_level="Unknown",
                signals=RiskSignals(False, 0.0, 0.0, 0.0),
                flags=[],
                interpretation="Insufficient data for risk analysis",
            )

        sorted_metrics = sorted(metrics, key=lambda m: m.date)

        # Calculate signals
        spike_detected, spike_magnitude = self._detect_review_spikes(sorted_metrics)
        seller_churn = self._calculate_seller_churn(sorted_metrics)
        rating_vol = self._calculate_rating_volatility(sorted_metrics)

        signals = RiskSignals(
            review_spike_detected=spike_detected,
            review_spike_magnitude=spike_magnitude,
            seller_churn_rate=seller_churn,
            rating_volatility=rating_vol,
        )

        # Normalize signals
        norm_spike = min(spike_magnitude / 5.0, 1.0)  # 5x spike = max risk
        norm_churn = min(seller_churn / 0.5, 1.0)  # 50% churn = max risk
        norm_volatility = min(rating_vol / 1.0, 1.0)  # 1.0 std dev = max risk

        score = (
            norm_spike * self.WEIGHT_REVIEW_SPIKE
            + norm_churn * self.WEIGHT_SELLER_CHURN
            + norm_volatility * self.WEIGHT_RATING_VOLATILITY
        ) * 100

        # Generate risk flags
        flags = self._generate_flags(signals)

        risk_level = self._determine_risk_level(score)
        interpretation = self._interpret_risk(score, signals, flags)

        return RiskResult(
            score=round(score, 1),
            risk_level=risk_level,
            signals=signals,
            flags=flags,
            interpretation=interpretation,
        )

    def _detect_review_spikes(
        self, metrics: list[DailyMetric]
    ) -> tuple[bool, float]:
        """Detect abnormal review velocity spikes."""
        if len(metrics) < 7:
            return False, 0.0

        # Calculate daily review changes
        daily_changes = []
        for i in range(1, len(metrics)):
            change = metrics[i].reviews - metrics[i - 1].reviews
            daily_changes.append(max(0, change))

        if not daily_changes or max(daily_changes) == 0:
            return False, 0.0

        avg_change = mean(daily_changes) if daily_changes else 0
        if avg_change == 0:
            return False, 0.0

        max_change = max(daily_changes)
        spike_magnitude = max_change / avg_change

        spike_detected = spike_magnitude > self.REVIEW_SPIKE_THRESHOLD
        return spike_detected, spike_magnitude

    def _calculate_seller_churn(self, metrics: list[DailyMetric]) -> float:
        """Calculate rate of seller count changes."""
        if len(metrics) < 2:
            return 0.0

        # Calculate changes in seller count
        changes = 0
        for i in range(1, len(metrics)):
            if metrics[i].seller_count != metrics[i - 1].seller_count:
                changes += 1

        return changes / (len(metrics) - 1)

    def _calculate_rating_volatility(self, metrics: list[DailyMetric]) -> float:
        """Calculate rating volatility (standard deviation)."""
        ratings = [float(m.rating) for m in metrics if m.rating]
        if len(ratings) < 2:
            return 0.0

        return stdev(ratings)

    def _generate_flags(self, signals: RiskSignals) -> list[RiskFlag]:
        """Generate specific risk flags based on signals."""
        flags = []

        if signals.review_spike_detected:
            severity = (
                "high" if signals.review_spike_magnitude > 5
                else "medium" if signals.review_spike_magnitude > 3
                else "low"
            )
            flags.append(RiskFlag(
                category="review_manipulation",
                severity=severity,
                description=f"Unusual review spike detected ({signals.review_spike_magnitude:.1f}x normal rate)",
            ))

        if signals.seller_churn_rate > self.HIGH_CHURN_THRESHOLD:
            flags.append(RiskFlag(
                category="seller_instability",
                severity="medium",
                description=f"High seller turnover ({signals.seller_churn_rate * 100:.0f}% churn rate)",
            ))

        if signals.rating_volatility > self.HIGH_VOLATILITY_THRESHOLD:
            flags.append(RiskFlag(
                category="quality_issues",
                severity="medium",
                description=f"Rating volatility detected (σ = {signals.rating_volatility:.2f})",
            ))

        return flags

    def _determine_risk_level(self, score: float) -> str:
        """Determine overall risk level."""
        if score >= 70:
            return "Critical"
        elif score >= 50:
            return "High"
        elif score >= 25:
            return "Medium"
        else:
            return "Low"

    def _interpret_risk(
        self, score: float, signals: RiskSignals, flags: list[RiskFlag]
    ) -> str:
        """Generate human-readable risk interpretation."""
        if not flags:
            return "No significant risk factors detected."

        high_severity_flags = [f for f in flags if f.severity == "high"]
        if high_severity_flags:
            return f"⚠️ Critical risk: {high_severity_flags[0].description}"

        flag_summaries = [f.description for f in flags[:2]]
        return "Risk factors: " + "; ".join(flag_summaries)
