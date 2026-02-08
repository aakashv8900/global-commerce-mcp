"""Brand intelligence analyzer for portfolio analysis and competitive positioning."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from src.db.models import Brand, BrandMetric, Product, DailyMetric


@dataclass
class BrandHealth:
    """Brand health metrics."""
    score: float  # 0-100
    trend: str  # "improving", "stable", "declining"
    strengths: list[str]
    weaknesses: list[str]
    interpretation: str


@dataclass
class BrandCompetitivePosition:
    """Brand's competitive position in category."""
    market_share_percent: float
    rank_in_category: int
    total_competitors: int
    price_positioning: str  # "premium", "mid-range", "value"
    review_advantage: float  # vs category average
    momentum: str  # "gaining", "stable", "losing"


@dataclass
class BrandIntelligence:
    """Complete intelligence report for a brand."""
    brand_id: str
    name: str
    platform: str
    category: str
    analysis_date: date

    # Portfolio metrics
    product_count: int
    total_revenue_estimate: Decimal
    avg_product_price: Decimal
    avg_product_rating: float
    total_reviews: int

    # Calculated intelligence
    health: BrandHealth
    competitive_position: BrandCompetitivePosition

    # Trends
    revenue_trend_30d: float  # percent change
    review_velocity: float  # reviews per day
    product_growth: int  # new products in 30 days

    # Recommendations
    verdict: str
    insights: list[str]


@dataclass
class BrandComparison:
    """Comparison between multiple brands."""
    brands: list[str]
    category: str
    comparison_date: date

    # Per-brand metrics (same order as brands list)
    revenues: list[Decimal]
    market_shares: list[float]
    avg_ratings: list[float]
    product_counts: list[int]

    # Analysis
    leader: str
    fastest_growing: str
    best_rated: str
    insights: list[str]


