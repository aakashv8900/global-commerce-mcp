"""Revenue estimation module.

Revenue Estimation Formula:
    estimated_daily_sales = a * (rank ^ -b)
    estimated_monthly_revenue = estimated_daily_sales * price * 30
    
Calibration constants are category-specific.
"""

from dataclasses import dataclass
from decimal import Decimal
import math

from src.db.models import DailyMetric


@dataclass
class RevenueEstimate:
    """Revenue estimation result."""

    estimated_daily_sales: float
    estimated_monthly_revenue: Decimal
    estimated_monthly_units: int
    confidence: float  # 0-1
    methodology: str


# Category-specific calibration constants for Amazon (BSR-based)
# Format: (a, b) where sales = a * (rank ^ -b)
# These are approximate values - would be calibrated with real data
AMAZON_CATEGORY_CALIBRATION = {
    "Electronics": (50000, 0.8),
    "Home & Kitchen": (30000, 0.75),
    "Toys & Games": (25000, 0.7),
    "Sports & Outdoors": (20000, 0.7),
    "Beauty & Personal Care": (35000, 0.75),
    "Health & Household": (30000, 0.72),
    "Clothing": (40000, 0.78),
    "Books": (60000, 0.85),
    "default": (25000, 0.72),
}

# Flipkart calibration constants (review-velocity based)
# Format: (multiplier, base_daily_sales) where sales = base + (review_velocity * multiplier)
# Since Flipkart doesn't have BSR, we estimate based on review accumulation rate
FLIPKART_CATEGORY_CALIBRATION = {
    "Electronics": (15.0, 5.0),       # High-ticket, lower volume
    "Mobiles": (12.0, 8.0),           # High volume category
    "Fashion": (20.0, 10.0),          # Very high volume
    "Home & Furniture": (10.0, 3.0),
    "Appliances": (8.0, 2.0),
    "Beauty": (18.0, 6.0),
    "Toys & Baby": (12.0, 4.0),
    "Sports": (10.0, 3.0),
    "Books": (25.0, 2.0),
    "Grocery": (30.0, 15.0),          # Very high velocity
    "default": (15.0, 5.0),
}

# Keep legacy alias for backward compatibility
CATEGORY_CALIBRATION = AMAZON_CATEGORY_CALIBRATION


