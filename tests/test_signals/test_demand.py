"""Unit tests for demand score calculation."""

from datetime import date, timedelta
from decimal import Decimal
import pytest

from src.db.models import DailyMetric
from src.signals.demand import DemandCalculator, DemandResult


def create_mock_metric(
    days_ago: int,
    reviews: int,
    rank: int | None,
    price: Decimal,
    in_stock: bool = True,
) -> DailyMetric:
    """Create a mock DailyMetric for testing."""
    metric = DailyMetric.__new__(DailyMetric)
    metric.date = date.today() - timedelta(days=days_ago)
    metric.reviews = reviews
    metric.rank = rank
    metric.price = price
    metric.in_stock = in_stock
    metric.rating = 4.5
    metric.seller_count = 3
    return metric


class TestDemandCalculator:
    """Tests for DemandCalculator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.calculator = DemandCalculator()

    def test_insufficient_data(self):
        """Test with insufficient data points."""
        metrics = [create_mock_metric(0, 100, 1000, Decimal("29.99"))]
        result = self.calculator.calculate(metrics)

        assert result.score == 0.0
        assert "Insufficient data" in result.interpretation

    def test_high_demand_signals(self):
        """Test calculation with high demand signals."""
        # Create metrics showing increasing reviews and improving rank
        metrics = [
            create_mock_metric(30, 100, 5000, Decimal("25.00")),
            create_mock_metric(20, 200, 3000, Decimal("27.00")),
            create_mock_metric(10, 400, 2000, Decimal("28.00")),
            create_mock_metric(0, 700, 1000, Decimal("29.99")),
        ]

        result = self.calculator.calculate(metrics)

        assert result.score > 50  # Should be high demand
        assert result.signals.review_velocity > 0
        assert result.signals.rank_improvement > 0

    def test_low_demand_signals(self):
        """Test calculation with low demand signals."""
        # Create metrics showing stagnant or declining signals
        metrics = [
            create_mock_metric(30, 1000, 1000, Decimal("29.99")),
            create_mock_metric(20, 1005, 1100, Decimal("28.00")),
            create_mock_metric(10, 1008, 1200, Decimal("27.00")),
            create_mock_metric(0, 1010, 1500, Decimal("25.00")),
        ]

        result = self.calculator.calculate(metrics)

        assert result.score < 40  # Should be low demand
        assert result.signals.rank_improvement < 0  # Rank worsened

    def test_stockout_frequency(self):
        """Test stockout frequency calculation."""
        metrics = [
            create_mock_metric(3, 100, 1000, Decimal("29.99"), in_stock=True),
            create_mock_metric(2, 102, 1000, Decimal("29.99"), in_stock=False),
            create_mock_metric(1, 104, 1000, Decimal("29.99"), in_stock=False),
            create_mock_metric(0, 106, 1000, Decimal("29.99"), in_stock=True),
        ]

        result = self.calculator.calculate(metrics)

        # 2 out of 4 days out of stock = 50%
        assert 0.4 <= result.signals.stockout_frequency <= 0.6

    def test_price_increase_signal(self):
        """Test price increase detection."""
        metrics = [
            create_mock_metric(7, 100, 1000, Decimal("20.00")),
            create_mock_metric(0, 105, 1000, Decimal("30.00")),
        ]

        result = self.calculator.calculate(metrics)

        # 50% price increase
        assert result.signals.price_increase == 0.5

    def test_interpretation_generation(self):
        """Test that interpretations are generated correctly."""
        metrics = [
            create_mock_metric(30, 100, 5000, Decimal("25.00")),
            create_mock_metric(0, 600, 1000, Decimal("30.00")),
        ]

        result = self.calculator.calculate(metrics)

        assert isinstance(result.interpretation, str)
        assert len(result.interpretation) > 0
