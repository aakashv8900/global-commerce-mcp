"""Amazon US product scraper."""

import re
from decimal import Decimal, InvalidOperation

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from .base import BaseScraper, ScrapedProduct


class AmazonScraper(BaseScraper):
    """Scraper for Amazon US product pages."""

    BASE_URL = "https://www.amazon.com"

    # Selectors for product page
    SELECTORS = {
        "title": "#productTitle",
        "price": "span.a-price span.a-offscreen",
        "original_price": "span.a-price.a-text-price span.a-offscreen",
        "rating": "#acrPopover span.a-size-base",
        "reviews": "#acrCustomerReviewText",
        "rank": "#productDetails_detailBullets_sections1 tr:has(th:text('Best Sellers Rank')) td",
        "rank_alt": "#detailBullets_feature_div li:has(span:text('Best Sellers Rank'))",
        "category": "#wayfinding-breadcrumbs_feature_div ul li:last-child a",
        "brand": "#bylineInfo",
        "image": "#landingImage",
        "availability": "#availability span",
        "seller_count": "#olp-upd-new a",
        "buybox_seller": "#sellerProfileTriggerId",
        "delivery": "#delivery-message",
    }

    async def scrape_product(self, url: str) -> ScrapedProduct | None:
        """Scrape an Amazon product page."""
        page = await self._get_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self._random_delay()

            # Check for CAPTCHA or blocking
            if await self._is_blocked(page):
                print(f"Blocked on {url}")
                return None

            # Extract data
            asin = self._extract_asin(url)
            if not asin:
                return None

            title = await self._get_text(page, self.SELECTORS["title"])
            if not title:
                print(f"Could not find title for {url}")
                return None

            price = await self._get_price(page, self.SELECTORS["price"])
            original_price = await self._get_price(page, self.SELECTORS["original_price"])

            # Calculate discount
            discount_percent = None
            if original_price and price and original_price > price:
                discount_percent = float((original_price - price) / original_price * 100)

            rating = await self._get_rating(page)
            reviews = await self._get_reviews(page)
            rank = await self._get_rank(page)
            category = await self._get_text(page, self.SELECTORS["category"]) or "Unknown"
            brand = await self._get_brand(page)
            image_url = await self._get_attribute(page, self.SELECTORS["image"], "src")
            in_stock = await self._check_availability(page)
            seller_count = await self._get_seller_count(page)
            buybox_owner = await self._get_text(page, self.SELECTORS["buybox_seller"])
            delivery_days = await self._get_delivery_days(page)

            return ScrapedProduct(
                asin=asin,
                title=title.strip(),
                price=price or Decimal("0"),
                original_price=original_price,
                discount_percent=discount_percent,
                rank=rank,
                category=category.strip(),
                reviews=reviews,
                rating=rating,
                seller_count=seller_count,
                in_stock=in_stock,
                image_url=image_url,
                brand=brand,
                delivery_days=delivery_days,
                buybox_owner=buybox_owner,
            )

        except PlaywrightTimeout:
            print(f"Timeout scraping {url}")
            return None
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None
        finally:
            await page.context.close()

    async def scrape_category_page(self, category: str, page_num: int = 1) -> list[str]:
        """Scrape product URLs from a category search page."""
        page = await self._get_page()
        urls = []

        try:
            search_url = f"{self.BASE_URL}/s?k={category}&page={page_num}"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await self._random_delay()

            if await self._is_blocked(page):
                return urls

            # Find all product links
            links = await page.query_selector_all("div[data-asin] a.a-link-normal[href*='/dp/']")

            for link in links[:50]:  # Limit to 50 per page
                href = await link.get_attribute("href")
                if href and "/dp/" in href:
                    asin = self._extract_asin(href)
                    if asin:
                        urls.append(f"{self.BASE_URL}/dp/{asin}")

            # Deduplicate
            urls = list(set(urls))

        except Exception as e:
            print(f"Error scraping category {category}: {e}")
        finally:
            await page.context.close()

        return urls

    async def scrape_bestseller_page(self, category: str) -> list[str]:
        """Scrape product URLs from bestseller page."""
        page = await self._get_page()
        urls = []

        # Category to bestseller URL mapping
        category_urls = {
            "Electronics": "/gp/bestsellers/electronics",
            "Home & Kitchen": "/gp/bestsellers/home-garden",
            "Toys & Games": "/gp/bestsellers/toys-and-games",
            "Sports & Outdoors": "/gp/bestsellers/sporting-goods",
            "Beauty & Personal Care": "/gp/bestsellers/beauty",
            "Health & Household": "/gp/bestsellers/hpc",
            "Clothing": "/gp/bestsellers/fashion",
            "Books": "/gp/bestsellers/books",
        }

        bestseller_path = category_urls.get(category, "/gp/bestsellers")

        try:
            await page.goto(
                f"{self.BASE_URL}{bestseller_path}",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            await self._random_delay()

            if await self._is_blocked(page):
                return urls

            # Find product links
            links = await page.query_selector_all("a[href*='/dp/']")

            for link in links[:100]:  # Top 100 bestsellers
                href = await link.get_attribute("href")
                if href and "/dp/" in href:
                    asin = self._extract_asin(href)
                    if asin:
                        urls.append(f"{self.BASE_URL}/dp/{asin}")

            urls = list(set(urls))

        except Exception as e:
            print(f"Error scraping bestsellers {category}: {e}")
        finally:
            await page.context.close()

        return urls

    # Helper methods

    def _extract_asin(self, url_or_text: str) -> str | None:
        """Extract ASIN from URL or text."""
        patterns = [
            r"/dp/([A-Z0-9]{10})",
            r"/gp/product/([A-Z0-9]{10})",
            r"asin=([A-Z0-9]{10})",
        ]
        for pattern in patterns:
            match = re.search(pattern, url_or_text, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        return None

    async def _is_blocked(self, page: Page) -> bool:
        """Check if we hit a CAPTCHA or block page."""
        content = await page.content()
        blocked_indicators = [
            "Enter the characters you see below",
            "Sorry, we just need to make sure you're not a robot",
            "Type the characters you see in this image",
        ]
        return any(indicator in content for indicator in blocked_indicators)

    async def _get_text(self, page: Page, selector: str) -> str | None:
        """Get text content of an element."""
        try:
            element = await page.query_selector(selector)
            if element:
                return await element.text_content()
        except Exception:
            pass
        return None

    async def _get_attribute(self, page: Page, selector: str, attr: str) -> str | None:
        """Get attribute value of an element."""
        try:
            element = await page.query_selector(selector)
            if element:
                return await element.get_attribute(attr)
        except Exception:
            pass
        return None

    async def _get_price(self, page: Page, selector: str) -> Decimal | None:
        """Extract price from element."""
        text = await self._get_text(page, selector)
        if text:
            # Extract numbers from price string like "$29.99"
            match = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
            if match:
                try:
                    return Decimal(match.group())
                except InvalidOperation:
                    pass
        return None

    async def _get_rating(self, page: Page) -> float:
        """Extract product rating."""
        text = await self._get_text(page, self.SELECTORS["rating"])
        if text:
            match = re.search(r"(\d+\.?\d*)", text)
            if match:
                return float(match.group(1))
        return 0.0

    async def _get_reviews(self, page: Page) -> int:
        """Extract review count."""
        text = await self._get_text(page, self.SELECTORS["reviews"])
        if text:
            match = re.search(r"([\d,]+)", text.replace(",", ""))
            if match:
                return int(match.group(1).replace(",", ""))
        return 0

    async def _get_rank(self, page: Page) -> int | None:
        """Extract bestseller rank."""
        for selector in [self.SELECTORS["rank"], self.SELECTORS["rank_alt"]]:
            text = await self._get_text(page, selector)
            if text:
                match = re.search(r"#?([\d,]+)", text.replace(",", ""))
                if match:
                    return int(match.group(1).replace(",", ""))
        return None

    async def _get_brand(self, page: Page) -> str | None:
        """Extract brand name."""
        text = await self._get_text(page, self.SELECTORS["brand"])
        if text:
            # Clean up "Visit the X Store" or "Brand: X"
            text = re.sub(r"(Visit the|Store|Brand:)\s*", "", text)
            return text.strip()
        return None

    async def _check_availability(self, page: Page) -> bool:
        """Check if product is in stock."""
        text = await self._get_text(page, self.SELECTORS["availability"])
        if text:
            out_of_stock_phrases = ["out of stock", "unavailable", "currently unavailable"]
            return not any(phrase in text.lower() for phrase in out_of_stock_phrases)
        return True  # Assume in stock if can't determine

    async def _get_seller_count(self, page: Page) -> int:
        """Get number of sellers offering this product."""
        text = await self._get_text(page, self.SELECTORS["seller_count"])
        if text:
            match = re.search(r"(\d+)", text)
            if match:
                return int(match.group(1))
        return 1

    async def _get_delivery_days(self, page: Page) -> int | None:
        """Extract estimated delivery days."""
        text = await self._get_text(page, self.SELECTORS["delivery"])
        if text:
            # Look for patterns like "arrives Thu, Jan 25" or "tomorrow"
            if "tomorrow" in text.lower():
                return 1
            # Could enhance with date parsing
        return None
