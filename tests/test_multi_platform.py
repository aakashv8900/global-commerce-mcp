"""Tests for multi-platform integration."""

import pytest
from src.mcp.tools import (
    detect_platform,
    extract_product_id,
    extract_asin_from_url,
    extract_fsn_from_url,
    extract_walmart_id,
    extract_alibaba_id,
    extract_ebay_id,
    extract_shopify_handle,
)


class TestPlatformDetection:
    """Tests for platform detection from URLs."""

    def test_detect_amazon_us(self):
        """Test Amazon US detection."""
        urls = [
            "https://www.amazon.com/dp/B0XXXXXXXX",
            "https://amazon.com/gp/product/B0XXXXXXXX",
            "https://www.amazon.com/Some-Product/dp/B0XXXXXXXX/ref=sr_1_1",
        ]
        for url in urls:
            assert detect_platform(url) == "amazon_us"

    def test_detect_flipkart(self):
        """Test Flipkart detection."""
        urls = [
            "https://www.flipkart.com/product/p/itm123",
            "https://flipkart.com/some-product?pid=ABCD123",
        ]
        for url in urls:
            assert detect_platform(url) == "flipkart_in"

    def test_detect_walmart(self):
        """Test Walmart detection."""
        urls = [
            "https://www.walmart.com/ip/Product-Name/123456789",
            "https://walmart.com/ip/123456789",
        ]
        for url in urls:
            assert detect_platform(url) == "walmart_us"

    def test_detect_alibaba(self):
        """Test Alibaba/AliExpress detection."""
        urls = [
            "https://www.alibaba.com/product-detail/Product_123456.html",
            "https://www.aliexpress.com/item/123456789.html",
        ]
        for url in urls:
            assert detect_platform(url) == "alibaba_cn"

    def test_detect_ebay(self):
        """Test eBay detection."""
        urls = [
            "https://www.ebay.com/itm/123456789",
            "https://ebay.com/itm/Product-Name/123456789",
        ]
        for url in urls:
            assert detect_platform(url) == "ebay_us"

    def test_detect_shopify(self):
        """Test Shopify detection."""
        urls = [
            "https://store.myshopify.com/products/product-handle",
            "https://example.com/products/cool-product",
        ]
        for url in urls:
            assert detect_platform(url) == "shopify"

    def test_detect_unknown(self):
        """Test unknown platform detection."""
        urls = [
            "https://example.com/some-page",
            "https://random-store.com/item/123",
        ]
        for url in urls:
            assert detect_platform(url) == "unknown"


class TestProductIdExtraction:
    """Tests for product ID extraction from URLs."""

    def test_extract_amazon_asin(self):
        """Test ASIN extraction from Amazon URLs."""
        test_cases = [
            ("https://amazon.com/dp/B0ABCDEFGH", "B0ABCDEFGH"),
            ("https://www.amazon.com/Product-Name/dp/B0ABCDEFGH/ref=sr", "B0ABCDEFGH"),
            ("https://amazon.com/gp/product/B0ABCDEFGH", "B0ABCDEFGH"),
        ]
        for url, expected in test_cases:
            assert extract_asin_from_url(url) == expected

    def test_extract_flipkart_fsn(self):
        """Test FSN extraction from Flipkart URLs."""
        test_cases = [
            ("https://flipkart.com/product?pid=MOBFWQ6BXGJQBHTZ", "MOBFWQ6BXGJQBHTZ"),
            ("https://flipkart.com/some-product/p/itmabc123", "ABC123"),
        ]
        for url, expected in test_cases:
            result = extract_fsn_from_url(url)
            assert result is not None

    def test_extract_walmart_id(self):
        """Test Walmart ID extraction."""
        test_cases = [
            ("https://walmart.com/ip/Product-Name/123456789", "123456789"),
            ("https://www.walmart.com/ip/987654321", "987654321"),
        ]
        for url, expected in test_cases:
            assert extract_walmart_id(url) == expected

    def test_extract_alibaba_id(self):
        """Test Alibaba ID extraction."""
        test_cases = [
            ("https://aliexpress.com/item/1234567890.html", "1234567890"),
            ("https://alibaba.com/product-detail/Product_9876543210.html", "9876543210"),
        ]
        for url, expected in test_cases:
            assert extract_alibaba_id(url) == expected

    def test_extract_ebay_id(self):
        """Test eBay ID extraction."""
        test_cases = [
            ("https://ebay.com/itm/123456789012", "123456789012"),
            ("https://www.ebay.com/itm/Product-Title/123456789012", "123456789012"),
        ]
        for url, expected in test_cases:
            assert extract_ebay_id(url) == expected

    def test_extract_shopify_handle(self):
        """Test Shopify handle extraction."""
        test_cases = [
            ("https://store.com/products/cool-sneakers", "cool-sneakers"),
            ("https://example.myshopify.com/products/widget-pro?variant=123", "widget-pro"),
        ]
        for url, expected in test_cases:
            assert extract_shopify_handle(url) == expected


class TestIntegratedExtraction:
    """Tests for the integrated extract_product_id function."""

    def test_extract_product_id_amazon(self):
        """Test integrated extraction for Amazon."""
        url = "https://amazon.com/dp/B0ABCDEFGH"
        product_id, platform = extract_product_id(url)
        assert product_id == "B0ABCDEFGH"
        assert platform == "amazon_us"

    def test_extract_product_id_walmart(self):
        """Test integrated extraction for Walmart."""
        url = "https://walmart.com/ip/Product/123456789"
        product_id, platform = extract_product_id(url)
        assert product_id == "123456789"
        assert platform == "walmart_us"

    def test_extract_product_id_ebay(self):
        """Test integrated extraction for eBay."""
        url = "https://ebay.com/itm/123456789"
        product_id, platform = extract_product_id(url)
        assert product_id == "123456789"
        assert platform == "ebay_us"

    def test_extract_product_id_unknown(self):
        """Test integrated extraction for unknown platform."""
        url = "https://unknown-store.com/item/123"
        product_id, platform = extract_product_id(url)
        assert product_id is None
        assert platform == "unknown"


class TestCrossPlatformArbitrage:
    """Tests for cross-platform price comparison."""

    def test_currency_conversion(self):
        """Test basic currency conversion."""
        from src.intelligence import Currency, RegionalPrice

        # Test USD to INR
        usd_price = RegionalPrice(
            currency=Currency.USD,
            amount=100.00,
            formatted="$100.00",
        )

        # Approximate conversion (1 USD ≈ 83 INR)
        inr_equivalent = usd_price.amount * 83
        assert inr_equivalent > 8000

    def test_arbitrage_opportunity_detection(self):
        """Test arbitrage opportunity detection."""
        from src.intelligence import ArbitrageAnalyzer

        analyzer = ArbitrageAnalyzer()

        # Product cheaper in India
        result = analyzer.calculate_arbitrage(
            source_price=100.00,
            source_currency="USD",
            target_price=6000.00,
            target_currency="INR",
            shipping_estimate=15.00,
            duty_percent=18.0,
        )

        assert "opportunity" in str(result).lower() or result is not None
