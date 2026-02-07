"""Background job scheduler for data collection."""

import asyncio
from datetime import date
from decimal import Decimal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.db.database import async_session_maker
from src.db.repositories import ProductRepository, MetricsRepository
from src.scrapers import AmazonScraper, FlipkartScraper

# Amazon US categories to track
AMAZON_CATEGORIES = [
    "Electronics",
    "Home & Kitchen",
    "Toys & Games",
    "Sports & Outdoors",
    "Beauty & Personal Care",
    "Health & Household",
    "Clothing",
    "Books",
]

# Flipkart India categories to track
FLIPKART_CATEGORIES = [
    "Electronics",
    "Mobiles",
    "Fashion",
    "Home & Furniture",
    "Appliances",
    "Beauty",
    "Toys & Baby",
    "Sports",
    "Books",
    "Grocery",
]

# Keep legacy alias for backward compatibility
TRACKED_CATEGORIES = AMAZON_CATEGORIES


async def refresh_bestsellers():
    """Refresh product universe from bestseller lists."""
    print("Starting bestseller refresh...")

    async with AmazonScraper() as scraper:
        for category in TRACKED_CATEGORIES:
            try:
                urls = await scraper.scrape_bestseller_page(category)
                print(f"Found {len(urls)} products in {category}")

                async with async_session_maker() as session:
                    product_repo = ProductRepository(session)

                    for url in urls[:100]:  # Limit to top 100 per category
                        asin = url.split("/dp/")[-1].split("/")[0]
                        
                        # Check if product exists
                        existing = await product_repo.get_by_asin(asin)
                        if existing:
                            continue

                        # Scrape product details
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
                            print(f"Added new product: {product_data.asin}")

            except Exception as e:
                print(f"Error refreshing {category}: {e}")

    print("Bestseller refresh complete")


async def collect_daily_metrics():
    """Collect daily metrics for all tracked products."""
    print("Starting daily metrics collection...")

    async with async_session_maker() as session:
        product_repo = ProductRepository(session)
        metrics_repo = MetricsRepository(session)

        # Get all products
        # In production, would paginate this
        for category in TRACKED_CATEGORIES:
            products = await product_repo.get_by_category(category, limit=500)
            print(f"Collecting metrics for {len(products)} products in {category}")

            async with AmazonScraper() as scraper:
                for product in products:
                    try:
                        product_data = await scraper.scrape_product(
                            f"https://www.amazon.com/dp/{product.asin}"
                        )

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

                    except Exception as e:
                        print(f"Error collecting metrics for {product.asin}: {e}")

    print("Daily metrics collection complete")


async def refresh_flipkart_bestsellers():
    """Refresh Flipkart product universe from bestseller lists."""
    print("Starting Flipkart bestseller refresh...")

    async with FlipkartScraper() as scraper:
        for category in FLIPKART_CATEGORIES:
            try:
                urls = await scraper.scrape_bestseller_page(category)
                print(f"Found {len(urls)} Flipkart products in {category}")

                async with async_session_maker() as session:
                    product_repo = ProductRepository(session)

                    for url in urls[:100]:  # Limit to top 100 per category
                        fsn = scraper._extract_fsn(url)
                        if not fsn:
                            continue
                        
                        # Check if product exists
                        existing = await product_repo.get_by_asin(fsn, platform="flipkart_in")
                        if existing:
                            continue

                        # Scrape product details
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
                            print(f"Added new Flipkart product: {product_data.asin}")

            except Exception as e:
                print(f"Error refreshing Flipkart {category}: {e}")

    print("Flipkart bestseller refresh complete")


async def collect_flipkart_metrics():
    """Collect daily metrics for all tracked Flipkart products."""
    print("Starting Flipkart metrics collection...")

    async with async_session_maker() as session:
        product_repo = ProductRepository(session)
        metrics_repo = MetricsRepository(session)

        for category in FLIPKART_CATEGORIES:
            products = await product_repo.get_by_category(
                category, platform="flipkart_in", limit=500
            )
            print(f"Collecting metrics for {len(products)} Flipkart products in {category}")

            async with FlipkartScraper() as scraper:
                for product in products:
                    try:
                        product_data = await scraper.scrape_product(product.url)

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

                    except Exception as e:
                        print(f"Error collecting Flipkart metrics for {product.asin}: {e}")

    print("Flipkart metrics collection complete")


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the job scheduler."""
    scheduler = AsyncIOScheduler()

    # === Amazon US Jobs ===
    # Refresh Amazon bestsellers weekly (Sunday at 2 AM)
    scheduler.add_job(
        refresh_bestsellers,
        CronTrigger(day_of_week="sun", hour=2, minute=0),
        id="refresh_amazon_bestsellers",
        name="Refresh Amazon Bestseller Products",
        replace_existing=True,
    )

    # Collect Amazon daily metrics (every day at 3 AM)
    scheduler.add_job(
        collect_daily_metrics,
        CronTrigger(hour=3, minute=0),
        id="collect_amazon_metrics",
        name="Collect Amazon Daily Metrics",
        replace_existing=True,
    )

    # === Flipkart India Jobs ===
    # Refresh Flipkart bestsellers weekly (Monday at 2 AM IST = ~8:30 PM UTC Sunday)
    scheduler.add_job(
        refresh_flipkart_bestsellers,
        CronTrigger(day_of_week="mon", hour=2, minute=0),
        id="refresh_flipkart_bestsellers",
        name="Refresh Flipkart Bestseller Products",
        replace_existing=True,
    )

    # Collect Flipkart daily metrics (every day at 4 AM to stagger with Amazon)
    scheduler.add_job(
        collect_flipkart_metrics,
        CronTrigger(hour=4, minute=0),
        id="collect_flipkart_metrics",
        name="Collect Flipkart Daily Metrics",
        replace_existing=True,
    )

    return scheduler


async def run_manual_refresh():
    """Run a manual refresh (for testing/initial setup)."""
    await refresh_bestsellers()
    await refresh_flipkart_bestsellers()
    await collect_daily_metrics()
    await collect_flipkart_metrics()


if __name__ == "__main__":
    # Run manual refresh for testing
    asyncio.run(run_manual_refresh())
