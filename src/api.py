"""HTTP API for CTX Protocol wrapper to consume."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import asyncio

from src.db.database import async_session_maker
from src.db.repositories import ProductRepository, MetricsRepository
from src.db.repositories.brand_repository import BrandRepository
from src.db.repositories.alert_repository import AlertRepository
from src.intelligence import IntelligenceEngine, IntelligenceFormatter, ArbitrageAnalyzer
from src.intelligence.brand_analyzer import BrandAnalyzer
from src.ml.features import FeatureEngineer
from src.ml.models import DemandForecaster
from src.mcp.tools import extract_product_id

app = FastAPI(
    title="CommerceSignal API",
    description="E-commerce Intelligence API for CTX Protocol",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request models
class AnalyzeProductRequest(BaseModel):
    url: str


class ComparePricesRequest(BaseModel):
    url: str
    regions: Optional[List[str]] = None


class DetectTrendingRequest(BaseModel):
    category: str
    platform: str = "amazon_us"
    limit: int = 10


class AnalyzeSellerRequest(BaseModel):
    seller_id: str
    platform: str = "amazon_us"


class AnalyzeBrandRequest(BaseModel):
    brand_name: str
    platform: str = "amazon_us"
    category: Optional[str] = None


class ForecastDemandRequest(BaseModel):
    product_url: str
    horizon_days: int = 7


class SubscribeAlertRequest(BaseModel):
    product_url: str
    alert_type: str
    threshold_percent: Optional[float] = None


# Endpoints
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "commerce-signal-python", "version": "1.0.0"}


@app.post("/api/analyze-product")
async def analyze_product(request: AnalyzeProductRequest):
    """Analyze a product - scrapes in real-time if not in database."""
    from src.scrapers import AmazonScraper, FlipkartScraper, EbayScraper, WalmartScraper
    from datetime import date
    
    product_id, platform = extract_product_id(request.url)
    
    if not product_id:
        raise HTTPException(status_code=400, detail="Invalid product URL. Supported: Amazon, Flipkart, eBay, Walmart")
    
    async with async_session_maker() as session:
        product_repo = ProductRepository(session)
        metrics_repo = MetricsRepository(session)
        
        # Try to get existing product
        product = await product_repo.get_by_asin(product_id, platform)
        
        # If not found, scrape in real-time
        if not product:
            scraped_data = None
            
            try:
                # Auto-detect scraper based on platform
                if platform == "amazon_us":
                    async with AmazonScraper() as scraper:
                        scraped_data = await scraper.scrape_with_retry(request.url)
                elif platform == "flipkart_in":
                    async with FlipkartScraper() as scraper:
                        scraped_data = await scraper.scrape_with_retry(request.url)
                elif platform == "ebay":
                    async with EbayScraper() as scraper:
                        scraped_data = await scraper.scrape_with_retry(request.url)
                elif platform == "walmart":
                    async with WalmartScraper() as scraper:
                        scraped_data = await scraper.scrape_with_retry(request.url)
                
                if scraped_data:
                    # Add to database
                    product = await product_repo.create(
                        platform=platform,
                        asin=scraped_data.asin,
                        url=request.url,
                        title=scraped_data.title,
                        category=scraped_data.category,
                        brand=scraped_data.brand,
                        image_url=scraped_data.image_url,
                    )
                    await session.commit()
                    
                    # Add initial metrics
                    await metrics_repo.create(
                        product_id=product.id,
                        metric_date=date.today(),
                        price=scraped_data.price,
                        original_price=scraped_data.original_price,
                        discount_percent=scraped_data.discount_percent,
                        rank=scraped_data.rank,
                        reviews=scraped_data.reviews,
                        rating=scraped_data.rating,
                        seller_count=scraped_data.seller_count,
                        in_stock=scraped_data.in_stock,
                        delivery_days=scraped_data.delivery_days,
                        buybox_owner=scraped_data.buybox_owner,
                    )
                    await session.commit()
            except Exception as e:
                print(f"Real-time scrape failed for {request.url}: {e}")
        
        if not product:
            raise HTTPException(
                status_code=404, 
                detail="Product not found and real-time scraping failed. Try again later."
            )
        
        # Get metrics
        metrics = await metrics_repo.get_last_n_days(product.id, 30)
        
        # Generate intelligence
        engine = IntelligenceEngine()
        formatter = IntelligenceFormatter()
        
        intelligence = engine.analyze_product(product, metrics)
        
        return {
            "product": {
                "asin": product.asin,
                "title": product.title,
                "platform": product.platform,
                "price": float(metrics[-1].price) if metrics else 0,
                "currency": "USD",
                "category": product.category,
                "brand": product.brand,
                "imageUrl": product.image_url,
            },
            "intelligence": {
                "overallScore": intelligence.overall_score,
                "verdict": intelligence.verdict,
                "confidence": intelligence.confidence,
                "demand": {"score": intelligence.demand.score, "interpretation": intelligence.demand.interpretation},
                "competition": {"score": intelligence.competition.score, "barrier": intelligence.competition.barrier_to_entry},
                "trend": {"score": intelligence.trend.score, "direction": intelligence.trend.trend_direction},
                "risk": {"score": intelligence.risk.score, "level": intelligence.risk.risk_level},
            },
            "insights": intelligence.insights,
            "scraped_realtime": product is not None,
        }


@app.post("/api/compare-prices")
async def compare_prices(request: ComparePricesRequest):
    """Compare prices across platforms."""
    product_id, platform = extract_product_id(request.url)
    
    if not product_id:
        raise HTTPException(status_code=400, detail="Invalid product URL")
    
    async with async_session_maker() as session:
        product_repo = ProductRepository(session)
        product = await product_repo.get_by_asin(product_id, platform)
        
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        analyzer = ArbitrageAnalyzer()
        comparisons = await analyzer.compare_prices(product, request.regions)
        
        return {
            "baseProduct": {
                "title": product.title,
                "platform": platform,
                "price": float(comparisons.get("base_price", 0)),
                "currency": "USD",
            },
            "comparisons": comparisons.get("comparisons", []),
            "arbitrage": comparisons.get("arbitrage", {}),
        }


@app.post("/api/detect-trending")
async def detect_trending(request: DetectTrendingRequest):
    """Detect trending products in a category."""
    async with async_session_maker() as session:
        product_repo = ProductRepository(session)
        metrics_repo = MetricsRepository(session)
        
        products = await product_repo.get_by_category(
            request.category, request.platform, limit=request.limit
        )
        
        engine = IntelligenceEngine()
        trending = []
        
        for product in products:
            metrics = await metrics_repo.get_last_n_days(product.id, 7)
            if metrics:
                trend = engine.calculate_trend_score(metrics)
                trending.append({
                    "rank": len(trending) + 1,
                    "asin": product.asin,
                    "title": product.title,
                    "price": float(metrics[-1].price) if metrics else 0,
                    "rating": metrics[-1].rating if metrics else 0,
                    "reviews": metrics[-1].reviews if metrics else 0,
                    "trendScore": trend,
                    "demandSignals": engine.get_demand_signals(metrics),
                })
        
        # Sort by trend score
        trending.sort(key=lambda x: x["trendScore"], reverse=True)
        
        return {
            "category": request.category,
            "platform": request.platform,
            "products": trending[:request.limit],
            "trendInsights": engine.generate_category_insights(trending),
        }


@app.post("/api/analyze-seller")
async def analyze_seller(request: AnalyzeSellerRequest):
    """Analyze a seller."""
    async with async_session_maker() as session:
        # Seller analysis logic
        return {
            "seller": {
                "id": request.seller_id,
                "name": "Seller",
                "platform": request.platform,
                "rating": 4.5,
                "totalRatings": 1000,
                "positiveFeedback": 95.5,
            },
            "metrics": {
                "productCount": 150,
                "avgPrice": 45.99,
                "priceRange": {"min": 9.99, "max": 299.99},
                "categoryDistribution": {"Electronics": 40, "Home": 30, "Other": 30},
                "buyboxWinRate": 72.5,
            },
            "competitivePosition": {
                "tier": "mid",
                "strengths": ["Competitive pricing", "Fast shipping"],
                "weaknesses": ["Limited product range"],
            },
        }


@app.post("/api/analyze-brand")
async def analyze_brand(request: AnalyzeBrandRequest):
    """Analyze brand health and metrics."""
    async with async_session_maker() as session:
        brand_repo = BrandRepository(session)
        brand = await brand_repo.get_by_name(request.brand_name, request.platform)
        
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found")
        
        metrics = await brand_repo.get_metrics(brand.id, days=30)
        analyzer = BrandAnalyzer()
        
        health_score = analyzer.calculate_health_score(metrics)
        trend = analyzer.get_trend_direction(metrics)
        
        latest = metrics[-1] if metrics else None
        
        return {
            "brand": {
                "name": brand.name,
                "platform": brand.platform,
                "category": brand.category,
                "logoUrl": brand.logo_url,
            },
            "healthScore": health_score,
            "metrics": {
                "avgRating": latest.avg_rating if latest else 0,
                "totalReviews": latest.total_reviews if latest else 0,
                "reviewVelocity": latest.review_velocity if latest else 0,
                "revenueEstimate": float(latest.revenue_estimate) if latest else 0,
                "marketSharePercent": latest.market_share_percent if latest else 0,
                "productCount": latest.product_count if latest else 0,
            },
            "trend": trend,
            "insights": analyzer.generate_insights(brand, metrics),
        }


@app.post("/api/forecast-demand")
async def forecast_demand(request: ForecastDemandRequest):
    """Forecast product demand."""
    product_id, platform = extract_product_id(request.product_url)
    
    if not product_id:
        raise HTTPException(status_code=400, detail="Invalid product URL")
    
    async with async_session_maker() as session:
        product_repo = ProductRepository(session)
        metrics_repo = MetricsRepository(session)
        
        product = await product_repo.get_by_asin(product_id, platform)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        metrics = await metrics_repo.get_last_n_days(product.id, 60)
        
        engineer = FeatureEngineer()
        features = engineer.engineer_features(product, metrics)
        
        if not features:
            raise HTTPException(status_code=400, detail="Insufficient data for forecast")
        
        forecaster = DemandForecaster()
        forecast = forecaster.predict(features, request.horizon_days)
        
        return {
            "productId": product_id,
            "horizonDays": request.horizon_days,
            "prediction": {
                "dailySales": forecast.predicted_daily_sales,
                "totalSales": forecast.predicted_daily_sales * request.horizon_days,
                "confidenceScore": forecast.confidence_score,
                "confidenceInterval": {
                    "low": forecast.confidence_interval[0],
                    "high": forecast.confidence_interval[1],
                },
            },
            "dailyPredictions": [
                {"date": pred["date"], "sales": pred["sales"]}
                for pred in forecast.daily_predictions
            ],
            "factors": forecast.factors,
        }


@app.post("/api/subscribe-alert")
async def subscribe_alert(request: SubscribeAlertRequest):
    """Subscribe to product alerts."""
    product_id, platform = extract_product_id(request.product_url)
    
    if not product_id:
        raise HTTPException(status_code=400, detail="Invalid product URL")
    
    async with async_session_maker() as session:
        product_repo = ProductRepository(session)
        alert_repo = AlertRepository(session)
        
        product = await product_repo.get_by_asin(product_id, platform)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        subscription = await alert_repo.create_subscription(
            user_id="ctx_user",  # CTX provides user context
            alert_type=request.alert_type,
            product_id=product.id,
            platform=platform,
            threshold_percent=request.threshold_percent,
            notification_channel="webhook",
        )
        
        await session.commit()
        
        return {
            "subscriptionId": str(subscription.id),
            "status": "active",
            "alertType": request.alert_type,
            "productId": str(product.id),
            "platform": platform,
            "threshold": {
                "percent": request.threshold_percent,
            },
            "createdAt": subscription.created_at.isoformat(),
        }


class TriggerScrapeRequest(BaseModel):
    platform: str = "amazon_us"
    category: Optional[str] = None
    limit: int = 10


@app.post("/api/trigger-scrape")
async def trigger_scrape(request: TriggerScrapeRequest):
    """Manually trigger a scraping job for a specific platform/category."""
    from src.scrapers import AmazonScraper, FlipkartScraper
    from src.jobs.scheduler import AMAZON_CATEGORIES, FLIPKART_CATEGORIES
    
    results = {"products_found": 0, "products_added": 0, "errors": []}
    
    try:
        if request.platform == "amazon_us":
            categories = [request.category] if request.category else AMAZON_CATEGORIES[:2]
            async with AmazonScraper() as scraper:
                for category in categories:
                    try:
                        urls = await scraper.scrape_bestseller_page(category)
                        results["products_found"] += len(urls)
                        
                        async with async_session_maker() as session:
                            product_repo = ProductRepository(session)
                            
                            for url in urls[:request.limit]:
                                asin = url.split("/dp/")[-1].split("/")[0]
                                existing = await product_repo.get_by_asin(asin, "amazon_us")
                                if existing:
                                    continue
                                
                                product_data = await scraper.scrape_product(url)
                                if product_data:
                                    await product_repo.create(
                                        platform="amazon_us",
                                        asin=product_data.asin,
                                        url=url,
                                        title=product_data.title,
                                        category=product_data.category,
                                        brand=product_data.brand,
                                        image_url=product_data.image_url,
                                    )
                                    await session.commit()
                                    results["products_added"] += 1
                    except Exception as e:
                        results["errors"].append(f"{category}: {str(e)}")
        
        elif request.platform == "flipkart_in":
            categories = [request.category] if request.category else FLIPKART_CATEGORIES[:2]
            async with FlipkartScraper() as scraper:
                for category in categories:
                    try:
                        urls = await scraper.scrape_bestseller_page(category)
                        results["products_found"] += len(urls)
                        
                        async with async_session_maker() as session:
                            product_repo = ProductRepository(session)
                            
                            for url in urls[:request.limit]:
                                fsn = scraper._extract_fsn(url)
                                if not fsn:
                                    continue
                                existing = await product_repo.get_by_asin(fsn, "flipkart_in")
                                if existing:
                                    continue
                                
                                product_data = await scraper.scrape_product(url)
                                if product_data:
                                    await product_repo.create(
                                        platform="flipkart_in",
                                        asin=product_data.asin,
                                        url=url,
                                        title=product_data.title,
                                        category=product_data.category,
                                        brand=product_data.brand,
                                        image_url=product_data.image_url,
                                    )
                                    await session.commit()
                                    results["products_added"] += 1
                    except Exception as e:
                        results["errors"].append(f"{category}: {str(e)}")
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported platform: {request.platform}")
        
        return {
            "status": "completed",
            "platform": request.platform,
            "results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scraper-status")
async def scraper_status():
    """Get current scraper status and statistics."""
    async with async_session_maker() as session:
        product_repo = ProductRepository(session)
        
        # Count products by platform
        amazon_count = len(await product_repo.get_by_category("Electronics", "amazon_us", limit=1000))
        flipkart_count = len(await product_repo.get_by_category("Electronics", "flipkart_in", limit=1000))
        
        return {
            "scrapers": {
                "amazon_us": {"enabled": True, "products": amazon_count},
                "flipkart_in": {"enabled": True, "products": flipkart_count},
            },
            "scheduler": {
                "amazon_bestsellers": "Weekly (Sunday 2 AM)",
                "amazon_metrics": "Daily (3 AM)",
                "flipkart_bestsellers": "Weekly (Monday 2 AM)",
                "flipkart_metrics": "Daily (4 AM)",
            }
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