class BrandAnalyzer:
    """Analyzes brands for portfolio insights and competitive intelligence."""

    def analyze_brand(
        self,
        brand: Brand,
        metrics: list[BrandMetric],
        products: list[Product],
        product_metrics: list[list[DailyMetric]],
    ) -> BrandIntelligence:
        """Generate complete intelligence for a brand."""
        latest_metric = metrics[0] if metrics else None

        # Calculate health score
        health = self._calculate_health(metrics)

        # Calculate competitive position
        position = self._calculate_competitive_position(
            brand, latest_metric, products
        )

        # Calculate trends
        revenue_trend = self._calculate_revenue_trend(metrics)
        review_velocity = self._calculate_review_velocity(metrics)
        product_growth = self._calculate_product_growth(products)

        # Generate verdict and insights
        verdict = self._generate_verdict(health, position, revenue_trend)
        insights = self._generate_insights(
            brand, health, position, revenue_trend, products
        )

        return BrandIntelligence(
            brand_id=str(brand.id),
            name=brand.name,
            platform=brand.platform,
            category=brand.category or "Unknown",
            analysis_date=date.today(),
            product_count=len(products),
            total_revenue_estimate=latest_metric.revenue_estimate if latest_metric else Decimal("0"),
            avg_product_price=latest_metric.avg_price if latest_metric else Decimal("0"),
            avg_product_rating=latest_metric.avg_rating if latest_metric else 0.0,
            total_reviews=latest_metric.total_reviews if latest_metric else 0,
            health=health,
            competitive_position=position,
            revenue_trend_30d=revenue_trend,
            review_velocity=review_velocity,
            product_growth=product_growth,
            verdict=verdict,
            insights=insights,
        )

    def compare_brands(
        self,
        brands: list[Brand],
        brand_metrics: list[list[BrandMetric]],
    ) -> BrandComparison:
        """Compare multiple brands in the same category."""
        brand_names = [b.name for b in brands]
        category = brands[0].category if brands else "Unknown"

        revenues = []
        market_shares = []
        avg_ratings = []
        product_counts = []

        for metrics in brand_metrics:
            if metrics:
                latest = metrics[0]
                revenues.append(latest.revenue_estimate)
                market_shares.append(float(latest.market_share_percent))
                avg_ratings.append(float(latest.avg_rating))
                product_counts.append(latest.product_count)
            else:
                revenues.append(Decimal("0"))
                market_shares.append(0.0)
                avg_ratings.append(0.0)
                product_counts.append(0)

        # Find leaders
        leader_idx = max(range(len(revenues)), key=lambda i: revenues[i])
        best_rated_idx = max(range(len(avg_ratings)), key=lambda i: avg_ratings[i])

        # Calculate growth rates
        growth_rates = []
        for metrics in brand_metrics:
            if len(metrics) >= 2:
                old = metrics[-1].revenue_estimate
                new = metrics[0].revenue_estimate
                if old > 0:
                    growth_rates.append(float((new - old) / old * 100))
                else:
                    growth_rates.append(0.0)
            else:
                growth_rates.append(0.0)

        fastest_idx = max(range(len(growth_rates)), key=lambda i: growth_rates[i])

        # Generate insights
        insights = self._generate_comparison_insights(
            brand_names, revenues, market_shares, avg_ratings, growth_rates
        )

        return BrandComparison(
            brands=brand_names,
            category=category,
            comparison_date=date.today(),
            revenues=revenues,
            market_shares=market_shares,
            avg_ratings=avg_ratings,
            product_counts=product_counts,
            leader=brand_names[leader_idx],
            fastest_growing=brand_names[fastest_idx],
            best_rated=brand_names[best_rated_idx],
            insights=insights,
        )

    def _calculate_health(self, metrics: list[BrandMetric]) -> BrandHealth:
        """Calculate brand health score."""
        if not metrics:
            return BrandHealth(
                score=50.0,
                trend="stable",
                strengths=[],
                weaknesses=["Insufficient data"],
                interpretation="Not enough data for health analysis",
            )

        latest = metrics[0]
        score = 50.0
        strengths = []
        weaknesses = []

        # Rating factor
        if latest.avg_rating >= 4.5:
            score += 15
            strengths.append("Excellent customer satisfaction")
        elif latest.avg_rating >= 4.0:
            score += 8
        elif latest.avg_rating < 3.5:
            score -= 10
            weaknesses.append("Below average ratings")

        # Review volume
        if latest.total_reviews > 10000:
            score += 10
            strengths.append("Strong review base")
        elif latest.total_reviews > 1000:
            score += 5

        # Product count
        if latest.product_count >= 50:
            score += 10
            strengths.append("Diverse product portfolio")
        elif latest.product_count <= 5:
            score -= 5
            weaknesses.append("Limited product range")

        # Revenue trend
        if len(metrics) >= 7:
            old_rev = metrics[-1].revenue_estimate
            new_rev = metrics[0].revenue_estimate
            if old_rev > 0:
                growth = float((new_rev - old_rev) / old_rev * 100)
                if growth > 20:
                    score += 15
                    strengths.append("Strong revenue growth")
                    trend = "improving"
                elif growth > 0:
                    score += 5
                    trend = "stable"
                else:
                    score -= 10
                    weaknesses.append("Declining revenue")
                    trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        score = max(0, min(100, score))

        interpretation = self._interpret_health_score(score, trend)

        return BrandHealth(
            score=score,
            trend=trend,
            strengths=strengths,
            weaknesses=weaknesses,
            interpretation=interpretation,
        )

    def _interpret_health_score(self, score: float, trend: str) -> str:
        """Generate health interpretation text."""
        if score >= 80:
            base = "Excellent brand health with strong fundamentals"
        elif score >= 60:
            base = "Good brand health with room for improvement"
        elif score >= 40:
            base = "Moderate brand health requiring attention"
        else:
            base = "Concerning brand health requiring immediate action"

        if trend == "improving":
            return f"{base}. Positive momentum suggests continued growth."
        elif trend == "declining":
            return f"{base}. Declining trend warrants investigation."
        return base

    def _calculate_competitive_position(
        self,
        brand: Brand,
        latest_metric: BrandMetric | None,
        products: list[Product],
    ) -> BrandCompetitivePosition:
        """Calculate brand's competitive position."""
        if not latest_metric:
            return BrandCompetitivePosition(
                market_share_percent=0.0,
                rank_in_category=0,
                total_competitors=0,
                price_positioning="mid-range",
                review_advantage=0.0,
                momentum="stable",
            )

        # Price positioning based on average price
        avg_price = float(latest_metric.avg_price)
        if avg_price > 100:
            price_positioning = "premium"
        elif avg_price > 30:
            price_positioning = "mid-range"
        else:
            price_positioning = "value"

        return BrandCompetitivePosition(
            market_share_percent=float(latest_metric.market_share_percent),
            rank_in_category=1,  # Would be calculated from category data
            total_competitors=10,  # Would be calculated from category data
            price_positioning=price_positioning,
            review_advantage=0.0,  # Would compare to category average
            momentum="stable",
        )

    def _calculate_revenue_trend(self, metrics: list[BrandMetric]) -> float:
        """Calculate 30-day revenue trend as percent change."""
        if len(metrics) < 2:
            return 0.0

        old = metrics[-1].revenue_estimate
        new = metrics[0].revenue_estimate

        if old <= 0:
            return 0.0

        return float((new - old) / old * 100)

    def _calculate_review_velocity(self, metrics: list[BrandMetric]) -> float:
        """Calculate average review velocity."""
        if not metrics:
            return 0.0
        return float(sum(m.review_velocity for m in metrics) / len(metrics))

    def _calculate_product_growth(self, products: list[Product]) -> int:
        """Calculate new products added in last 30 days."""
        from datetime import timedelta
        cutoff = date.today() - timedelta(days=30)
        return sum(1 for p in products if p.created_at.date() >= cutoff)

    def _generate_verdict(
        self,
        health: BrandHealth,
        position: BrandCompetitivePosition,
        revenue_trend: float,
    ) -> str:
        """Generate executive verdict for the brand."""
        if health.score >= 80 and revenue_trend > 10:
            return "🚀 High-performing brand with strong growth trajectory"
        elif health.score >= 60:
            return "✅ Solid brand with stable performance"
        elif health.score >= 40:
            return "⚠️ Brand showing mixed signals, monitor closely"
        else:
            return "🔴 Underperforming brand requiring strategic review"

    def _generate_insights(
        self,
        brand: Brand,
        health: BrandHealth,
        position: BrandCompetitivePosition,
        revenue_trend: float,
        products: list[Product],
    ) -> list[str]:
        """Generate actionable insights for the brand."""
        insights = []

        if health.score >= 70:
            insights.append(f"{brand.name} maintains strong brand equity with consistent customer satisfaction")

        if revenue_trend > 20:
            insights.append(f"Revenue growth of {revenue_trend:.1f}% suggests successful product strategy")
        elif revenue_trend < -10:
            insights.append(f"Revenue decline of {abs(revenue_trend):.1f}% warrants competitive analysis")

        if position.price_positioning == "premium":
            insights.append("Premium pricing strategy indicates strong brand differentiation")

        if len(products) > 20:
            insights.append(f"Portfolio of {len(products)} products provides good category coverage")

        if health.strengths:
            insights.append(f"Key strength: {health.strengths[0]}")

        return insights[:5]

    def _generate_comparison_insights(
        self,
        brands: list[str],
        revenues: list[Decimal],
        market_shares: list[float],
        avg_ratings: list[float],
        growth_rates: list[float],
    ) -> list[str]:
        """Generate insights from brand comparison."""
        insights = []

        if len(brands) >= 2:
            leader_idx = max(range(len(revenues)), key=lambda i: revenues[i])
            insights.append(f"{brands[leader_idx]} leads with ${revenues[leader_idx]:,.0f} estimated monthly revenue")

            if max(growth_rates) > 30:
                fastest_idx = max(range(len(growth_rates)), key=lambda i: growth_rates[i])
                insights.append(f"{brands[fastest_idx]} growing fastest at {growth_rates[fastest_idx]:.1f}%")

            # Rating insights
            best_rated_idx = max(range(len(avg_ratings)), key=lambda i: avg_ratings[i])
            if avg_ratings[best_rated_idx] > 4.5:
                insights.append(f"{brands[best_rated_idx]} excels in customer satisfaction ({avg_ratings[best_rated_idx]:.1f}⭐)")

        return insights
