# CommerceSignal MCP

**AI-native e-commerce intelligence engine** that converts raw marketplace signals into revenue estimates, demand forecasting, competition analysis, and actionable product insights.

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

## 🎯 What is CommerceSignal?

CommerceSignal is an MCP (Model Context Protocol) server that provides decision-grade intelligence about e-commerce products. Instead of returning raw data, it delivers:

- **Revenue Estimation** - Monthly/daily sales estimates based on BSR ranking
- **Demand Scoring** - 0-100 score based on review velocity, rank trends, stockouts
- **Competition Analysis** - Seller count, buybox volatility, barrier to entry
- **Trend Detection** - Accelerating/declining momentum indicators
- **Risk Assessment** - Review manipulation flags, seller churn, quality signals
- **Discount Prediction** - Next expected sale timing

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 6+ (optional, for caching)

### Installation

```bash
# Clone the repository
cd global-commerce-mcp

# Install dependencies
pip install -e ".[dev]"

# Install Playwright browsers
playwright install chromium

# Copy environment template
cp .env.example .env
# Edit .env with your database credentials

# Initialize the database
python -c "from src.db.database import init_db; import asyncio; asyncio.run(init_db())"
```

### Running the MCP Server

```bash
# Run as MCP server (stdio transport)
python -m src.main
```

### Using with Claude Desktop

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "commerce-signal": {
      "command": "python",
      "args": ["-m", "src.main"],
      "cwd": "/path/to/global-commerce-mcp"
    }
  }
}
```

## 📊 MCP Tools

### 1. `analyze_product(url)`

Analyze a product from any supported platform:
- **Amazon US** - Full intelligence with BSR revenue estimation
- **Flipkart India** - Review-velocity based analytics
- **Walmart US** - Price and fulfillment tracking
- **Alibaba/AliExpress** - B2B and B2C sourcing data
- **eBay US** - Auction and fixed-price analysis  
- **Shopify** - Generic store product tracking

```
# Amazon US
analyze_product("https://amazon.com/dp/B0XXXXXXXX")

# Flipkart India
analyze_product("https://flipkart.com/product/p/xyz?pid=MOBF123")

# Walmart US
analyze_product("https://walmart.com/ip/Product/123456789")

# eBay US
analyze_product("https://ebay.com/itm/123456789")

# Shopify Store
analyze_product("https://store.com/products/product-handle")
```


**Returns:**
- Estimated monthly revenue (review-velocity based for Flipkart)
- Demand score (0-100)
- Competition score (0-100)
- Trend score (-100 to +100)
- Risk score with flags
- Discount cycle prediction
- 5 actionable insights

### 2. `detect_trending_products(category, platform?)`

Find trending products in a category.

```
# Amazon US (default)
detect_trending_products("Electronics")

# Flipkart India
detect_trending_products("Mobiles", platform="flipkart_in")
```

**Amazon Categories:** Electronics, Home & Kitchen, Toys & Games, Sports & Outdoors, Beauty & Personal Care, Health & Household, Clothing, Books

**Flipkart Categories:** Electronics, Mobiles, Fashion, Home & Furniture, Appliances, Beauty, Toys & Baby, Sports, Books, Grocery

### 3. `compare_global_prices(url)`

Compare prices between Amazon US and Flipkart India with full arbitrage analysis.

```
compare_global_prices("https://amazon.com/dp/B0XXXXXXXX")
```

**Returns:**
- Regional prices in local currency and USD
- Price spread percentage
- Arbitrage opportunities with shipping/duty estimates
- Net margin calculations
- Buy/sell recommendations

### 4. `analyze_seller(seller_id, platform?)`

Analyze a seller profile.

```
analyze_seller("A1BCDEF2345", platform="amazon_us")
```

### 5. `analyze_brand(brand_name, platform?)` ✨ NEW

Get brand-level intelligence including health score and portfolio metrics.

```
analyze_brand("Apple", platform="amazon_us")
```

### 6. `compare_brands(brands, category?)` ✨ NEW

Compare multiple brands side-by-side.

```
compare_brands(brands=["Apple", "Samsung", "Google"])
```

### 7. `forecast_demand(url, days?)` ✨ NEW

ML-powered demand forecasting for products.

```
forecast_demand("https://amazon.com/dp/B0XXXXXXXX", days=7)
```

**Returns:** Predicted daily sales, trend direction, peak days, seasonality detection.

### 8. `predict_price(url, days?)` ✨ NEW

Predict future price trajectory and optimal buy windows.

```
predict_price("https://amazon.com/dp/B0XXXXXXXX", days=30)
```

**Returns:** Expected price change, drop probability, volatility, buy recommendations.

### 9. `predict_stockout(url)` ✨ NEW

Assess stockout risk and supply constraints.

```
predict_stockout("https://flipkart.com/product/...")
```

**Returns:** Risk level, probability, warning signals, recommendations.

### 10. `subscribe_alert(type, url, threshold?, webhook_url?)` ✨ NEW

Subscribe to product alerts.

```
subscribe_alert(type="price_drop", url="https://amazon.com/dp/B0...", threshold=10)
```

**Alert Types:** price_drop, stockout, trend_change, arbitrage, rank_change

### 11. `list_alerts()` ✨ NEW

View all active alert subscriptions.

### 12. `unsubscribe_alert(id)` ✨ NEW

Remove an alert subscription.

## 🧮 Signal Formulas

### Demand Score
```
demand_score = (
    review_velocity * 0.4 +
    rank_improvement * 0.3 +
    stockout_frequency * 0.2 +
    price_increase * 0.1
)
```

### Competition Score
```
competition_score = (
    seller_count * 0.4 +
    review_concentration * 0.3 +
    buybox_volatility * 0.3
)
```

### Revenue Estimation
```
daily_sales = a * (rank ^ -b)  # Power law model
monthly_revenue = daily_sales * price * 30
```

## 🗂 Project Structure

```
global-commerce-mcp/
├── src/
│   ├── config/          # Settings and configuration
│   ├── db/              # Database models and repositories
│   ├── scrapers/        # Playwright-based scrapers
│   ├── signals/         # Intelligence calculation modules
│   ├── intelligence/    # Main engine and formatting
│   ├── ml/              # ML models and inference ✨ NEW
│   ├── alerts/          # Alert engine and channels ✨ NEW
│   ├── mcp/             # MCP server and tools
│   ├── jobs/            # Background job scheduler
│   └── main.py          # Entry point
├── tests/               # Test suite
├── requirements.txt     # Python dependencies
├── pyproject.toml       # Project configuration
└── .env.example         # Environment template
```

## 🔧 Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Format code
black src tests
ruff check src tests --fix
```

## 📈 Roadmap

- [x] **Phase 1**: Amazon US product intelligence
- [x] **Phase 2**: Flipkart India + cross-border arbitrage
- [x] **Phase 3**: Brand-level intelligence
- [x] **Phase 4**: Predictive forecasting with ML (LightGBM)
- [x] **Phase 5**: Alerts & subscriptions

## 📝 License

MIT License - see LICENSE file for details.

---

**CommerceSignal** - Decision-grade e-commerce intelligence at your fingertips.
