"""Free proxy manager with enhanced stealth - no paid services required."""

import random
import asyncio
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta


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
    """Free proxy manager - uses direct connection with enhanced stealth."""
    
    def __init__(self):
        self.failed_proxies: dict[str, datetime] = {}
        self.scraper_api_client = None  # No paid services
        print("Running in FREE mode - enhanced stealth without paid proxies")
    
    def has_scraper_api(self) -> bool:
        """Always False for free mode."""
        return False
    
    async def fetch_with_scraper_api(self, url: str) -> Optional[str]:
        """Not available in free mode."""
        return None
    
    def get_proxy(self) -> Optional[ProxyConfig]:
        """No proxy in free mode - rely on stealth."""
        return None
    
    def mark_failed(self, proxy: ProxyConfig):
        """Mark a proxy as failed."""
        pass
    
    def mark_success(self, proxy: ProxyConfig):
        """Mark a proxy as successful."""
        pass


class RateLimiter:
    """Rate limiter for scrapers - slower for free mode to avoid blocks."""
    
    def __init__(self, requests_per_minute: int = 5):  # Slower for free mode
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
                await asyncio.sleep(wait_time + 0.5)
        
        self.request_times.append(now)


class CircuitBreaker:
    """Circuit breaker for failing scrapers."""
    
    def __init__(self, failure_threshold: int = 3, reset_timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout  # 5 minutes for free mode
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
            print(f"Circuit breaker OPEN for {platform} - waiting {self.reset_timeout}s")
    
    def record_success(self, platform: str):
        """Record a success for a platform."""
        self.failures[platform] = 0
        if platform in self.open_circuits:
            del self.open_circuits[platform]


# Global instances - configured for free mode
proxy_manager = ProxyManager()
rate_limiter = RateLimiter(requests_per_minute=5)  # Slower for free
circuit_breaker = CircuitBreaker(failure_threshold=3, reset_timeout=300)
