"""Walmart US product scraper."""

import re
import logging
from dataclasses import dataclass
from decimal import Decimal

from playwright.async_api import Page, Browser

from .base import BaseScraper, ScrapedProduct, ScrapedMetrics

logger = logging.getLogger(__name__)


@dataclass
class WalmartProduct(ScrapedProduct):
    """Walmart-specific product data."""
    walmart_id: str | None = None
    fulfillment_type: str | None = None  # "Shipped by Walmart", "Marketplace seller"
    pickup_available: bool = False
    delivery_available: bool = True


class WalmartScraper(BaseScraper):
    """Scraper for Walmart US products."""

    PLATFORM = "walmart_us"
    BASE_URL = "https://www.walmart.com"

    # Category mappings
    CATEGORY_URLS = {
        "Electronics": "/browse/electronics/3944",
        "Home": "/browse/home/4044",
        "Toys": "/browse/toys/4171",
        "Clothing": "/browse/clothing/5438",
        "Sports & Outdoors": "/browse/sports-outdoors/4125",
        "Beauty": "/browse/beauty/1085666",
        "Grocery": "/browse/food/976759",
        "Baby": "/browse/baby/5427",
        "Pets": "/browse/pets/5440",
        "Auto": "/browse/auto-tires/91083",
    }

    def extract_product_id(self, url: str) -> str | None:
        """Extract Walmart product ID from URL."""
        patterns = [
            r"/ip/[^/]+/(\d+)",           # /ip/product-name/12345
            r"/ip/(\d+)",                  # /ip/12345
            r"[?&]irgwc=(\d+)",           # Query param
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    async def scrape_product(self, url: str, page: Page) -> WalmartProduct | None:
        """Scrape Walmart product page."""
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            product_id = self.extract_product_id(url)

            # Title
            title = await self._safe_text(page, 'h1[itemprop="name"]')
            if not title:
                title = await self._safe_text(page, '[data-testid="product-title"]')

            # Price
            price_text = await self._safe_text(page, '[itemprop="price"]')
            if not price_text:
                price_text = await self._safe_text(page, '[data-testid="price-wrap"] span')
            price = self._parse_price(price_text)

            # Rating
            rating_text = await self._safe_text(page, '[itemprop="ratingValue"]')
            rating = float(rating_text) if rating_text else 0.0

            # Reviews
            reviews_text = await self._safe_text(page, '[itemprop="reviewCount"]')
            reviews = self._parse_int(reviews_text)

            # Brand
            brand = await self._safe_text(page, '[itemprop="brand"]')

            # Image
            image_url = await self._safe_attr(page, '[data-testid="hero-image"] img', 'src')

            # Category from breadcrumb
            category = await self._safe_text(page, '[data-testid="breadcrumb"] li:nth-child(2) a')

            # Stock status
            in_stock = True
            stock_elem = await page.query_selector('[data-testid="add-to-cart-btn"]')
            if not stock_elem:
                in_stock = False

            # Seller info
            seller = await self._safe_text(page, '[data-testid="sold-shipped-by"] span')
            fulfillment = "Walmart" if "Walmart" in (seller or "") else "Marketplace"

            return WalmartProduct(
                platform=self.PLATFORM,
                product_id=product_id or "",
                url=url,
                title=title or "Unknown Product",
                price=price or Decimal("0"),
                rating=rating,
                reviews=reviews,
                brand=brand,
                category=category or "General",
                image_url=image_url,
                in_stock=in_stock,
                seller_count=1,
                walmart_id=product_id,
                fulfillment_type=fulfillment,
            )

        except Exception as e:
            logger.error(f"Error scraping Walmart product {url}: {e}")
            return None

    async def scrape_metrics(self, url: str, page: Page) -> ScrapedMetrics | None:
        """Scrape current metrics for a Walmart product."""
        product = await self.scrape_product(url, page)
        if not product:
            return None

        return ScrapedMetrics(
            price=product.price,
            original_price=None,
            discount_percent=None,
            rank=None,  # Walmart doesn't expose BSR
            reviews=product.reviews,
            rating=product.rating,
            seller_count=product.seller_count,
            in_stock=product.in_stock,
            delivery_days=2,  # Walmart+ typical
            buybox_owner=product.fulfillment_type,
        )

    async def scrape_bestsellers(self, category: str, page: Page, limit: int = 50) -> list[WalmartProduct]:
        """Scrape bestsellers from category."""
        products = []
        category_url = self.CATEGORY_URLS.get(category)

        if not category_url:
            logger.warning(f"Unknown Walmart category: {category}")
            return products

        try:
            url = f"{self.BASE_URL}{category_url}?sort=best_seller"
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            # Get product links
            product_links = await page.query_selector_all('[data-testid="product-tile"] a')

            for link in product_links[:limit]:
                href = await link.get_attribute("href")
                if href and "/ip/" in href:
                    full_url = f"{self.BASE_URL}{href}" if href.startswith("/") else href
                    product = await self.scrape_product(full_url, page)
                    if product:
                        products.append(product)

        except Exception as e:
            logger.error(f"Error scraping Walmart bestsellers: {e}")

        return products

    async def _safe_text(self, page: Page, selector: str) -> str | None:
        """Safely get text from selector."""
        try:
            elem = await page.query_selector(selector)
            if elem:
                return (await elem.inner_text()).strip()
        except Exception:
            pass
        return None

    async def _safe_attr(self, page: Page, selector: str, attr: str) -> str | None:
        """Safely get attribute from selector."""
        try:
            elem = await page.query_selector(selector)
            if elem:
                return await elem.get_attribute(attr)
        except Exception:
            pass
        return None

    def _parse_price(self, text: str | None) -> Decimal | None:
        """Parse price from text."""
        if not text:
            return None
        match = re.search(r'\$?([\d,]+\.?\d*)', text.replace(',', ''))
        if match:
            return Decimal(match.group(1))
        return None

    def _parse_int(self, text: str | None) -> int:
        """Parse integer from text."""
        if not text:
            return 0
        match = re.search(r'([\d,]+)', text.replace(',', ''))
        if match:
            return int(match.group(1))
        return 0
