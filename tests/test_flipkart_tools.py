"""Tests for Flipkart integration in MCP tools."""

import pytest
from decimal import Decimal

from src.mcp.tools import (
    extract_fsn_from_url,
    detect_platform,
    extract_product_id,
)


class TestFlipkartUrlExtraction:
    """Tests for Flipkart URL extraction functions."""

    def test_extract_fsn_with_pid_parameter(self):
        """Test FSN extraction from URL with pid= parameter."""
        url = "https://www.flipkart.com/product-name/p/itm12345?pid=MOBF9GHXYZ"
        fsn = extract_fsn_from_url(url)
        assert fsn == "MOBF9GHXYZ"

    def test_extract_fsn_from_path(self):
        """Test FSN extraction from URL path."""
        url = "https://www.flipkart.com/product/p/xyz123abc"
        fsn = extract_fsn_from_url(url)
        assert fsn == "XYZ123ABC"

    def test_extract_fsn_with_itm_pattern(self):
        """Test FSN extraction from itm pattern."""
        url = "https://www.flipkart.com/product-name/itmABCD1234/p/xyz"
        fsn = extract_fsn_from_url(url)
        assert fsn == "ABCD1234"

    def test_extract_fsn_invalid_url(self):
        """Test FSN extraction returns None for invalid URL."""
        url = "https://www.flipkart.com/search?q=laptop"
        fsn = extract_fsn_from_url(url)
        assert fsn is None


class TestPlatformDetection:
    """Tests for platform detection from URLs."""

    def test_detect_flipkart_platform(self):
        """Test detection of Flipkart platform."""
        url = "https://www.flipkart.com/product/p/xyz"
        platform = detect_platform(url)
        assert platform == "flipkart_in"

    def test_detect_amazon_platform(self):
        """Test detection of Amazon platform."""
        url = "https://www.amazon.com/dp/B0ABCD1234"
        platform = detect_platform(url)
        assert platform == "amazon_us"

    def test_detect_amazon_india_platform(self):
        """Test detection of Amazon India (mapped to amazon_us for now)."""
        url = "https://www.amazon.in/dp/B0ABCD1234"
        platform = detect_platform(url)
        assert platform == "amazon_us"

    def test_detect_unknown_platform(self):
        """Test detection of unknown platform."""
        url = "https://www.ebay.com/item/12345"
        platform = detect_platform(url)
        assert platform == "unknown"


class TestExtractProductId:
    """Tests for combined product ID and platform extraction."""

    def test_extract_amazon_product_id(self):
        """Test extraction of Amazon ASIN."""
        url = "https://www.amazon.com/dp/B0ABCD1234"
        product_id, platform = extract_product_id(url)
        assert product_id == "B0ABCD1234"
        assert platform == "amazon_us"

    def test_extract_flipkart_product_id(self):
        """Test extraction of Flipkart FSN."""
        url = "https://www.flipkart.com/product/p/xyz?pid=MOBF9GHXYZ"
        product_id, platform = extract_product_id(url)
        assert product_id == "MOBF9GHXYZ"
        assert platform == "flipkart_in"

    def test_extract_unknown_platform(self):
        """Test extraction from unknown platform."""
        url = "https://www.ebay.com/item/12345"
        product_id, platform = extract_product_id(url)
        assert product_id is None
        assert platform == "unknown"


class TestFlipkartRevenueEstimation:
    """Tests for Flipkart review-based revenue estimation."""

    def test_estimate_from_reviews_insufficient_data(self):
        """Test that estimation requires minimum data points."""
        from src.signals.revenue import RevenueEstimator
        
        estimator = RevenueEstimator()
        # Short list means insufficient data
        result = estimator.estimate_from_reviews([], Decimal("999"), "Electronics")
        
        assert result.estimated_daily_sales == 0.0
        assert result.confidence == 0.2
        assert "Insufficient data" in result.methodology
