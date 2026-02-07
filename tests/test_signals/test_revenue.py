"""Unit tests for revenue estimation."""

from datetime import date, timedelta
from decimal import Decimal
import pytest

from src.db.models import DailyMetric
from src.signals.revenue import RevenueEstimator, CATEGORY_CALIBRATION


def create_mock_metric(
    days_ago: int = 0,
    rank: int | None = 1000,
    price: Decimal = Decimal("29.99"),
    reviews: int = 500,
) -> DailyMetric:
    """Create a mock DailyMetric for testing."""
    metric = DailyMetric.__new__(DailyMetric)
    metric.date = date.today() - timedelta(days=days_ago)
    metric.rank = rank
    metric.price = price
    metric.reviews = reviews
    metric.rating = 4.5
    return metric


class TestRevenueEstimator:
    """Tests for RevenueEstimator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.estimator = RevenueEstimator()

    def test_no_data(self):
        """Test with no metrics data."""
        result = self.estimator.estimate([])

        assert result.estimated_daily_sales == 0.0
        assert result.estimated_monthly_revenue == Decimal("0.00")
        assert result.confidence == 0.0

    def test_no_rank(self):
        """Test with missing rank data."""
        metrics = [create_mock_metric(rank=None)]

        result = self.estimator.estimate(metrics)

        assert result.estimated_daily_sales == 0.0
        assert "No rank data" in result.methodology

    def test_high_rank_product(self):
        """Test estimation for high-ranking product (low BSR number)."""
        metrics = [create_mock_metric(rank=100, price=Decimal("49.99"))]

        result = self.estimator.estimate(metrics, category="Electronics")

        # High rank should have high sales
        assert result.estimated_daily_sales > 50
        assert result.estimated_monthly_revenue > Decimal("50000")

    def test_low_rank_product(self):
        """Test estimation for low-ranking product (high BSR number)."""
        metrics = [create_mock_metric(rank=100000, price=Decimal("29.99"))]

        result = self.estimator.estimate(metrics, category="Electronics")

        # Low rank should have low sales
        assert result.estimated_daily_sales < 10
        assert result.estimated_monthly_revenue < Decimal("10000")

    def test_category_calibration(self):
        """Test that different categories have different calibrations."""
        metrics = [create_mock_metric(rank=1000, price=Decimal("29.99"))]

        electronics_result = self.estimator.estimate(metrics, category="Electronics")
        books_result = self.estimator.estimate(metrics, category="Books")

        # Different categories should yield different results
        assert electronics_result.estimated_monthly_revenue != books_result.estimated_monthly_revenue

    def test_confidence_with_more_data(self):
        """Test that more data points increase confidence."""
        # Few data points
        few_metrics = [create_mock_metric(i, rank=1000) for i in range(5)]
        
        # Many data points
        many_metrics = [create_mock_metric(i, rank=1000, reviews=500 + i * 10) for i in range(60)]

        few_result = self.estimator.estimate(few_metrics)
        many_result = self.estimator.estimate(many_metrics)

        assert many_result.confidence > few_result.confidence

    def test_stable_rank_increases_confidence(self):
        """Test that stable rank increases confidence."""
        # Stable rank (all same)
        stable_metrics = [create_mock_metric(i, rank=1000, reviews=500 + i * 10) for i in range(14)]
        
        result = self.estimator.estimate(stable_metrics)

        assert result.confidence >= 0.5

    def test_estimate_from_rank_direct(self):
        """Test direct estimation from rank and price."""
        result = self.estimator.estimate_from_rank(
            rank=500,
            price=Decimal("39.99"),
            category="Electronics",
        )

        assert result.estimated_daily_sales > 0
        assert result.estimated_monthly_revenue > Decimal("0")
        assert result.confidence == 0.5  # Lower confidence for single-point estimate

    def test_power_law_relationship(self):
        """Test that sales follow power law (lower rank = higher sales)."""
        rank_100 = self.estimator.estimate_from_rank(100, Decimal("29.99"))
        rank_1000 = self.estimator.estimate_from_rank(1000, Decimal("29.99"))
        rank_10000 = self.estimator.estimate_from_rank(10000, Decimal("29.99"))

        assert rank_100.estimated_daily_sales > rank_1000.estimated_daily_sales
        assert rank_1000.estimated_daily_sales > rank_10000.estimated_daily_sales
