"""Comprehensive background job scheduler for all platforms."""

import asyncio
from datetime import date
from decimal import Decimal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.db.database import async_session_maker
from src.db.repositories import ProductRepository, MetricsRepository
from src.scrapers import (
    AmazonScraper, FlipkartScraper, EbayScraper, 
    WalmartScraper, AlibabaScraper, ShopifyScraper
)
from src.scrapers.proxy_manager import circuit_breaker


# ================== AMAZON CATEGORIES (50+) ==================
AMAZON_CATEGORIES = [
    # Top-level categories
    "Electronics", "Computers", "Home & Kitchen", "Garden & Outdoor",
    "Sports & Outdoors", "Toys & Games", "Books", "Fashion",
    "Beauty & Personal Care", "Health & Household", "Baby Products",
    "Automotive", "Office Products", "Pet Supplies", "Industrial",
    "Arts & Crafts", "Grocery", "Movies & TV", "Music", "Video Games",
    "Software", "Handmade", "Appliances", "Musical Instruments",
    # Sub-categories (high-volume)
    "Cell Phones", "Laptops", "Headphones", "Smart Home", "Cameras",
    "Televisions", "Kitchen Appliances", "Furniture", "Bedding",
    "Clothing", "Shoes", "Jewelry", "Watches", "Luggage",
    "Fitness Equipment", "Outdoor Recreation", "Camping", "Cycling",
    "Pet Food", "Pet Toys", "Baby Clothing", "Diapers", "Strollers",
]

# ================== FLIPKART CATEGORIES (40+) ==================
FLIPKART_CATEGORIES = [
    "Electronics", "Mobiles", "Mobile Accessories", "Laptops",
    "Televisions", "Cameras", "Audio", "Fashion - Men",
    "Fashion - Women", "Fashion - Kids", "Footwear", "Watches",
    "Jewellery", "Home & Furniture", "Kitchen", "Appliances",
    "Beauty & Personal Care", "Toys & Baby", "Sports & Fitness",
    "Books", "Stationery", "Grocery", "Automotive", "Tools",
    "Computing Accessories", "Gaming", "Software", "Tablets",
    "Smart Devices", "Air Conditioners", "Refrigerators",
    "Washing Machines", "Microwave Ovens", "Air Purifiers",
]

# ================== EBAY CATEGORIES (30+) ==================
EBAY_CATEGORIES = [
    "Electronics", "Cell Phones & Accessories", "Computers",
    "Video Games", "Cameras", "Home & Garden", "Sporting Goods",
    "Toys & Hobbies", "Fashion", "Jewelry & Watches", "Motors",
    "Collectibles", "Antiques", "Art", "Books", "Music",
    "Movies & TV", "Health & Beauty", "Business & Industrial",
    "Pet Supplies", "Baby", "Crafts", "Coins", "Stamps",
]

# ================== WALMART CATEGORIES (30+) ==================
WALMART_CATEGORIES = [
    "Electronics", "Cell Phones", "Computers", "TV & Video",
    "Smart Home", "Home", "Kitchen", "Furniture", "Patio",
    "Sports & Outdoors", "Toys", "Clothing", "Shoes", "Jewelry",
    "Beauty", "Personal Care", "Health", "Baby", "Pets",
    "Grocery", "Household", "Auto", "Office", "Party",
]


async def discover_products(platform: str, categories: list, scraper_class, limit_per_category: int = 50):
    """Discover new products from bestseller pages."""
    print(f"[{platform}] Starting product discovery...")
    
    if circuit_breaker.is_open(platform):
        print(f"[{platform}] Circuit breaker open, skipping")
        return
    
    added = 0
    failed = 0
    
    async with scraper_class() as scraper:
        for category in categories:
            try:
                print(f"[{platform}] Scanning {category}...")
                urls = await scraper.scrape_bestseller_page(category)
                print(f"[{platform}] Found {len(urls)} products in {category}")
                
                async with async_session_maker() as session:
                    product_repo = ProductRepository(session)
                    
                    for url in urls[:limit_per_category]:
                        try:
                            # Extract product ID
                            if hasattr(scraper, '_extract_asin'):
                                asin = scraper._extract_asin(url)
                            elif hasattr(scraper, '_extract_fsn'):
                                asin = scraper._extract_fsn(url)
                            else:
                                asin = url.split("/")[-1]
                            
                            if not asin:
                                continue
                            
                            # Check if exists
                            existing = await product_repo.get_by_asin(asin, platform)
                            if existing:
                                continue
                            
                            # Scrape product
                            product_data = await scraper.scrape_with_retry(url)
                            if product_data:
                                await product_repo.create(
                                    platform=platform,
                                    asin=product_data.asin,
                                    url=url,
                                    title=product_data.title,
                                    category=product_data.category,
                                    brand=product_data.brand,
                                    image_url=product_data.image_url,
                                )
                                await session.commit()
                                added += 1
                                print(f"[{platform}] Added: {product_data.asin}")
                        except Exception as e:
                            failed += 1
                            
            except Exception as e:
                print(f"[{platform}] Error in {category}: {e}")
                failed += 1
    
    print(f"[{platform}] Discovery complete: {added} added, {failed} failed")


