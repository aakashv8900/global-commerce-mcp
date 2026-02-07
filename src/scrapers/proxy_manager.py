"""Proxy manager with ScraperAPI direct rendering support."""

import random
import asyncio
import aiohttp
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta

from src.config import settings


@dataclass
class ProxyConfig:
    """Proxy configuration."""
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = "http"
    
    @property
    def url(self) -> str:
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"


class ScraperAPIClient:
    """Client for ScraperAPI direct rendering (more reliable than proxy mode)."""
    
    BASE_URL = "https://api.scraperapi.com"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def fetch_html(self, url: str, render_js: bool = True) -> Optional[str]:
        """Fetch page HTML using ScraperAPI."""
        params = {
            "api_key": self.api_key,
            "url": url,
            "render": str(render_js).lower(),
            "country_code": "us",
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.BASE_URL,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        print(f"ScraperAPI error {response.status}: {await response.text()}")
                        return None
        except Exception as e:
            print(f"ScraperAPI request failed: {e}")
            return None


class ProxyManager:
    """Manages proxy rotation for scrapers."""
    
    def __init__(self):
        self.proxies: list[ProxyConfig] = []
        self.failed_proxies: dict[str, datetime] = {}
        self.current_index = 0
        self.scraper_api_client: Optional[ScraperAPIClient] = None
        self._load_proxies()
    
    def _load_proxies(self):
        """Load proxies from config or environment."""
        # Check for ScraperAPI key - use direct API mode
        scraper_api_key = getattr(settings, 'scraper_api_key', None)
        if scraper_api_key:
            self.scraper_api_client = ScraperAPIClient(scraper_api_key)
            print(f"ScraperAPI configured in direct mode")
        
        # Check for Bright Data credentials
        bright_data_user = getattr(settings, 'bright_data_user', None)
        bright_data_pass = getattr(settings, 'bright_data_pass', None)
        if bright_data_user and bright_data_pass:
            self.proxies.append(ProxyConfig(
                host="brd.superproxy.io",
                port=22225,
                username=bright_data_user,
                password=bright_data_pass,
            ))
    
    def has_scraper_api(self) -> bool:
        """Check if ScraperAPI is configured."""
        return self.scraper_api_client is not None
    
    async def fetch_with_scraper_api(self, url: str) -> Optional[str]:
        """Fetch page using ScraperAPI direct rendering."""
        if self.scraper_api_client:
            return await self.scraper_api_client.fetch_html(url)
        return None
    
    def get_proxy(self) -> Optional[ProxyConfig]:
        """Get next available proxy with rotation."""
        if not self.proxies:
            return None
        
        # Clean expired failures (retry after 5 minutes)
        now = datetime.now()
        self.failed_proxies = {
            k: v for k, v in self.failed_proxies.items()
            if now - v < timedelta(minutes=5)
        }
        
        # Find available proxy
        for _ in range(len(self.proxies)):
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
            
            if proxy.url not in self.failed_proxies:
                return proxy
        
        # All proxies failed, return first one anyway
        return self.proxies[0] if self.proxies else None
    
    def mark_failed(self, proxy: ProxyConfig):
        """Mark a proxy as failed."""
        self.failed_proxies[proxy.url] = datetime.now()
    
    def mark_success(self, proxy: ProxyConfig):
        """Mark a proxy as successful."""
        if proxy.url in self.failed_proxies:
            del self.failed_proxies[proxy.url]


class RateLimiter:
    """Rate limiter for scrapers."""
    
    def __init__(self, requests_per_minute: int = 10):
        self.requests_per_minute = requests_per_minute
        self.request_times: list[datetime] = []
    
    async def acquire(self):
        """Wait if rate limit exceeded."""
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        
        # Clean old entries
        self.request_times = [t for t in self.request_times if t > minute_ago]
        
        if len(self.request_times) >= self.requests_per_minute:
            # Wait until oldest request expires
            wait_time = (self.request_times[0] - minute_ago).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time + 0.1)
        
        self.request_times.append(now)


class CircuitBreaker:
    """Circuit breaker for failing scrapers."""
    
    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures: dict[str, int] = {}
        self.open_circuits: dict[str, datetime] = {}
    
    def is_open(self, platform: str) -> bool:
        """Check if circuit is open (blocking requests)."""
        if platform in self.open_circuits:
            if datetime.now() - self.open_circuits[platform] > timedelta(seconds=self.reset_timeout):
                # Reset circuit
                del self.open_circuits[platform]
                self.failures[platform] = 0
                return False
            return True
        return False
    
    def record_failure(self, platform: str):
        """Record a failure for a platform."""
        self.failures[platform] = self.failures.get(platform, 0) + 1
        if self.failures[platform] >= self.failure_threshold:
            self.open_circuits[platform] = datetime.now()
    
    def record_success(self, platform: str):
        """Record a success for a platform."""
        self.failures[platform] = 0
        if platform in self.open_circuits:
            del self.open_circuits[platform]


# Global instances
proxy_manager = ProxyManager()
rate_limiter = RateLimiter(requests_per_minute=30)
circuit_breaker = CircuitBreaker(failure_threshold=10, reset_timeout=300)
