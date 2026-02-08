"""Generic Shopify store scraper."""

import re
import logging
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlparse

from playwright.async_api import Page

from .base import BaseScraper, ScrapedProduct, ScrapedMetrics

logger = logging.getLogger(__name__)


@dataclass
class ShopifyProduct(ScrapedProduct):
    """Shopify-specific product data."""
    shopify_id: str | None = None
    variant_id: str | None = None
    store_domain: str | None = None
    vendor: str | None = None
    product_type: str | None = None
    tags: list[str] | None = None
    compare_at_price: Decimal | None = None


class ShopifyScraper(BaseScraper):
    """
    Generic scraper for Shopify stores.
    
    Works with any Shopify-powered store by leveraging
    the standard Shopify product JSON API.
    """

    PLATFORM = "shopify"

    def extract_product_id(self, url: str) -> str | None:
        """Extract Shopify product handle from URL."""
        patterns = [
            r"/products/([^/?#]+)",           # /products/product-handle
            r"variant=(\d+)",                  # Variant ID
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def get_store_domain(self, url: str) -> str:
        """Extract store domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc

    async def scrape_product(self, url: str, page: Page) -> ShopifyProduct | None:
        """Scrape Shopify product page."""
        try:
            # Try JSON API first (faster and more reliable)
            json_product = await self._fetch_product_json(url, page)
            if json_product:
                return json_product

            # Fallback to HTML scraping
            return await self._scrape_html(url, page)

        except Exception as e:
            logger.error(f"Error scraping Shopify product {url}: {e}")
            return None

    async def _fetch_product_json(self, url: str, page: Page) -> ShopifyProduct | None:
        """Fetch product data from Shopify JSON API."""
        try:
            # Convert product URL to JSON endpoint
            parsed = urlparse(url)
            path = parsed.path
            if '/products/' in path:
                handle = path.split('/products/')[-1].split('?')[0].split('/')[0]
                json_url = f"{parsed.scheme}://{parsed.netloc}/products/{handle}.json"
                
                await page.goto(json_url, wait_until="domcontentloaded", timeout=15000)
                content = await page.content()
                
                # Check if we got JSON
                if '"product"' in content:
                    import json
                    # Extract JSON from page
                    text = await page.inner_text('body')
                    data = json.loads(text)
                    product_data = data.get('product', {})
                    
                    # Get first variant for pricing
                    variants = product_data.get('variants', [])
                    first_variant = variants[0] if variants else {}
                    
                    price = Decimal(str(first_variant.get('price', '0')))
                    compare_price = first_variant.get('compare_at_price')
                    if compare_price:
                        compare_price = Decimal(str(compare_price))
                    
                    # Check stock
                    in_stock = first_variant.get('available', True)
                    
                    return ShopifyProduct(
                        platform=self.PLATFORM,
                        product_id=str(product_data.get('id', handle)),
                        url=url,
                        title=product_data.get('title', 'Unknown'),
                        price=price,
                        rating=0.0,  # Shopify doesn't have native ratings
                        reviews=0,
                        brand=product_data.get('vendor'),
                        category=product_data.get('product_type', 'General'),
                        image_url=product_data.get('images', [{}])[0].get('src') if product_data.get('images') else None,
                        in_stock=in_stock,
                        seller_count=1,
                        shopify_id=str(product_data.get('id')),
                        variant_id=str(first_variant.get('id')),
                        store_domain=parsed.netloc,
                        vendor=product_data.get('vendor'),
                        product_type=product_data.get('product_type'),
                        tags=product_data.get('tags', '').split(', ') if product_data.get('tags') else None,
                        compare_at_price=compare_price,
                    )
        except Exception as e:
            logger.debug(f"JSON API failed, falling back to HTML: {e}")
        
        return None

    async def _scrape_html(self, url: str, page: Page) -> ShopifyProduct | None:
        """Fallback HTML scraping for Shopify stores."""
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        store_domain = self.get_store_domain(url)
        product_id = self.extract_product_id(url)

        # Title - common Shopify selectors
        title = await self._safe_text(page, '.product-title')
        if not title:
            title = await self._safe_text(page, 'h1.product__title')
        if not title:
            title = await self._safe_text(page, '[data-product-title]')
        if not title:
            title = await self._safe_text(page, 'h1')

        # Price
        price_text = await self._safe_text(page, '.product-price')
        if not price_text:
            price_text = await self._safe_text(page, '.price__regular .price-item')
        if not price_text:
            price_text = await self._safe_text(page, '[data-product-price]')
        price = self._parse_price(price_text)

        # Compare-at price
        compare_text = await self._safe_text(page, '.price__compare .price-item')
        compare_price = self._parse_price(compare_text)

        # Brand/vendor
        vendor = await self._safe_text(page, '.product-vendor')
        if not vendor:
            vendor = await self._safe_text(page, '[data-vendor]')

        # Image
        image_url = await self._safe_attr(page, '.product-featured-image img', 'src')
        if not image_url:
            image_url = await self._safe_attr(page, '.product__media img', 'src')

        # Stock status
        in_stock = True
        oos_elem = await page.query_selector('[data-soldout]')
        if oos_elem:
            in_stock = False
        add_button = await page.query_selector('[data-add-to-cart]:not([disabled])')
        if not add_button:
            # Check if button is disabled
            disabled_button = await page.query_selector('[data-add-to-cart][disabled]')
            if disabled_button:
                in_stock = False

        return ShopifyProduct(
            platform=self.PLATFORM,
            product_id=product_id or "",
            url=url,
            title=title or "Unknown Product",
            price=price or Decimal("0"),
            rating=0.0,
            reviews=0,
            brand=vendor,
            category="General",
            image_url=image_url,
            in_stock=in_stock,
            seller_count=1,
            shopify_id=product_id,
            store_domain=store_domain,
            vendor=vendor,
            compare_at_price=compare_price,
        )

    async def scrape_metrics(self, url: str, page: Page) -> ScrapedMetrics | None:
        """Scrape metrics from Shopify product."""
        product = await self.scrape_product(url, page)
        if not product:
            return None

        discount = None
        if product.compare_at_price and product.compare_at_price > product.price:
            discount = float((product.compare_at_price - product.price) / product.compare_at_price * 100)

        return ScrapedMetrics(
            price=product.price,
            original_price=product.compare_at_price,
            discount_percent=discount,
            rank=None,
            reviews=0,
            rating=0.0,
            seller_count=1,
            in_stock=product.in_stock,
            delivery_days=5,
            buybox_owner=product.store_domain,
        )

    async def scrape_collection(self, collection_url: str, page: Page, limit: int = 50) -> list[ShopifyProduct]:
        """Scrape products from a Shopify collection page."""
        products = []
        try:
            # Try JSON first
            json_url = f"{collection_url}.json"
            await page.goto(json_url, wait_until="domcontentloaded", timeout=15000)
            content = await page.content()
            
            if '"products"' in content:
                import json
                text = await page.inner_text('body')
                data = json.loads(text)
                
                for prod in data.get('products', [])[:limit]:
                    variants = prod.get('variants', [])
                    first_variant = variants[0] if variants else {}
                    
                    products.append(ShopifyProduct(
                        platform=self.PLATFORM,
                        product_id=str(prod.get('id')),
                        url=f"{collection_url.rsplit('/collections', 1)[0]}/products/{prod.get('handle')}",
                        title=prod.get('title', 'Unknown'),
                        price=Decimal(str(first_variant.get('price', '0'))),
                        rating=0.0,
                        reviews=0,
                        brand=prod.get('vendor'),
                        category=prod.get('product_type', 'General'),
                        image_url=prod.get('images', [{}])[0].get('src') if prod.get('images') else None,
                        in_stock=first_variant.get('available', True),
                        seller_count=1,
                        shopify_id=str(prod.get('id')),
                        vendor=prod.get('vendor'),
                    ))
                    
        except Exception as e:
            logger.error(f"Error scraping Shopify collection: {e}")

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
        match = re.search(r'[\$£€]?([\d,]+\.?\d*)', text.replace(',', ''))
        if match:
            return Decimal(match.group(1))
        return None