async def collect_metrics(platform: str, scraper_class):
    """Collect daily metrics for all tracked products."""
    print(f"[{platform}] Starting metrics collection...")
    
    if circuit_breaker.is_open(platform):
        print(f"[{platform}] Circuit breaker open, skipping")
        return
    
    collected = 0
    failed = 0
    
    async with async_session_maker() as session:
        product_repo = ProductRepository(session)
        metrics_repo = MetricsRepository(session)
        
        # Get all products for this platform
        products = await product_repo.get_all_by_platform(platform, limit=1000)
        print(f"[{platform}] Collecting metrics for {len(products)} products")
        
        async with scraper_class() as scraper:
            for product in products:
                try:
                    product_data = await scraper.scrape_with_retry(product.url)
                    
                    if product_data:
                        await metrics_repo.create(
                            product_id=product.id,
                            metric_date=date.today(),
                            price=product_data.price,
                            original_price=product_data.original_price,
                            discount_percent=product_data.discount_percent,
                            rank=product_data.rank,
                            reviews=product_data.reviews,
                            rating=product_data.rating,
                            seller_count=product_data.seller_count,
                            in_stock=product_data.in_stock,
                            delivery_days=product_data.delivery_days,
                            buybox_owner=product_data.buybox_owner,
                        )
                        await session.commit()
                        collected += 1
                except Exception as e:
                    failed += 1
    
    print(f"[{platform}] Metrics complete: {collected} collected, {failed} failed")


# ================== SCHEDULED JOB FUNCTIONS ==================

async def job_amazon_discover():
    """Discover new Amazon products."""
    await discover_products("amazon_us", AMAZON_CATEGORIES, AmazonScraper, limit_per_category=30)


async def job_amazon_metrics():
    """Collect Amazon metrics."""
    await collect_metrics("amazon_us", AmazonScraper)


async def job_flipkart_discover():
    """Discover new Flipkart products."""
    await discover_products("flipkart_in", FLIPKART_CATEGORIES, FlipkartScraper, limit_per_category=30)


async def job_flipkart_metrics():
    """Collect Flipkart metrics."""
    await collect_metrics("flipkart_in", FlipkartScraper)


async def job_ebay_discover():
    """Discover new eBay products."""
    await discover_products("ebay", EBAY_CATEGORIES, EbayScraper, limit_per_category=20)


async def job_ebay_metrics():
    """Collect eBay metrics."""
    await collect_metrics("ebay", EbayScraper)


async def job_walmart_discover():
    """Discover new Walmart products."""
    await discover_products("walmart", WALMART_CATEGORIES, WalmartScraper, limit_per_category=20)


async def job_walmart_metrics():
    """Collect Walmart metrics."""
    await collect_metrics("walmart", WalmartScraper)


def create_scheduler() -> AsyncIOScheduler:
    """Create comprehensive job scheduler."""
    scheduler = AsyncIOScheduler()
    
    # ========== AMAZON US ==========
    # Discovery: Every 6 hours
    scheduler.add_job(
        job_amazon_discover,
        IntervalTrigger(hours=6),
        id="amazon_discover",
        name="Amazon Product Discovery",
        replace_existing=True,
    )
    # Metrics: Daily at 3 AM UTC
    scheduler.add_job(
        job_amazon_metrics,
        CronTrigger(hour=3, minute=0),
        id="amazon_metrics",
        name="Amazon Daily Metrics",
        replace_existing=True,
    )
    
    # ========== FLIPKART INDIA ==========
    # Discovery: Every 6 hours (offset by 1 hour)
    scheduler.add_job(
        job_flipkart_discover,
        IntervalTrigger(hours=6, start_date="2024-01-01 01:00:00"),
        id="flipkart_discover",
        name="Flipkart Product Discovery",
        replace_existing=True,
    )
    # Metrics: Daily at 4 AM UTC
    scheduler.add_job(
        job_flipkart_metrics,
        CronTrigger(hour=4, minute=0),
        id="flipkart_metrics",
        name="Flipkart Daily Metrics",
        replace_existing=True,
    )
    
    # ========== EBAY ==========
    # Discovery: Every 12 hours
    scheduler.add_job(
        job_ebay_discover,
        IntervalTrigger(hours=12),
        id="ebay_discover",
        name="eBay Product Discovery",
        replace_existing=True,
    )
    # Metrics: Daily at 5 AM UTC
    scheduler.add_job(
        job_ebay_metrics,
        CronTrigger(hour=5, minute=0),
        id="ebay_metrics",
        name="eBay Daily Metrics",
        replace_existing=True,
    )
    
    # ========== WALMART ==========
    # Discovery: Every 12 hours
    scheduler.add_job(
        job_walmart_discover,
        IntervalTrigger(hours=12, start_date="2024-01-01 06:00:00"),
        id="walmart_discover",
        name="Walmart Product Discovery",
        replace_existing=True,
    )
    # Metrics: Daily at 6 AM UTC
    scheduler.add_job(
        job_walmart_metrics,
        CronTrigger(hour=6, minute=0),
        id="walmart_metrics",
        name="Walmart Daily Metrics",
        replace_existing=True,
    )
    
    print("Scheduler configured with:")
    print("  - Amazon: 6h discovery + daily metrics")
    print("  - Flipkart: 6h discovery + daily metrics")
    print("  - eBay: 12h discovery + daily metrics")
    print("  - Walmart: 12h discovery + daily metrics")
    
    return scheduler


async def run_full_discovery():
    """Run discovery for all platforms (manual trigger)."""
    print("Running full discovery for all platforms...")
    await job_amazon_discover()
    await job_flipkart_discover()
    await job_ebay_discover()
    await job_walmart_discover()
    print("Full discovery complete!")


async def run_full_metrics():
    """Run metrics collection for all platforms (manual trigger)."""
    print("Running full metrics collection...")
    await job_amazon_metrics()
    await job_flipkart_metrics()
    await job_ebay_metrics()
    await job_walmart_metrics()
    print("Full metrics collection complete!")


if __name__ == "__main__":
    # Run manual discovery for testing
    asyncio.run(run_full_discovery())
