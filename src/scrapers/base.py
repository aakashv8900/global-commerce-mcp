"""Base scraper class with anti-blocking and stealth features."""

import asyncio
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

from src.config import settings
from src.scrapers.proxy_manager import proxy_manager, rate_limiter, circuit_breaker


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
    
    # Optional fields for platform compatibility
    platform: str = "unknown"
    product_id: str = ""
    url: str = ""


@dataclass
class ScrapedMetrics:
    """Daily metrics scraped from a product page."""
    
    price: Decimal
    original_price: Decimal | None
    discount_percent: float | None
    rank: int | None
    reviews: int
    rating: float
    seller_count: int
    in_stock: bool
    delivery_days: int | None
    buybox_owner: str | None


class BaseScraper(ABC):
    """Abstract base class for e-commerce scrapers with anti-blocking."""

    PLATFORM = "unknown"
    MAX_RETRIES = 3
    
    # User agents for rotation
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    ]
    
    # Viewports to rotate
    VIEWPORTS = [
        {"width": 1920, "height": 1080},
        {"width": 1366, "height": 768},
        {"width": 1536, "height": 864},
        {"width": 1440, "height": 900},
        {"width": 1280, "height": 720},
    ]
    
    # Locales to rotate
    LOCALES = ["en-US", "en-GB", "en-CA", "en-AU"]

    def __init__(self):
        self.browser: Browser | None = None
        self.playwright = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.playwright = await async_playwright().start()
        
        # Launch with stealth args
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu",
                "--window-size=1920,1080",
            ],
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    def _get_random_user_agent(self) -> str:
        """Get a random user agent string."""
        return random.choice(self.USER_AGENTS)
    
    def _get_random_viewport(self) -> dict:
        """Get a random viewport size."""
        return random.choice(self.VIEWPORTS)
    
    def _get_random_locale(self) -> str:
        """Get a random locale."""
        return random.choice(self.LOCALES)

    async def _get_page(self) -> Page:
        """Create a new page with anti-detection measures."""
        if not self.browser:
            raise RuntimeError("Browser not initialized")
        
        # Get proxy if available
        proxy = proxy_manager.get_proxy()
        proxy_settings = None
        if proxy:
            proxy_settings = {
                "server": f"{proxy.protocol}://{proxy.host}:{proxy.port}",
            }
            if proxy.username:
                proxy_settings["username"] = proxy.username
                proxy_settings["password"] = proxy.password

        # Create context with randomized fingerprint
        context = await self.browser.new_context(
            user_agent=self._get_random_user_agent(),
            viewport=self._get_random_viewport(),
            locale=self._get_random_locale(),
            timezone_id="America/New_York",
            proxy=proxy_settings,
            java_script_enabled=True,
            has_touch=False,
            is_mobile=False,
            color_scheme="light",
            ignore_https_errors=True,  # Fix SSL errors with proxy
        )
        
        # Block unnecessary resources for speed
        await context.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2}", lambda route: route.abort())
        
        page = await context.new_page()

        # Stealth JavaScript injection
        await page.add_init_script("""
            // Override navigator properties
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            
            // Override chrome property
            window.chrome = {runtime: {}};
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({state: Notification.permission}) :
                originalQuery(parameters)
            );
            
            // Hide automation indicators
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        """)

        return page

    async def _random_delay(self, min_delay: float = None, max_delay: float = None):
        """Add random delay between requests."""
        min_d = min_delay or getattr(settings, 'scrape_delay_min', 1.0)
        max_d = max_delay or getattr(settings, 'scrape_delay_max', 3.0)
        delay = random.uniform(min_d, max_d)
        await asyncio.sleep(delay)

    async def _human_scroll(self, page: Page):
        """Simulate human-like scrolling."""
        for _ in range(random.randint(2, 5)):
            scroll_y = random.randint(200, 500)
            await page.mouse.wheel(0, scroll_y)
            await asyncio.sleep(random.uniform(0.3, 0.8))

    async def scrape_with_retry(self, url: str) -> ScrapedProduct | None:
        """Scrape with retry logic and circuit breaker."""
        # Check circuit breaker
        if circuit_breaker.is_open(self.PLATFORM):
            print(f"Circuit breaker open for {self.PLATFORM}, skipping")
            return None
        
        # Rate limiting
        await rate_limiter.acquire()
        
        for attempt in range(self.MAX_RETRIES):
            try:
                result = await self.scrape_product(url)
                if result:
                    circuit_breaker.record_success(self.PLATFORM)
                    return result
                else:
                    # Null result might mean blocked
                    circuit_breaker.record_failure(self.PLATFORM)
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for {url}: {e}")
                circuit_breaker.record_failure(self.PLATFORM)
                
                if attempt < self.MAX_RETRIES - 1:
                    # Exponential backoff
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(wait_time)
        
        return None

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
