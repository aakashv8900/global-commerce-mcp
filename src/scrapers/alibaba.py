"""Alibaba/AliExpress product scraper."""

import re
import logging
from dataclasses import dataclass
from decimal import Decimal

from playwright.async_api import Page

from .base import BaseScraper, ScrapedProduct, ScrapedMetrics

logger = logging.getLogger(__name__)


@dataclass
class AlibabaProduct(ScrapedProduct):
    """Alibaba-specific product data."""
    alibaba_id: str | None = None
    min_order_qty: int = 1
    is_aliexpress: bool = False
    supplier_name: str | None = None
    supplier_location: str | None = None
    trade_assurance: bool = False


class AlibabaScraper(BaseScraper):
    """Scraper for Alibaba and AliExpress products."""

    PLATFORM = "alibaba_cn"
    ALIBABA_BASE = "https://www.alibaba.com"
    ALIEXPRESS_BASE = "https://www.aliexpress.com"

    CATEGORY_URLS = {
        "Electronics": "/category/100003109",
        "Consumer Electronics": "/category/100003109",
        "Home & Garden": "/category/100003109",
        "Apparel": "/category/100003070",
        "Beauty": "/category/100003086",
        "Toys": "/category/100003108",
        "Sports": "/category/100003098",
        "Jewelry": "/category/100003100",
    }

    def extract_product_id(self, url: str) -> str | None:
        """Extract product ID from Alibaba/AliExpress URL."""
        patterns = [
            r"/item/(\d+)\.html",           # AliExpress
            r"/product-detail/[^/]+_(\d+)\.html",  # Alibaba
            r"productId=(\d+)",             # Query param
            r"/(\d+)\.html",                # Generic
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def is_aliexpress(self, url: str) -> bool:
        """Check if URL is AliExpress or Alibaba."""
        return "aliexpress" in url.lower()

    async def scrape_product(self, url: str, page: Page) -> AlibabaProduct | None:
        """Scrape Alibaba/AliExpress product page."""
        try:
            is_aliexpress = self.is_aliexpress(url)
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            product_id = self.extract_product_id(url)

            if is_aliexpress:
                return await self._scrape_aliexpress(url, page, product_id)
            else:
                return await self._scrape_alibaba(url, page, product_id)

        except Exception as e:
            logger.error(f"Error scraping Alibaba product {url}: {e}")
            return None

    async def _scrape_aliexpress(self, url: str, page: Page, product_id: str | None) -> AlibabaProduct | None:
        """Scrape AliExpress product."""
        title = await self._safe_text(page, 'h1[data-pl="product-title"]')
        if not title:
            title = await self._safe_text(page, '.product-title-text')

        # Price
        price_text = await self._safe_text(page, '[data-pl="product-price"]')
        if not price_text:
            price_text = await self._safe_text(page, '.product-price-value')
        price = self._parse_price(price_text)

        # Rating
        rating_text = await self._safe_text(page, '.overview-rating-average')
        rating = float(rating_text) if rating_text else 0.0

        # Reviews
        reviews_text = await self._safe_text(page, '[data-pl="review-count"]')
        reviews = self._parse_int(reviews_text)

        # Orders (as proxy for demand)
        orders_text = await self._safe_text(page, '[data-pl="sold-count"]')
        orders = self._parse_int(orders_text)

        # Store name
        store_name = await self._safe_text(page, '.store-name')

        # Image
        image_url = await self._safe_attr(page, '.magnifier-image img', 'src')

        return AlibabaProduct(
            platform=self.PLATFORM,
            product_id=product_id or "",
            url=url,
            title=title or "Unknown Product",
            price=price or Decimal("0"),
            rating=rating,
            reviews=reviews + orders,  # Combine for demand signal
            brand=None,
            category="General",
            image_url=image_url,
            in_stock=True,
            seller_count=1,
            alibaba_id=product_id,
            min_order_qty=1,
            is_aliexpress=True,
            supplier_name=store_name,
        )

    async def _scrape_alibaba(self, url: str, page: Page, product_id: str | None) -> AlibabaProduct | None:
        """Scrape Alibaba B2B product."""
        title = await self._safe_text(page, '.module-pdp-title h1')
        if not title:
            title = await self._safe_text(page, '.ma-title')

        # Price range
        price_text = await self._safe_text(page, '.module-pdp-price')
        price = self._parse_price(price_text)

        # MOQ
        moq_text = await self._safe_text(page, '.module-pdp-moq')
        moq = self._parse_int(moq_text) or 1

        # Supplier
        supplier = await self._safe_text(page, '.company-name')
        location = await self._safe_text(page, '.company-location')

        # Trade assurance
        trade_assurance = await page.query_selector('.trade-assurance-icon') is not None

        # Image
        image_url = await self._safe_attr(page, '.main-image img', 'src')

        return AlibabaProduct(
            platform=self.PLATFORM,
            product_id=product_id or "",
            url=url,
            title=title or "Unknown Product",
            price=price or Decimal("0"),
            rating=0.0,  # B2B doesn't show ratings typically
            reviews=0,
            brand=None,
            category="General",
            image_url=image_url,
            in_stock=True,
            seller_count=1,
            alibaba_id=product_id,
            min_order_qty=moq,
            is_aliexpress=False,
            supplier_name=supplier,
            supplier_location=location,
            trade_assurance=trade_assurance,
        )

    async def scrape_metrics(self, url: str, page: Page) -> ScrapedMetrics | None:
        """Scrape metrics from Alibaba product."""
        product = await self.scrape_product(url, page)
        if not product:
            return None

        return ScrapedMetrics(
            price=product.price,
            original_price=None,
            discount_percent=None,
            rank=None,
            reviews=product.reviews,
            rating=product.rating,
            seller_count=1,
            in_stock=product.in_stock,
            delivery_days=14,  # Typical intl shipping
            buybox_owner=product.supplier_name,
        )

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
        """Parse price from text (handles $ and ¥)."""
        if not text:
            return None
        # Remove currency symbols and get first number
        match = re.search(r'[\$¥]?([\d,]+\.?\d*)', text.replace(',', ''))
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
