"""Proxy manager for scraper anti-blocking."""

import random
import asyncio
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


class ProxyManager:
    """Manages proxy rotation for scrapers."""
    
    # Free proxy list (rotate these)
    FREE_PROXIES = [
        # These are examples - in production, fetch from proxy APIs
        {"host": "proxy1.example.com", "port": 8080},
        {"host": "proxy2.example.com", "port": 8080},
    ]
    
    def __init__(self):
        self.proxies: list[ProxyConfig] = []
        self.failed_proxies: dict[str, datetime] = {}
        self.current_index = 0
        self._load_proxies()
    
    def _load_proxies(self):
        """Load proxies from config or environment."""
        # Check for ScraperAPI key
        scraper_api_key = getattr(settings, 'scraper_api_key', None)
        if scraper_api_key:
            # ScraperAPI proxy format
            self.proxies.append(ProxyConfig(
                host="proxy-server.scraperapi.com",
                port=8001,
                username="scraperapi",
                password=scraper_api_key,
            ))
        
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
        
        # If no paid proxies, use direct connection with stealth
        if not self.proxies:
            self.proxies = []  # Empty = direct connection
    
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
circuit_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=120)
