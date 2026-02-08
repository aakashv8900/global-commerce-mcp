"""eBay US product scraper."""

import re
import logging
from dataclasses import dataclass
from decimal import Decimal

from playwright.async_api import Page

from .base import BaseScraper, ScrapedProduct, ScrapedMetrics

logger = logging.getLogger(__name__)


@dataclass
class EbayProduct(ScrapedProduct):
    """eBay-specific product data."""
    ebay_id: str | None = None
    listing_type: str = "fixed_price"  # "auction", "fixed_price", "best_offer"
    bids: int = 0
    time_left: str | None = None
    condition: str = "new"
    seller_feedback: float = 0.0
    seller_feedback_count: int = 0


class EbayScraper(BaseScraper):
    """Scraper for eBay US products."""

    PLATFORM = "ebay_us"
    BASE_URL = "https://www.ebay.com"

    CATEGORY_URLS = {
        "Electronics": "/b/Electronics/bn_7000259124",
        "Computers": "/b/Computers-Tablets-Network-Hardware/58058",
        "Cell Phones": "/b/Cell-Phones-Smart-Watches-Accessories/15032",
        "Clothing": "/b/Clothing-Shoes-Accessories/11450",
        "Home & Garden": "/b/Home-Garden/11700",
        "Sporting Goods": "/b/Sporting-Goods/888",
        "Toys & Hobbies": "/b/Toys-Hobbies/220",
        "Collectibles": "/b/Collectibles/1",
        "Motors": "/b/eBay-Motors/6000",
        "Jewelry": "/b/Jewelry-Watches/281",
    }

    def extract_product_id(self, url: str) -> str | None:
        """Extract eBay item ID from URL."""
        patterns = [
            r"/itm/(\d+)",                    # /itm/123456
            r"/itm/[^/]+/(\d+)",              # /itm/product-name/123456
            r"item=(\d+)",                     # Query param
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    async def scrape_product(self, url: str, page: Page) -> EbayProduct | None:
        """Scrape eBay product page."""
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            product_id = self.extract_product_id(url)

            # Title
            title = await self._safe_text(page, 'h1.x-item-title__mainTitle span')
            if not title:
                title = await self._safe_text(page, '#itemTitle')

            # Price
            price_text = await self._safe_text(page, '.x-price-primary span')
            if not price_text:
                price_text = await self._safe_text(page, '#prcIsum')
            price = self._parse_price(price_text)

            # Listing type
            listing_type = "fixed_price"
            auction_elem = await page.query_selector('.x-bid-count')
            if auction_elem:
                listing_type = "auction"
                bids_text = await auction_elem.inner_text()
                bids = self._parse_int(bids_text)
            else:
                bids = 0

            best_offer = await page.query_selector('[data-testid="x-best-offer"]')
            if best_offer:
                listing_type = "best_offer"

            # Condition
            condition_text = await self._safe_text(page, '.x-item-condition-text span')
            condition = condition_text.lower() if condition_text else "used"

            # Seller info
            seller_name = await self._safe_text(page, '.x-sellercard-atf__info a span')
            feedback_text = await self._safe_text(page, '.x-sellercard-atf__data-item span')
            seller_feedback = self._parse_feedback(feedback_text)

            # Reviews/sold count
            sold_text = await self._safe_text(page, '.x-quantity__availability span')
            reviews = self._parse_int(sold_text)  # Using sold count as proxy

            # Image
            image_url = await self._safe_attr(page, '.ux-image-carousel-item img', 'src')

            # Category
            category = await self._safe_text(page, 'nav.breadcrumbs li:nth-child(2) a span')

            # Stock
            in_stock = True
            oos_elem = await page.query_selector('.d-quantity__availability--out-of-stock')
            if oos_elem:
                in_stock = False

            return EbayProduct(
                platform=self.PLATFORM,
                product_id=product_id or "",
                url=url,
                title=title or "Unknown Product",
                price=price or Decimal("0"),
                rating=0.0,  # eBay doesn't show product ratings
                reviews=reviews,
                brand=None,
                category=category or "General",
                image_url=image_url,
                in_stock=in_stock,
                seller_count=1,
                ebay_id=product_id,
                listing_type=listing_type,
                bids=bids,
                condition=condition,
                seller_feedback=seller_feedback,
            )

        except Exception as e:
            logger.error(f"Error scraping eBay product {url}: {e}")
            return None

    async def scrape_metrics(self, url: str, page: Page) -> ScrapedMetrics | None:
        """Scrape metrics from eBay product."""
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
            delivery_days=5,  # Typical eBay shipping
            buybox_owner=None,
        )

    async def search_products(self, query: str, page: Page, limit: int = 50) -> list[EbayProduct]:
        """Search for products on eBay."""
        products = []
        try:
            search_url = f"{self.BASE_URL}/sch/i.html?_nkw={query.replace(' ', '+')}&_sop=12"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            items = await page.query_selector_all('.s-item__link')
            for item in items[:limit]:
                href = await item.get_attribute('href')
                if href and '/itm/' in href:
                    product = await self.scrape_product(href, page)
                    if product:
                        products.append(product)

        except Exception as e:
            logger.error(f"Error searching eBay: {e}")

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

    def _parse_feedback(self, text: str | None) -> float:
        """Parse feedback percentage."""
        if not text:
            return 0.0
        match = re.search(r'([\d.]+)%', text)
        if match:
            return float(match.group(1))
        return 0.0
