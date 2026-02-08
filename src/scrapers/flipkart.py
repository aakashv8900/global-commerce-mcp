"""Flipkart India product scraper."""

import re
from decimal import Decimal, InvalidOperation

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from .base import BaseScraper, ScrapedProduct


class FlipkartScraper(BaseScraper):
    """Scraper for Flipkart India product pages."""

    BASE_URL = "https://www.flipkart.com"

    # Selectors for Flipkart product page
    SELECTORS = {
        "title": "span.VU-ZEz, h1._6EBuvT, span.B_NuCI",
        "price": "div.Nx9bqj.CxhGGd, div._30jeq3._16Jk6d",
        "original_price": "div.yRaY8j.A6+E6v, div._3I9_wc._2p6lqe",
        "rating": "div.XQDdHH, div._3LWZlK",
        "reviews": "span.Wphh3N span:last-child, span._2_R_DZ span",
        "category": "div._1MR4o5 a, div._3GIHBu a",
        "brand": "span.mEh187, div._2WkVRV",
        "image": "img._396cs4._2amPTt._3qGmMb, img._2r_T1I",
        "availability": "div._16FRp0, div.Z8JjpR",
        "seller": "div._1RLviB span, #sellerName span",
        "delivery": "div._3XINqE, span.U-rGRe",
        "highlights": "div._2418kt li, div.xFVion li",
        "specifications": "div._3k-BhJ",
    }

    # Category mapping for Flipkart
    CATEGORY_PATHS = {
        "Electronics": "/electronics/pr",
        "Mobiles": "/mobiles/pr",
        "Fashion": "/fashion/pr",
        "Home & Furniture": "/home-furniture/pr",
        "Appliances": "/appliances/pr",
        "Beauty": "/beauty-and-personal-care/pr",
        "Toys & Baby": "/toys-and-baby-products/pr",
        "Sports": "/sports-and-fitness/pr",
        "Books": "/books/pr",
        "Grocery": "/grocery/pr",
    }

    async def scrape_product(self, url: str) -> ScrapedProduct | None:
        """Scrape a Flipkart product page."""
        page = await self._get_page()

        try:
            # Handle Flipkart login popup
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self._close_login_popup(page)
            await self._random_delay()

            # Check for blocking
            if await self._is_blocked(page):
                print(f"Blocked on {url}")
                return None

            # Extract FSN (Flipkart Serial Number)
            fsn = self._extract_fsn(url)
            if not fsn:
                print(f"Could not extract FSN from {url}")
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
            category = await self._get_category(page)
            brand = await self._get_text(page, self.SELECTORS["brand"])
            image_url = await self._get_attribute(page, self.SELECTORS["image"], "src")
            in_stock = await self._check_availability(page)
            seller = await self._get_text(page, self.SELECTORS["seller"])
            delivery_days = await self._get_delivery_days(page)

            return ScrapedProduct(
                asin=fsn,  # Using FSN as the product ID
                title=title.strip(),
                price=price or Decimal("0"),
                original_price=original_price,
                discount_percent=discount_percent,
                rank=None,  # Flipkart doesn't show BSR like Amazon
                category=category or "Unknown",
                reviews=reviews,
                rating=rating,
                seller_count=1,  # Would need separate call to get all sellers
                in_stock=in_stock,
                image_url=image_url,
                brand=brand.strip() if brand else None,
                delivery_days=delivery_days,
                buybox_owner=seller.strip() if seller else None,
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
        """Scrape product URLs from a Flipkart category page."""
        page = await self._get_page()
        urls = []

        try:
            category_path = self.CATEGORY_PATHS.get(category, f"/search?q={category}")
            search_url = f"{self.BASE_URL}{category_path}?page={page_num}"

            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await self._close_login_popup(page)
            await self._random_delay()

            if await self._is_blocked(page):
                return urls

            # Find product links
            links = await page.query_selector_all("a._1fQZEK, a.CGtC98, a.IRpwTa, a._2UzuFa")

            for link in links[:50]:
                href = await link.get_attribute("href")
                if href:
                    full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                    if "/p/" in full_url or "pid=" in full_url:
                        urls.append(full_url)

            # Deduplicate
            urls = list(set(urls))

        except Exception as e:
            print(f"Error scraping category {category}: {e}")
        finally:
            await page.context.close()

        return urls

    async def scrape_bestseller_page(self, category: str) -> list[str]:
        """Scrape product URLs from Flipkart top selling page."""
        page = await self._get_page()
        urls = []

        try:
            # Flipkart's top selling is usually in category with sort
            category_path = self.CATEGORY_PATHS.get(category, f"/search?q={category}")
            bestseller_url = f"{self.BASE_URL}{category_path}?sort=popularity"

            await page.goto(bestseller_url, wait_until="domcontentloaded", timeout=30000)
            await self._close_login_popup(page)
            await self._random_delay()

            if await self._is_blocked(page):
                return urls

            # Find product links
            links = await page.query_selector_all("a._1fQZEK, a.CGtC98, a.IRpwTa, a._2UzuFa")

            for link in links[:100]:
                href = await link.get_attribute("href")
                if href:
                    full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                    if "/p/" in full_url or "pid=" in full_url:
                        urls.append(full_url)

            urls = list(set(urls))

        except Exception as e:
            print(f"Error scraping bestsellers {category}: {e}")
        finally:
            await page.context.close()

        return urls

    # Helper methods

    def _extract_fsn(self, url: str) -> str | None:
        """Extract FSN (product ID) from Flipkart URL."""
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

    async def _close_login_popup(self, page: Page):
        """Close the Flipkart login popup if it appears."""
        try:
            close_button = await page.query_selector("button._2KpZ6l._2doB4z")
            if close_button:
                await close_button.click()
                await page.wait_for_timeout(500)
        except Exception:
            pass

    async def _is_blocked(self, page: Page) -> bool:
        """Check if we hit a CAPTCHA or block page."""
        content = await page.content()
        blocked_indicators = [
            "Access Denied",
            "Please verify you are a human",
            "captcha",
            "robot",
        ]
        return any(indicator.lower() in content.lower() for indicator in blocked_indicators)

    async def _get_text(self, page: Page, selector: str) -> str | None:
        """Get text content of an element, trying multiple selectors."""
        selectors = selector.split(", ")
        for sel in selectors:
            try:
                element = await page.query_selector(sel.strip())
                if element:
                    text = await element.text_content()
                    if text and text.strip():
                        return text.strip()
            except Exception:
                continue
        return None

    async def _get_attribute(self, page: Page, selector: str, attr: str) -> str | None:
        """Get attribute value of an element."""
        selectors = selector.split(", ")
        for sel in selectors:
            try:
                element = await page.query_selector(sel.strip())
                if element:
                    value = await element.get_attribute(attr)
                    if value:
                        return value
            except Exception:
                continue
        return None

    async def _get_price(self, page: Page, selector: str) -> Decimal | None:
        """Extract price from element (handles ₹ symbol)."""
        text = await self._get_text(page, selector)
        if text:
            # Remove ₹ symbol and commas
            cleaned = text.replace("₹", "").replace(",", "").strip()
            match = re.search(r"[\d]+\.?\d*", cleaned)
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
            # Handle formats like "45,234 Reviews" or "1,234 Ratings & 567 Reviews"
            match = re.search(r"([\d,]+)\s*(?:Reviews|Ratings)", text, re.IGNORECASE)
            if match:
                return int(match.group(1).replace(",", ""))
            # Try just extracting first number
            match = re.search(r"([\d,]+)", text)
            if match:
                return int(match.group(1).replace(",", ""))
        return 0

    async def _get_category(self, page: Page) -> str | None:
        """Extract category from breadcrumbs."""
        try:
            breadcrumbs = await page.query_selector_all(self.SELECTORS["category"].split(", ")[0])
            if breadcrumbs and len(breadcrumbs) > 1:
                # Get second-to-last breadcrumb (more specific category)
                category = await breadcrumbs[-2].text_content()
                return category.strip() if category else None
        except Exception:
            pass
        return None

    async def _check_availability(self, page: Page) -> bool:
        """Check if product is in stock."""
        text = await self._get_text(page, self.SELECTORS["availability"])
        if text:
            out_of_stock_phrases = ["out of stock", "currently unavailable", "sold out"]
            return not any(phrase in text.lower() for phrase in out_of_stock_phrases)
        return True

    async def _get_delivery_days(self, page: Page) -> int | None:
        """Extract estimated delivery days."""
        text = await self._get_text(page, self.SELECTORS["delivery"])
        if text:
            # Look for patterns like "Delivery by Mon, Feb 10" or "2 days"
            if "tomorrow" in text.lower():
                return 1
            match = re.search(r"(\d+)\s*days?", text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None
