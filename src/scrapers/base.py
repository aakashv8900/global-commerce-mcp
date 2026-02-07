"""Base scraper class with common functionality."""

import asyncio
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from playwright.async_api import async_playwright, Page, Browser

from src.config import settings


@dataclass
class ScrapedProduct:
    """Data scraped from a product page."""

    asin: str
    title: str
    price: Decimal
    original_price: Decimal | None
    discount_percent: float | None
    rank: int | None
    category: str
    reviews: int
    rating: float
    seller_count: int
    in_stock: bool
    image_url: str | None
    brand: str | None
    delivery_days: int | None
    buybox_owner: str | None


class BaseScraper(ABC):
    """Abstract base class for e-commerce scrapers."""

    def __init__(self):
        self.browser: Browser | None = None
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        ]

    async def __aenter__(self):
        """Async context manager entry."""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.browser:
            await self.browser.close()

    def _get_random_user_agent(self) -> str:
        """Get a random user agent string."""
        return random.choice(self.user_agents)

    async def _get_page(self) -> Page:
        """Create a new page with anti-detection measures."""
        if not self.browser:
            raise RuntimeError("Browser not initialized")

        context = await self.browser.new_context(
            user_agent=self._get_random_user_agent(),
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )

        page = await context.new_page()

        # Add stealth JS
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        """)

        return page

    async def _random_delay(self):
        """Add random delay between requests."""
        delay = random.uniform(
            settings.scrape_delay_min,
            settings.scrape_delay_max,
        )
        await asyncio.sleep(delay)

    @abstractmethod
    async def scrape_product(self, url: str) -> ScrapedProduct | None:
        """Scrape a product page. Must be implemented by subclasses."""
        pass

    @abstractmethod
    async def scrape_category_page(self, category: str, page_num: int = 1) -> list[str]:
        """Scrape product URLs from a category page. Must be implemented by subclasses."""
        pass

    @abstractmethod
    async def scrape_bestseller_page(self, category: str) -> list[str]:
        """Scrape product URLs from bestseller page. Must be implemented by subclasses."""
        pass
