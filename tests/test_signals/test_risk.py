"""Unit tests for risk score calculation."""

from datetime import date, timedelta
from decimal import Decimal
import pytest

from src.db.models import DailyMetric
from src.signals.risk import RiskCalculator


def create_mock_metric(
    days_ago: int = 0,
    reviews: int = 100,
    rating: float = 4.5,
    seller_count: int = 3,
) -> DailyMetric:
    """Create a mock DailyMetric for testing."""
    metric = DailyMetric.__new__(DailyMetric)
    metric.date = date.today() - timedelta(days=days_ago)
    metric.reviews = reviews
    metric.rating = rating
    metric.seller_count = seller_count
    metric.price = Decimal("29.99")
    metric.rank = 1000
    metric.in_stock = True
    return metric


class TestRiskCalculator:
    """Tests for RiskCalculator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.calculator = RiskCalculator()

    def test_insufficient_data(self):
        """Test with insufficient data points."""
        metrics = [create_mock_metric(0)]

        result = self.calculator.calculate(metrics)

        assert result.risk_level == "Unknown"
        assert "Insufficient data" in result.interpretation

    def test_no_risk_flags(self):
        """Test normal product with no risk indicators."""
        # Steady review growth, stable rating, stable sellers
        metrics = [
            create_mock_metric(days_ago=i, reviews=100 + i * 5, rating=4.5, seller_count=3)
            for i in range(14)
        ]

        result = self.calculator.calculate(metrics)

        assert result.risk_level in ["Low", "Medium"]
        assert len(result.flags) == 0 or all(f.severity == "low" for f in result.flags)

    def test_review_spike_detection(self):
        """Test detection of suspicious review spikes."""
        # Normal reviews then sudden spike
        metrics = [create_mock_metric(days_ago=i, reviews=100 + i * 2) for i in range(10)]
        # Add spike - 200 reviews in one day when average was ~4
        metrics.append(create_mock_metric(days_ago=0, reviews=400))

        result = self.calculator.calculate(metrics)

        assert result.signals.review_spike_detected
        assert result.signals.review_spike_magnitude > 3.0
        assert any(f.category == "review_manipulation" for f in result.flags)

    def test_seller_churn_detection(self):
        """Test detection of high seller churn."""
        # Seller count changes frequently
        metrics = [
            create_mock_metric(days_ago=9, seller_count=5),
            create_mock_metric(days_ago=8, seller_count=3),
            create_mock_metric(days_ago=7, seller_count=7),
            create_mock_metric(days_ago=6, seller_count=2),
            create_mock_metric(days_ago=5, seller_count=6),
            create_mock_metric(days_ago=4, seller_count=1),
            create_mock_metric(days_ago=3, seller_count=4),
            create_mock_metric(days_ago=2, seller_count=2),
            create_mock_metric(days_ago=1, seller_count=5),
            create_mock_metric(days_ago=0, seller_count=3),
        ]

        result = self.calculator.calculate(metrics)

        assert result.signals.seller_churn_rate > 0.5
        assert any(f.category == "seller_instability" for f in result.flags)

    def test_rating_volatility_detection(self):
        """Test detection of rating volatility."""
        # Wildly fluctuating ratings
        ratings = [4.5, 3.0, 4.8, 2.5, 4.0, 3.2, 4.7, 2.8]
        metrics = [
            create_mock_metric(days_ago=i, rating=ratings[i])
            for i in range(len(ratings))
        ]

        result = self.calculator.calculate(metrics)

        assert result.signals.rating_volatility > 0.5
        # May or may not flag depending on threshold

    def test_risk_level_thresholds(self):
        """Test risk level determination."""
        # Create high-risk scenario
        metrics = [create_mock_metric(days_ago=i, reviews=100 + i * 2) for i in range(10)]
        # Massive review spike
        metrics.append(create_mock_metric(days_ago=0, reviews=1000))

        result = self.calculator.calculate(metrics)

        assert result.risk_level in ["High", "Critical"]

    def test_interpretation_generation(self):
        """Test that interpretations are generated correctly."""
        metrics = [create_mock_metric(days_ago=i) for i in range(14)]

        result = self.calculator.calculate(metrics)

        assert isinstance(result.interpretation, str)
        assert len(result.interpretation) > 0
