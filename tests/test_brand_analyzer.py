"""Tests for Brand Intelligence module."""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock
import uuid


class TestBrandAnalyzer:
    """Tests for BrandAnalyzer class."""

    def test_calculate_health_score_high_rating(self):
        """Test health score calculation with high rating."""
        from src.intelligence.brand_analyzer import BrandAnalyzer

        analyzer = BrandAnalyzer()

        metrics = [
            MagicMock(
                avg_rating=4.5,
                total_reviews=10000,
                review_velocity=100.0,
                revenue_estimate=Decimal("500000"),
                market_share_percent=15.0,
                product_count=50,
            )
        ]

        score = analyzer.calculate_health_score(metrics)
        assert score >= 70, "High-performing brand should have high health score"

    def test_calculate_health_score_low_rating(self):
        """Test health score calculation with low rating."""
        from src.intelligence.brand_analyzer import BrandAnalyzer

        analyzer = BrandAnalyzer()

        metrics = [
            MagicMock(
                avg_rating=2.5,
                total_reviews=100,
                review_velocity=5.0,
                revenue_estimate=Decimal("10000"),
                market_share_percent=0.5,
                product_count=3,
            )
        ]

        score = analyzer.calculate_health_score(metrics)
        assert score < 50, "Low-performing brand should have low health score"

    def test_calculate_health_score_no_metrics(self):
        """Test health score with no metrics."""
        from src.intelligence.brand_analyzer import BrandAnalyzer

        analyzer = BrandAnalyzer()
        score = analyzer.calculate_health_score([])
        assert score == 0, "No metrics should return 0 health score"

    def test_get_trend_direction_growing(self):
        """Test trend detection for growing brand."""
        from src.intelligence.brand_analyzer import BrandAnalyzer

        analyzer = BrandAnalyzer()

        # Simulate growing revenue
        metrics = []
        base_revenue = Decimal("100000")
        for i in range(7):
            metrics.append(
                MagicMock(
                    date=date.today() - timedelta(days=6 - i),
                    revenue_estimate=base_revenue + Decimal(str(i * 10000)),
                    total_reviews=1000 + i * 100,
                )
            )

        trend = analyzer.get_trend_direction(metrics)
        assert trend in ["growing", "stable"], "Should detect positive trend"

    def test_get_trend_direction_declining(self):
        """Test trend detection for declining brand."""
        from src.intelligence.brand_analyzer import BrandAnalyzer

        analyzer = BrandAnalyzer()

        # Simulate declining revenue
        metrics = []
        base_revenue = Decimal("100000")
        for i in range(7):
            metrics.append(
                MagicMock(
                    date=date.today() - timedelta(days=6 - i),
                    revenue_estimate=base_revenue - Decimal(str(i * 15000)),
                    total_reviews=1000 - i * 100,
                )
            )

        trend = analyzer.get_trend_direction(metrics)
        assert trend in ["declining", "stable"], "Should detect negative trend"


class TestBrandComparison:
    """Tests for brand comparison functionality."""

    def test_compare_two_brands(self):
        """Test comparing two brands."""
        from src.intelligence.brand_analyzer import BrandAnalyzer

        analyzer = BrandAnalyzer()

        brand1_metrics = [
            MagicMock(
                avg_rating=4.5,
                total_reviews=10000,
                revenue_estimate=Decimal("500000"),
                market_share_percent=20.0,
            )
        ]

        brand2_metrics = [
            MagicMock(
                avg_rating=3.8,
                total_reviews=5000,
                revenue_estimate=Decimal("200000"),
                market_share_percent=8.0,
            )
        ]

        comparison = analyzer.compare_brands(
            [("Brand A", brand1_metrics), ("Brand B", brand2_metrics)]
        )

        assert "Brand A" in comparison
        assert "Brand B" in comparison
        assert comparison["Brand A"]["score"] > comparison["Brand B"]["score"]


class TestBrandRepository:
    """Tests for BrandRepository database operations."""

    @pytest.mark.asyncio
    async def test_get_by_name_found(self):
        """Test getting brand by name when it exists."""
        from src.db.repositories.brand_repository import BrandRepository

        mock_session = AsyncMock()
        mock_brand = MagicMock(
            id=uuid.uuid4(),
            name="Apple",
            platform="amazon_us",
            slug="apple",
        )

        # Setup mock query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_brand
        mock_session.execute.return_value = mock_result

        repo = BrandRepository(mock_session)
        result = await repo.get_by_name("Apple", "amazon_us")

        assert result is not None
        assert result.name == "Apple"

    @pytest.mark.asyncio
    async def test_get_by_name_not_found(self):
        """Test getting brand by name when it doesn't exist."""
        from src.db.repositories.brand_repository import BrandRepository

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = BrandRepository(mock_session)
        result = await repo.get_by_name("NonExistent", "amazon_us")

        assert result is None
