"""Main intelligence engine that orchestrates all signal calculations."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import uuid

from src.db.models import Product, DailyMetric
from src.signals import (
    DemandCalculator,
    CompetitionCalculator,
    RevenueEstimator,
    TrendCalculator,
    RiskCalculator,
    DiscountCyclePredictor,
)
from src.signals.demand import DemandResult
from src.signals.competition import CompetitionResult
from src.signals.revenue import RevenueEstimate
from src.signals.trend import TrendResult
from src.signals.risk import RiskResult
from src.signals.discount_cycle import DiscountCyclePrediction


@dataclass
class ProductIntelligence:
    """Complete intelligence report for a product."""

    product_id: uuid.UUID
    asin: str
    title: str
    category: str
    platform: str
    analysis_date: date

    # Current metrics
    current_price: Decimal
    current_rank: int | None
    current_reviews: int
    current_rating: float

    # Intelligence scores
    demand: DemandResult
    competition: CompetitionResult
    revenue: RevenueEstimate
    trend: TrendResult
    risk: RiskResult
    discount_prediction: DiscountCyclePrediction

    # Summary
    overall_score: float
    verdict: str
    confidence: float
    insights: list[str]


@dataclass
class SellerIntelligence:
    """Intelligence report for a seller."""

    seller_id: str
    name: str
    platform: str

    competition_index: float
    review_manipulation_risk: str
    fulfillment_pattern: str
    stockout_frequency: float

    verdict: str
    insights: list[str]


@dataclass
class TrendingProduct:
    """A trending product entry."""

    asin: str
    title: str
    rank: int | None
    trend_score: float
    review_velocity: float
    rank_improvement: float


class IntelligenceEngine:
    """Main engine that computes complete product intelligence."""

    def __init__(self):
        self.demand_calc = DemandCalculator()
        self.competition_calc = CompetitionCalculator()
        self.revenue_est = RevenueEstimator()
        self.trend_calc = TrendCalculator()
        self.risk_calc = RiskCalculator()
        self.discount_pred = DiscountCyclePredictor()

    def analyze_product(
        self, product: Product, metrics: list[DailyMetric]
    ) -> ProductIntelligence:
        """Generate complete intelligence for a product."""
        # Get latest metrics
        latest = max(metrics, key=lambda m: m.date) if metrics else None

        # Calculate all signals
        demand = self.demand_calc.calculate(metrics)
        competition = self.competition_calc.calculate(metrics)
        revenue = self.revenue_est.estimate(metrics, product.category)
        trend = self.trend_calc.calculate(metrics)
        risk = self.risk_calc.calculate(metrics)
        discount = self.discount_pred.predict(metrics)

        # Calculate overall score
        overall = self._calculate_overall_score(demand, competition, trend, risk)

        # Generate verdict
        verdict = self._generate_verdict(demand, competition, trend, risk, revenue)

        # Generate insights
        insights = self._generate_insights(demand, competition, trend, risk, discount)

        # Calculate confidence
        confidence = self._calculate_confidence(len(metrics), revenue, risk)

        return ProductIntelligence(
            product_id=product.id,
            asin=product.asin,
            title=product.title,
            category=product.category,
            platform=product.platform,
            analysis_date=date.today(),
            current_price=latest.price if latest else Decimal("0"),
            current_rank=latest.rank if latest else None,
            current_reviews=latest.reviews if latest else 0,
            current_rating=float(latest.rating) if latest else 0.0,
            demand=demand,
            competition=competition,
            revenue=revenue,
            trend=trend,
            risk=risk,
            discount_prediction=discount,
            overall_score=overall,
            verdict=verdict,
            confidence=confidence,
            insights=insights,
        )

    def _calculate_overall_score(
        self,
        demand: DemandResult,
        competition: CompetitionResult,
        trend: TrendResult,
        risk: RiskResult,
    ) -> float:
        """Calculate overall opportunity score (0-100)."""
        # Weights: demand most important, then trend, then inverse competition/risk
        demand_weight = 0.35
        trend_weight = 0.25
        competition_weight = 0.20  # Inverted
        risk_weight = 0.20  # Inverted

        # Normalize trend score from -100/+100 to 0-100
        normalized_trend = (trend.score + 100) / 2

        # Invert competition and risk (lower = better)
        inverted_competition = 100 - competition.score
        inverted_risk = 100 - risk.score

        score = (
            demand.score * demand_weight
            + normalized_trend * trend_weight
            + inverted_competition * competition_weight
            + inverted_risk * risk_weight
        )

        return round(score, 1)

    def _generate_verdict(
        self,
        demand: DemandResult,
        competition: CompetitionResult,
        trend: TrendResult,
        risk: RiskResult,
        revenue: RevenueEstimate,
    ) -> str:
        """Generate executive verdict."""
        verdicts = []

        # Demand assessment
        if demand.score >= 70:
            verdicts.append("High-demand product")
        elif demand.score >= 40:
            verdicts.append("Moderate demand")
        else:
            verdicts.append("Low demand")

        # Competition assessment
        if competition.score >= 70:
            verdicts.append("with intense competition")
        elif competition.score >= 40:
            verdicts.append("with moderate competition")
        else:
            verdicts.append("with low competition")

        # Trend assessment
        if trend.score > 30:
            verdicts.append("showing accelerating growth")
        elif trend.score < -30:
            verdicts.append("showing declining trend")

        # Risk flags
        if risk.score >= 50:
            verdicts.append("⚠️ Elevated risk detected")

        # Revenue context
        verdicts.append(
            f"Est. ${revenue.estimated_monthly_revenue:,.0f}/mo revenue"
        )

        # Recommendation
        if demand.score >= 60 and competition.score <= 50 and risk.score <= 40:
            verdicts.append("✅ Good private label opportunity")
        elif demand.score >= 70 and competition.score >= 70:
            verdicts.append("Consider differentiation strategy")

        return ". ".join(verdicts) + "."

    def _generate_insights(
        self,
        demand: DemandResult,
        competition: CompetitionResult,
        trend: TrendResult,
        risk: RiskResult,
        discount: DiscountCyclePrediction,
    ) -> list[str]:
        """Generate top 5 actionable insights."""
        insights = []

        # Demand insight
        if demand.score >= 60:
            insights.append(
                f"Strong demand signal: {demand.interpretation}"
            )
        elif demand.score <= 30:
            insights.append(
                "Low demand indicators - consider alternative products"
            )

        # Competition insight
        insights.append(
            f"Competition level: {competition.barrier_to_entry} barrier to entry"
        )

        # Trend insight
        if trend.trend_direction == "Accelerating":
            insights.append(
                f"Positive momentum: {trend.interpretation}"
            )
        elif trend.trend_direction == "Declining":
            insights.append(
                f"Market declining: {trend.interpretation}"
            )

        # Risk insights
        for flag in risk.flags[:2]:
            insights.append(f"Risk: {flag.description}")

        # Discount cycle insight
        if discount.next_predicted_discount:
            days_until = (discount.next_predicted_discount - date.today()).days
            if 0 < days_until <= 14:
                insights.append(
                    f"💰 Discount expected in ~{days_until} days"
                )

        return insights[:5]

    def _calculate_confidence(
        self, data_points: int, revenue: RevenueEstimate, risk: RiskResult
    ) -> float:
        """Calculate overall confidence in the analysis."""
        # Base on data availability
        if data_points >= 60:
            data_confidence = 0.9
        elif data_points >= 30:
            data_confidence = 0.7
        elif data_points >= 14:
            data_confidence = 0.5
        else:
            data_confidence = 0.3

        # Combine with revenue confidence
        return round((data_confidence + revenue.confidence) / 2, 2)

    def get_trending_products(
        self, products_with_metrics: list[tuple[Product, list[DailyMetric]]], limit: int = 10
    ) -> list[TrendingProduct]:
        """Get top trending products from a list."""
        scored = []

        for product, metrics in products_with_metrics:
            trend = self.trend_calc.calculate(metrics)
            demand = self.demand_calc.calculate(metrics)

            latest = max(metrics, key=lambda m: m.date) if metrics else None

            scored.append(TrendingProduct(
                asin=product.asin,
                title=product.title,
                rank=latest.rank if latest else None,
                trend_score=trend.score,
                review_velocity=demand.signals.review_velocity,
                rank_improvement=demand.signals.rank_improvement,
            ))

        # Sort by trend score descending
        scored.sort(key=lambda x: x.trend_score, reverse=True)
        return scored[:limit]
