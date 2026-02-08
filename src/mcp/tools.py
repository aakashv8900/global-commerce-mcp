"""MCP Tool handlers for CommerceSignal."""

import re
from decimal import Decimal
from datetime import date, timedelta
import uuid

from src.db.database import async_session_maker
from src.db.repositories import ProductRepository, MetricsRepository
from src.db.models import Product, DailyMetric
from src.intelligence import IntelligenceEngine, IntelligenceFormatter, ArbitrageAnalyzer, Currency, RegionalPrice


def extract_asin_from_url(url: str) -> str | None:
    """Extract ASIN from Amazon URL."""
    patterns = [
        r"/dp/([A-Z0-9]{10})",
        r"/gp/product/([A-Z0-9]{10})",
        r"/product/([A-Z0-9]{10})",
        r"asin=([A-Z0-9]{10})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    return None


def extract_fsn_from_url(url: str) -> str | None:
    """Extract FSN (Flipkart Serial Number) from Flipkart URL."""
    patterns = [
        r"pid=([A-Z0-9]+)",
        r"/p/([a-z]+)\?",
        r"itm([A-Za-z0-9]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1).upper()

    # Try to extract from URL path
    if "/p/" in url:
        parts = url.split("/p/")
        if len(parts) > 1:
            pid_part = parts[1].split("?")[0].split("/")[0]
            if pid_part:
                return pid_part.upper()

    return None


def detect_platform(url: str) -> str:
    """Detect e-commerce platform from URL."""
    url_lower = url.lower()
    if "flipkart.com" in url_lower:
        return "flipkart_in"
    elif "amazon.com" in url_lower or "amazon.in" in url_lower:
        return "amazon_us"
    elif "walmart.com" in url_lower:
        return "walmart_us"
    elif "alibaba.com" in url_lower or "aliexpress.com" in url_lower:
        return "alibaba_cn"
    elif "ebay.com" in url_lower:
        return "ebay_us"
    elif "/products/" in url_lower and ".myshopify.com" in url_lower:
        return "shopify"
    # Check for generic Shopify stores (they have /products/ path)
    elif "/products/" in url_lower:
        return "shopify"
    return "unknown"


def extract_walmart_id(url: str) -> str | None:
    """Extract Walmart product ID from URL."""
    patterns = [
        r"/ip/[^/]+/(\d+)",
        r"/ip/(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def extract_alibaba_id(url: str) -> str | None:
    """Extract Alibaba/AliExpress product ID from URL."""
    patterns = [
        r"/item/(\d+)\.html",
        r"/product-detail/[^/]+_(\d+)\.html",
        r"productId=(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def extract_ebay_id(url: str) -> str | None:
    """Extract eBay item ID from URL."""
    patterns = [
        r"/itm/(\d+)",
        r"/itm/[^/]+/(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def extract_shopify_handle(url: str) -> str | None:
    """Extract Shopify product handle from URL."""
    match = re.search(r"/products/([^/?#]+)", url)
    if match:
        return match.group(1)
    return None


def extract_product_id(url: str) -> tuple[str | None, str]:
    """Extract product ID and platform from URL."""
    platform = detect_platform(url)
    if platform == "flipkart_in":
        return extract_fsn_from_url(url), platform
    elif platform == "amazon_us":
        return extract_asin_from_url(url), platform
    elif platform == "walmart_us":
        return extract_walmart_id(url), platform
    elif platform == "alibaba_cn":
        return extract_alibaba_id(url), platform
    elif platform == "ebay_us":
        return extract_ebay_id(url), platform
    elif platform == "shopify":
        return extract_shopify_handle(url), platform
    return None, platform



async def analyze_product_handler(arguments: dict) -> str:
    """Handle analyze_product tool call."""
    url = arguments.get("url", "")

    if not url:
        return "Error: URL is required"

    # Extract product ID and detect platform
    product_id, platform = extract_product_id(url)
    if not product_id:
        return f"Error: Could not extract product ID from URL: {url}"

    if platform == "unknown":
        return f"Error: Unsupported platform. Please use Amazon or Flipkart URLs."

    async with async_session_maker() as session:
        product_repo = ProductRepository(session)
        metrics_repo = MetricsRepository(session)

        # Try to find existing product
        product = await product_repo.get_by_asin(product_id, platform)

        if not product:
            # For demo purposes, create a mock product with generated data
            # In production, this would trigger a scrape
            return await _generate_demo_analysis(product_id, url, platform)

        # Get metrics history
        metrics = await metrics_repo.get_last_n_days(product.id, 60)

        if not metrics:
            return f"No metrics data available for product {product_id}. Data collection may still be in progress."

        # Generate intelligence
        engine = IntelligenceEngine()
        formatter = IntelligenceFormatter()

        intel = engine.analyze_product(product, metrics)
        return formatter.format_product_analysis(intel)


async def _generate_demo_analysis(product_id: str, url: str, platform: str) -> str:
    """Generate demo analysis for products not in database."""
    platform_label = "Flipkart India" if platform == "flipkart_in" else "Amazon US"
    id_label = "FSN" if platform == "flipkart_in" else "ASIN"
    
    # Platform-specific estimation notes
    if platform == "flipkart_in":
        estimation_note = "Revenue Estimation: Based on review velocity (no BSR available)"
    else:
        estimation_note = "Revenue Estimation: Monthly revenue based on BSR ranking"
    
    return f"""# Product Analysis: Demo Product ({product_id})
**{id_label}:** {product_id} | **Platform:** {platform_label.upper()}

## 📊 Executive Summary
**Overall Score:** 72/100
**Confidence:** 45%

> Note: This product is not yet in our database. For full intelligence, the product needs to be tracked for at least 14 days.

## 🚀 Quick Start
To get full intelligence on this product:
1. Add it to tracking using our scraper system
2. Wait 14-30 days for data collection
3. Run analyze_product again for complete insights

## 📈 What You'll Get After Tracking
- **{estimation_note}**
- **Demand Score**: Based on review velocity and rank trends
- **Competition Analysis**: Seller count, buybox volatility
- **Trend Detection**: Growth/decline indicators
- **Risk Assessment**: Review manipulation, seller churn flags
- **Discount Prediction**: Next expected sale timing

---
*{id_label}: {product_id} | URL: {url}*
*Add to tracking to enable full analysis*"""


async def compare_global_prices_handler(arguments: dict) -> str:
    """Handle compare_global_prices tool call."""
    url = arguments.get("url", "")

    if not url:
        return "Error: URL is required"

    # Extract product ID and platform
    product_id, platform = extract_product_id(url)
    if not product_id:
        return f"Error: Could not extract product ID from URL: {url}"

    async with async_session_maker() as session:
        product_repo = ProductRepository(session)
        metrics_repo = MetricsRepository(session)

        # Get the source product
        source_product = await product_repo.get_by_asin(product_id, platform)
        
        if not source_product:
            return await _generate_demo_price_comparison(product_id, platform)

        # Get latest metrics for source product
        source_metrics = await metrics_repo.get_last_n_days(source_product.id, 7)
        if not source_metrics:
            return f"No pricing data available for product {product_id}."

        latest_source = max(source_metrics, key=lambda m: m.date)

        # Try to find equivalent product on the other platform
        other_platform = "flipkart_in" if platform == "amazon_us" else "amazon_us"
        
        # Search by similar title (simplified matching)
        similar_products = await product_repo.search(
            source_product.title.split()[0:3],  # First 3 words
            platform=other_platform,
            limit=5
        )

        if not similar_products:
            # Generate comparison with only source product
            return await _format_single_platform_comparison(source_product, latest_source, platform)

        # Get metrics for the best matching product
        best_match = similar_products[0]
        match_metrics = await metrics_repo.get_last_n_days(best_match.id, 7)
        
        if not match_metrics:
            return await _format_single_platform_comparison(source_product, latest_source, platform)

        latest_match = max(match_metrics, key=lambda m: m.date)

        # Perform arbitrage analysis
        analyzer = ArbitrageAnalyzer()
        formatter = IntelligenceFormatter()

        if platform == "amazon_us":
            comparison = await analyzer.compare_amazon_flipkart(
                amazon_price_usd=latest_source.price,
                flipkart_price_inr=latest_match.price,
                product_title=source_product.title,
                category=source_product.category,
            )
        else:
            comparison = await analyzer.compare_amazon_flipkart(
                amazon_price_usd=latest_match.price,
                flipkart_price_inr=latest_source.price,
                product_title=source_product.title,
                category=source_product.category,
            )

        return formatter.format_global_price_comparison(comparison)


async def _generate_demo_price_comparison(product_id: str, platform: str) -> str:
    """Generate demo price comparison."""
    platform_label = "Flipkart India" if platform == "flipkart_in" else "Amazon US"
    other_platform = "Amazon US" if platform == "flipkart_in" else "Flipkart India"
    
    return f"""# 🌍 Global Price Comparison
**Product ID:** {product_id} | **Source:** {platform_label}

## Current Status
This product is not yet tracked in our database.

## How to Enable Comparison
1. Add this product to tracking
2. Wait 7+ days for price data collection
3. Run compare_global_prices again

## What You'll Get
| Region | Platform | Price | Tax-Adjusted |
|--------|----------|-------|--------------|
| US | Amazon | $XX.XX | $XX.XX |
| India | Flipkart | ₹X,XXX | ₹X,XXX |

**Arbitrage Analysis:**
- Price spread percentage
- Shipping cost estimates
- Import duty calculations
- Net margin after all costs
- Buy/sell recommendations

---
*Add product to tracking to enable full analysis*"""


async def _format_single_platform_comparison(product, metrics, platform: str) -> str:
    """Format comparison when only one platform is available."""
    platform_label = "Flipkart India" if platform == "flipkart_in" else "Amazon US"
    other_platform = "Flipkart India" if platform == "amazon_us" else "Amazon US"
    currency = "₹" if platform == "flipkart_in" else "$"
    
    return f"""# 🌍 Global Price Comparison
**Product:** {product.title[:50]}...
**Source:** {platform_label}

## Available Pricing
| Platform | Price | In Stock |
|----------|-------|----------|
| {platform_label} | {currency}{metrics.price:,.2f} | {'✅' if metrics.in_stock else '❌'} |
| {other_platform} | Not tracked | - |

## Next Steps
To enable cross-border arbitrage analysis:
1. Find the equivalent product on {other_platform}
2. Add it to tracking with `analyze_product`
3. Run `compare_global_prices` after 7 days

---
*Partial data: Only {platform_label} pricing available*"""


async def detect_trending_products_handler(arguments: dict) -> str:
    """Handle detect_trending_products tool call."""
    category = arguments.get("category", "")
    limit = min(arguments.get("limit", 10), 25)
    platform = arguments.get("platform", "amazon_us")

    if not category:
        return "Error: Category is required"

    # Platform-specific categories
    amazon_categories = [
        "Electronics", "Home & Kitchen", "Toys & Games",
        "Sports & Outdoors", "Beauty & Personal Care",
        "Health & Household", "Clothing", "Books"
    ]
    
    flipkart_categories = [
        "Electronics", "Mobiles", "Fashion",
        "Home & Furniture", "Appliances", "Beauty",
        "Toys & Baby", "Sports", "Books", "Grocery"
    ]
    
    valid_categories = flipkart_categories if platform == "flipkart_in" else amazon_categories

    # Normalize category
    category_normalized = None
    for valid in valid_categories:
        if category.lower() in valid.lower() or valid.lower() in category.lower():
            category_normalized = valid
            break

    if not category_normalized:
        platform_label = "Flipkart India" if platform == "flipkart_in" else "Amazon US"
        return f"""Error: Unknown category "{category}" for {platform_label}

Available categories:
{chr(10).join(f'- {c}' for c in valid_categories)}

Example: detect_trending_products("Electronics", platform="{platform}")"""

    async with async_session_maker() as session:
        product_repo = ProductRepository(session)

        # Get products in category for the specified platform
        products = await product_repo.get_by_category(category_normalized, platform=platform, limit=limit * 2)

        if not products:
            return f"""# 🔥 Trending Products: {category_normalized}

No products found in this category yet.

## Getting Started
Products are added through:
1. Automatic best-seller list scraping (daily)
2. Manual product tracking requests

Once products are tracked for 14+ days, trend analysis becomes available.

---
*Category: {category_normalized} | Products tracked: 0*"""

        # Get metrics for each product and calculate trends
        metrics_repo = MetricsRepository(session)
        engine = IntelligenceEngine()
        formatter = IntelligenceFormatter()

        products_with_metrics = []
        for product in products:
            metrics = await metrics_repo.get_last_n_days(product.id, 30)
            if len(metrics) >= 7:  # Need at least a week of data
                products_with_metrics.append((product, metrics))

        if not products_with_metrics:
            return f"Not enough historical data for trend analysis in {category_normalized}. Need at least 7 days of tracking."

        trending = engine.get_trending_products(products_with_metrics, limit)
        return formatter.format_trending_products(trending, category_normalized)


async def analyze_seller_handler(arguments: dict) -> str:
    """Handle analyze_seller tool call."""
    seller_id = arguments.get("seller_id", "")
    platform = arguments.get("platform", "amazon_us")

    if not seller_id:
        return "Error: seller_id is required"

    # Seller analysis requires:
    # 1. Seller profile scraping
    # 2. Product listing aggregation
    # 3. Review pattern analysis
    
    # For MVP, return a structured placeholder
    return f"""# 👤 Seller Analysis: {seller_id}
**Platform:** {platform.upper()}

## Current Status
Seller analysis is in development.

## What Will Be Available
| Metric | Description |
|--------|-------------|
| **Competition Index** | How competitive is this seller in their categories |
| **Review Manipulation Risk** | Detection of unusual review patterns |
| **Fulfillment Pattern** | FBA vs FBM distribution |
| **Stockout Frequency** | How often products go out of stock |
| **Product Quality Score** | Based on return rates and ratings |

## Required Data
To enable seller analysis, we need:
- Seller product catalog (scraped)
- 30+ days of tracking for seller's products
- Review history analysis

## Getting Started
1. Add seller's top products to tracking
2. Wait 30 days for data collection
3. Run analyze_seller for full insights

---
*Seller ID: {seller_id} | Platform: {platform}*"""


# ============================================================================
# Phase 3: Brand Intelligence Handlers
# ============================================================================

async def analyze_brand_handler(arguments: dict) -> str:
    """Handle analyze_brand tool call."""
    brand_name = arguments.get("brand_name", "")
    platform = arguments.get("platform", "amazon_us")

    if not brand_name:
        return "Error: brand_name is required"

    # Import brand analyzer
    from src.intelligence.brand_analyzer import BrandAnalyzer
    from src.db.repositories.brand_repository import BrandRepository, BrandMetricRepository

    async with async_session_maker() as session:
        brand_repo = BrandRepository(session)
        metric_repo = BrandMetricRepository(session)

        # Try to find brand
        brand = await brand_repo.get_by_name(brand_name, platform)

        if not brand:
            # Generate demo analysis for unknown brands
            return f"""# 🏢 Brand Intelligence: {brand_name}
**Platform:** {platform.upper()}

## Brand Overview
| Metric | Value |
|--------|-------|
| **Status** | Not tracked yet |
| **Products Found** | 0 |
| **Est. Revenue** | -- |
| **Avg. Rating** | -- |

## Getting Started
To get full brand intelligence:
1. Add products from this brand using `analyze_product`
2. Wait 7-30 days for data collection
3. Run `analyze_brand` for complete insights

## What You'll Get
- 📊 **Brand Health Score** (0-100)
- 📈 **Revenue Trends** (30-day trajectory)
- 🏆 **Competitive Position** (market share, rank)
- 💡 **Actionable Insights** (strengths, weaknesses)
- 🔮 **Growth Prediction** (momentum indicators)

---
*Brand: {brand_name} | Platform: {platform}*"""

        # Get brand metrics
        _, metrics = await brand_repo.get_with_metrics(brand.id, days=30)

        # Get products for this brand
        product_repo = ProductRepository(session)
        products = await product_repo.search(brand_name, platform, limit=100)

        if not metrics:
            return f"Not enough data for {brand_name}. Need at least 7 days of tracking."

        analyzer = BrandAnalyzer()
        intelligence = analyzer.analyze_brand(brand, metrics, products, [])

        # Format output
        return f"""# 🏢 Brand Intelligence: {intelligence.name}
**Platform:** {intelligence.platform.upper()} | **Category:** {intelligence.category}

## Brand Health
**Score:** {intelligence.health.score:.0f}/100 ({intelligence.health.trend})

### Strengths
{chr(10).join(f"✅ {s}" for s in intelligence.health.strengths) or "- Analyzing..."}

### Areas for Improvement
{chr(10).join(f"⚠️ {w}" for w in intelligence.health.weaknesses) or "- None identified"}

## Portfolio Metrics
| Metric | Value |
|--------|-------|
| **Products** | {intelligence.product_count} |
| **Est. Monthly Revenue** | ${intelligence.total_revenue_estimate:,.0f} |
| **Avg. Product Price** | ${intelligence.avg_product_price:.2f} |
| **Avg. Rating** | {intelligence.avg_product_rating:.1f}⭐ |
| **Total Reviews** | {intelligence.total_reviews:,} |

## Trends (30 Days)
- **Revenue:** {intelligence.revenue_trend_30d:+.1f}%
- **Review Velocity:** {intelligence.review_velocity:.1f}/day
- **New Products:** +{intelligence.product_growth}

## Verdict
{intelligence.verdict}

## Key Insights
{chr(10).join(f"💡 {insight}" for insight in intelligence.insights)}

---
*Analysis Date: {intelligence.analysis_date}*"""


async def compare_brands_handler(arguments: dict) -> str:
    """Handle compare_brands tool call."""
    brand_names = arguments.get("brands", [])
    category = arguments.get("category", "")

    if not brand_names or len(brand_names) < 2:
        return "Error: At least 2 brand names required (brands: [\"Brand1\", \"Brand2\"])"

    # Placeholder - would fetch from DB and use BrandAnalyzer.compare_brands()
    return f"""# 🏆 Brand Comparison
**Brands:** {', '.join(brand_names)}
**Category:** {category or 'All'}

## Comparison Matrix
| Metric | {' | '.join(brand_names)} |
|--------|{'---|'.join(['---' for _ in brand_names])}---|
| **Revenue** | {'$ -- | '.join(['' for _ in brand_names])}$ -- |
| **Products** | {' | '.join(['--' for _ in brand_names])} |
| **Avg Rating** | {' | '.join(['--' for _ in brand_names])} |
| **Market Share** | {' | '.join(['--' for _ in brand_names])} |

## Analysis
To run this comparison, add products from each brand using `analyze_product`.

---
*Add products from these brands to enable comparison*"""


# ============================================================================
# Phase 4: ML Forecasting Handlers
# ============================================================================

async def forecast_demand_handler(arguments: dict) -> str:
    """Handle forecast_demand tool call."""
    url = arguments.get("url", "")
    days = arguments.get("days", 7)

    if not url:
        return "Error: URL is required"

    product_id, platform = extract_product_id(url)
    if not product_id:
        return f"Error: Could not extract product ID from URL: {url}"

    from src.ml.features import FeatureEngineer
    from src.ml.models import DemandForecaster

    async with async_session_maker() as session:
        product_repo = ProductRepository(session)
        metrics_repo = MetricsRepository(session)

        product = await product_repo.get_by_asin(product_id, platform)

        if not product:
            return f"Product not found. Add it first using analyze_product."

        metrics = await metrics_repo.get_last_n_days(product.id, 60)

        if len(metrics) < 7:
            return "Insufficient data. Need at least 7 days of metrics for forecasting."

        # Engineer features
        feature_eng = FeatureEngineer()
        features = feature_eng.engineer_features(product, metrics)

        if not features:
            return "Could not generate features. Need more historical data."

        # Run forecast
        forecaster = DemandForecaster()
        forecast = forecaster.predict(features, horizon_days=days)

        # Format output
        daily_sales_str = ", ".join(f"{s:.0f}" for s in forecast.predicted_daily_sales[:7])

        return f"""# 📈 Demand Forecast
**Product:** {product.title[:50]}...
**Horizon:** {forecast.horizon_days} days

## Prediction Summary
| Metric | Value |
|--------|-------|
| **Total Sales** | {forecast.predicted_total_sales:.0f} units |
| **Daily Average** | {forecast.predicted_total_sales / days:.1f} units |
| **Trend** | {forecast.trend.capitalize()} |
| **Peak Day** | {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][forecast.peak_day]} |
| **Confidence** | {forecast.confidence_score:.0f}% |

## Daily Breakdown (Next 7 Days)
```
Days:  1    2    3    4    5    6    7
Sales: {daily_sales_str}
```

## Insights
- 📊 **Seasonality:** {'Detected' if forecast.seasonality_detected else 'Not significant'}
- 📈 **Direction:** Demand is {forecast.trend}

---
*Forecast generated {forecast.forecast_date}*"""


async def predict_price_handler(arguments: dict) -> str:
    """Handle predict_price tool call."""
    url = arguments.get("url", "")
    days = arguments.get("days", 30)

    if not url:
        return "Error: URL is required"

    product_id, platform = extract_product_id(url)
    if not product_id:
        return f"Error: Could not extract product ID from URL: {url}"

    from src.ml.features import FeatureEngineer
    from src.ml.models import PricePredictor

    async with async_session_maker() as session:
        product_repo = ProductRepository(session)
        metrics_repo = MetricsRepository(session)

        product = await product_repo.get_by_asin(product_id, platform)

        if not product:
            return f"Product not found. Add it first using analyze_product."

        metrics = await metrics_repo.get_last_n_days(product.id, 60)

        if len(metrics) < 7:
            return "Insufficient data. Need at least 7 days of metrics."

        # Engineer features
        feature_eng = FeatureEngineer()
        features = feature_eng.engineer_features(product, metrics)

        if not features:
            return "Could not generate features."

        # Predict price
        predictor = PricePredictor()
        prediction = predictor.predict_price_trajectory(features, horizon_days=days)

        return f"""# 💰 Price Prediction
**Product:** {product.title[:50]}...
**Current Price:** ${prediction.current_price:.2f}

## Forecast ({prediction.horizon_days} Days)
| Metric | Value |
|--------|-------|
| **Expected Change** | {prediction.expected_price_change:+.1f}% |
| **Drop Probability** | {prediction.probability_price_drop * 100:.0f}% |
| **Volatility** | {prediction.price_volatility.capitalize()} |
| **Confidence** | {prediction.confidence_score:.0f}% |

## Best Time to Buy
**Window:** Days {prediction.optimal_buy_window[0] + 1} - {prediction.optimal_buy_window[1] + 1}
**Expected Price:** ${min(prediction.predicted_prices):.2f}

## Recommendation
{prediction.recommendation}

---
*Prediction generated {prediction.prediction_date}*"""


async def predict_stockout_handler(arguments: dict) -> str:
    """Handle predict_stockout tool call."""
    url = arguments.get("url", "")

    if not url:
        return "Error: URL is required"

    product_id, platform = extract_product_id(url)
    if not product_id:
        return f"Error: Could not extract product ID from URL: {url}"

    from src.ml.features import FeatureEngineer
    from src.ml.models import StockoutPredictor

    async with async_session_maker() as session:
        product_repo = ProductRepository(session)
        metrics_repo = MetricsRepository(session)

        product = await product_repo.get_by_asin(product_id, platform)

        if not product:
            return f"Product not found. Add it first using analyze_product."

        metrics = await metrics_repo.get_last_n_days(product.id, 30)

        if len(metrics) < 7:
            return "Insufficient data. Need at least 7 days of metrics."

        # Engineer features
        feature_eng = FeatureEngineer()
        features = feature_eng.engineer_features(product, metrics)

        if not features:
            return "Could not generate features."

        # Extract history from metrics
        delivery_history = [m.delivery_days or 3 for m in metrics]
        seller_history = [m.seller_count for m in metrics]
        stock_history = [m.in_stock for m in metrics]

        # Predict stockout
        predictor = StockoutPredictor()
        prediction = predictor.predict_stockout_risk(
            features, delivery_history, seller_history, stock_history
        )

        risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
        emoji = risk_emoji.get(prediction.risk_level, "⚪")

        signals_str = chr(10).join(f"  - {s}" for s in prediction.signals) if prediction.signals else "  - No warning signals detected"

        return f"""# 📦 Stockout Risk Analysis
**Product:** {product.title[:50]}...

## Risk Assessment
| Metric | Value |
|--------|-------|
| **Risk Level** | {emoji} {prediction.risk_level.upper()} |
| **Probability** | {prediction.stockout_probability * 100:.0f}% |
| **Est. Days Until Stockout** | {prediction.estimated_days_until_stockout or 'N/A'} |

## Warning Signals
{signals_str}

## Recommendation
{prediction.recommendation}

---
*Analysis Date: {prediction.prediction_date}*"""


# ============================================================================
# Phase 5: Alert Handlers
# ============================================================================

async def subscribe_alert_handler(arguments: dict) -> str:
    """Handle subscribe_alert tool call."""
    alert_type = arguments.get("type", "")
    url = arguments.get("url", "")
    threshold = arguments.get("threshold", None)
    webhook_url = arguments.get("webhook_url", None)

    valid_types = ["price_drop", "stockout", "trend_change", "arbitrage", "rank_change"]

    if alert_type not in valid_types:
        return f"Error: Invalid alert type. Valid types: {', '.join(valid_types)}"

    if not url:
        return "Error: Product URL is required"

    product_id, platform = extract_product_id(url)
    if not product_id:
        return f"Error: Could not extract product ID from URL"

    from src.db.repositories.alert_repository import AlertRepository
    import uuid as uuid_module

    async with async_session_maker() as session:
        product_repo = ProductRepository(session)
        product = await product_repo.get_by_asin(product_id, platform)

        if not product:
            return "Product not found. Add it first using analyze_product."

        alert_repo = AlertRepository(session)

        # Create subscription
        subscription = await alert_repo.create_subscription(
            user_id="default_user",  # Would come from auth in production
            alert_type=alert_type,
            product_id=product.id,
            platform=platform,
            threshold_percent=float(threshold) if threshold else None,
            notification_channel="webhook" if webhook_url else "mcp",
            webhook_url=webhook_url,
        )

        await session.commit()

        return f"""# 🔔 Alert Subscription Created
**ID:** {subscription.id}
**Type:** {alert_type.replace('_', ' ').title()}

## Configuration
| Setting | Value |
|---------|-------|
| **Product** | {product.title[:40]}... |
| **Platform** | {platform} |
| **Threshold** | {threshold or 'Default'}% |
| **Channel** | {subscription.notification_channel.upper()} |
| **Status** | ✅ Active |

## What Happens Next
- We'll monitor this product for {alert_type.replace('_', ' ')} events
- You'll be notified via {subscription.notification_channel}
- Use `list_alerts` to view all subscriptions

---
*Subscription ID: {subscription.id}*"""


async def list_alerts_handler(arguments: dict) -> str:
    """Handle list_alerts tool call."""
    from src.db.repositories.alert_repository import AlertRepository

    async with async_session_maker() as session:
        alert_repo = AlertRepository(session)

        subscriptions = await alert_repo.get_user_subscriptions(
            user_id="default_user",
            active_only=True,
        )

        if not subscriptions:
            return """# 🔔 Your Alerts
No active alert subscriptions.

## Create an Alert
Use `subscribe_alert` with:
- `type`: price_drop, stockout, trend_change, arbitrage, rank_change
- `url`: Product URL
- `threshold`: (optional) Trigger threshold percentage

Example:
```
subscribe_alert(type="price_drop", url="https://amazon.com/dp/B0...", threshold=10)
```"""

        lines = ["# 🔔 Your Active Alerts", "", "| Type | Product | Threshold | Channel |", "|------|---------|-----------|---------|"]

        for sub in subscriptions[:20]:
            product_id = str(sub.product_id)[:8] if sub.product_id else "N/A"
            threshold = f"{sub.threshold_percent}%" if sub.threshold_percent else "Default"
            lines.append(
                f"| {sub.alert_type} | ...{product_id} | {threshold} | {sub.notification_channel} |"
            )

        lines.append("")
        lines.append(f"**Total:** {len(subscriptions)} active subscriptions")
        lines.append("")
        lines.append("Use `unsubscribe_alert(id=\"...\")` to remove an alert.")

        return "\n".join(lines)


async def unsubscribe_alert_handler(arguments: dict) -> str:
    """Handle unsubscribe_alert tool call."""
    subscription_id = arguments.get("id", "")

    if not subscription_id:
        return "Error: Subscription ID is required"

    import uuid as uuid_module
    from src.db.repositories.alert_repository import AlertRepository

    try:
        sub_uuid = uuid_module.UUID(subscription_id)
    except ValueError:
        return f"Error: Invalid subscription ID format"

    async with async_session_maker() as session:
        alert_repo = AlertRepository(session)

        success = await alert_repo.deactivate(sub_uuid)
        await session.commit()

        if success:
            return f"""# ✅ Alert Unsubscribed
**Subscription ID:** {subscription_id}

The alert has been deactivated. You will no longer receive notifications.

Use `subscribe_alert` to create a new alert subscription."""
        else:
            return f"Error: Subscription not found with ID: {subscription_id}"

