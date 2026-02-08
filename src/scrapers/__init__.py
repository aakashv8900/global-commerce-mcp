from .base import BaseScraper
from .amazon import AmazonScraper
from .flipkart import FlipkartScraper
from .walmart import WalmartScraper
from .alibaba import AlibabaScraper
from .ebay import EbayScraper
from .shopify import ShopifyScraper

__all__ = [
    "BaseScraper",
    "AmazonScraper",
    "FlipkartScraper",
    "WalmartScraper",
    "AlibabaScraper",
    "EbayScraper",
    "ShopifyScraper",
]