class RevenueEstimator:
    """Estimator for product revenue based on rank and price."""

    def estimate(
        self,
        metrics: list[DailyMetric],
        category: str = "default",
    ) -> RevenueEstimate:
        """Estimate monthly revenue from rank and price."""
        if not metrics:
            return RevenueEstimate(
                estimated_daily_sales=0.0,
                estimated_monthly_revenue=Decimal("0.00"),
                estimated_monthly_units=0,
                confidence=0.0,
                methodology="No data available",
            )

        # Get latest metric
        latest = max(metrics, key=lambda m: m.date)

        if latest.rank is None or latest.rank == 0:
            return RevenueEstimate(
                estimated_daily_sales=0.0,
                estimated_monthly_revenue=Decimal("0.00"),
                estimated_monthly_units=0,
                confidence=0.0,
                methodology="No rank data available",
            )

        # Get calibration constants
        a, b = CATEGORY_CALIBRATION.get(category, CATEGORY_CALIBRATION["default"])

        # Calculate daily sales using power law
        daily_sales = self._calculate_daily_sales(latest.rank, a, b)

        # Calculate monthly metrics
        monthly_units = int(daily_sales * 30)
        monthly_revenue = Decimal(str(daily_sales * 30)) * latest.price

        # Calculate confidence based on data quality
        confidence = self._calculate_confidence(metrics, latest)

        methodology = (
            f"Power law model (a={a}, b={b}) for {category} category. "
            f"Based on BSR #{latest.rank:,}."
        )

        return RevenueEstimate(
            estimated_daily_sales=round(daily_sales, 2),
            estimated_monthly_revenue=round(monthly_revenue, 2),
            estimated_monthly_units=monthly_units,
            confidence=confidence,
            methodology=methodology,
        )

    def _calculate_daily_sales(self, rank: int, a: float, b: float) -> float:
        """Calculate estimated daily sales from rank using power law."""
        if rank <= 0:
            return 0.0

        # sales = a * (rank ^ -b)
        daily_sales = a * math.pow(rank, -b)

        # Apply reasonable bounds
        return max(0.1, min(daily_sales, 10000))  # 0.1 to 10k units/day

    def _calculate_confidence(
        self, metrics: list[DailyMetric], latest: DailyMetric
    ) -> float:
        """Calculate confidence score for the estimate."""
        confidence = 0.5  # Base confidence

        # More data = higher confidence
        if len(metrics) >= 30:
            confidence += 0.2
        elif len(metrics) >= 14:
            confidence += 0.1

        # Stable rank = higher confidence
        if len(metrics) >= 7:
            ranks = [m.rank for m in metrics if m.rank is not None]
            if ranks:
                avg_rank = sum(ranks) / len(ranks)
                if latest.rank:
                    rank_deviation = abs(latest.rank - avg_rank) / avg_rank if avg_rank else 0
                    if rank_deviation < 0.1:
                        confidence += 0.1
                    elif rank_deviation < 0.25:
                        confidence += 0.05

        # High review count = higher confidence (more established product)
        if latest.reviews > 1000:
            confidence += 0.1
        elif latest.reviews > 100:
            confidence += 0.05

        return min(confidence, 0.95)  # Cap at 95%

    def estimate_from_rank(
        self, rank: int, price: Decimal, category: str = "default"
    ) -> RevenueEstimate:
        """Quick estimation from just rank and price."""
        if rank <= 0:
            return RevenueEstimate(
                estimated_daily_sales=0.0,
                estimated_monthly_revenue=Decimal("0.00"),
                estimated_monthly_units=0,
                confidence=0.3,
                methodology="Direct rank estimation (low confidence)",
            )

        a, b = CATEGORY_CALIBRATION.get(category, CATEGORY_CALIBRATION["default"])
        daily_sales = self._calculate_daily_sales(rank, a, b)
        monthly_units = int(daily_sales * 30)
        monthly_revenue = Decimal(str(daily_sales * 30)) * price

        return RevenueEstimate(
            estimated_daily_sales=round(daily_sales, 2),
            estimated_monthly_revenue=round(monthly_revenue, 2),
            estimated_monthly_units=monthly_units,
            confidence=0.5,  # Lower confidence for single-point estimate
            methodology=f"Power law estimate for {category} at BSR #{rank:,}",
        )

    def estimate_from_reviews(
        self,
        metrics: list[DailyMetric],
        price: Decimal,
        category: str = "default",
    ) -> RevenueEstimate:
        """Estimate revenue for Flipkart products based on review velocity.
        
        Since Flipkart doesn't have BSR, we use review velocity as a proxy for sales.
        The assumption is that ~1-5% of buyers leave reviews.
        """
        if len(metrics) < 7:
            return RevenueEstimate(
                estimated_daily_sales=0.0,
                estimated_monthly_revenue=Decimal("0.00"),
                estimated_monthly_units=0,
                confidence=0.2,
                methodology="Insufficient data (need 7+ days for Flipkart estimation)",
            )

        # Calculate review velocity (reviews per day)
        sorted_metrics = sorted(metrics, key=lambda m: m.date)
        first = sorted_metrics[0]
        last = sorted_metrics[-1]
        
        days_diff = (last.date - first.date).days
        if days_diff <= 0:
            days_diff = 1
        
        review_diff = last.reviews - first.reviews
        review_velocity = review_diff / days_diff if days_diff > 0 else 0

        # Get Flipkart calibration constants
        multiplier, base_sales = FLIPKART_CATEGORY_CALIBRATION.get(
            category, FLIPKART_CATEGORY_CALIBRATION["default"]
        )

        # Estimate daily sales based on review velocity
        # Assumption: only 2-5% of buyers leave reviews
        daily_sales = base_sales + (review_velocity * multiplier)
        daily_sales = max(0.5, min(daily_sales, 5000))  # Reasonable bounds

        monthly_units = int(daily_sales * 30)
        monthly_revenue = Decimal(str(daily_sales * 30)) * price

        # Calculate confidence
        confidence = 0.4  # Base confidence for review-based estimation
        if len(metrics) >= 30:
            confidence += 0.15
        elif len(metrics) >= 14:
            confidence += 0.1
        
        if last.reviews > 1000:
            confidence += 0.1
        elif last.reviews > 100:
            confidence += 0.05

        confidence = min(confidence, 0.75)  # Cap at 75% for review-based estimates

        return RevenueEstimate(
            estimated_daily_sales=round(daily_sales, 2),
            estimated_monthly_revenue=round(monthly_revenue, 2),
            estimated_monthly_units=monthly_units,
            confidence=confidence,
            methodology=f"Review velocity estimate for {category}: {review_velocity:.2f} reviews/day → {daily_sales:.1f} sales/day",
        )
