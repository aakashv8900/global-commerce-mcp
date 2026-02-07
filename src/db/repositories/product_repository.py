"""Product repository for database operations."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Product, DailyMetric


class ProductRepository:
    """Repository for Product CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, product_id: uuid.UUID) -> Product | None:
        """Get product by ID with daily metrics."""
        stmt = (
            select(Product)
            .where(Product.id == product_id)
            .options(selectinload(Product.daily_metrics))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_asin(self, asin: str, platform: str = "amazon_us") -> Product | None:
        """Get product by ASIN and platform."""
        stmt = select(Product).where(
            Product.asin == asin,
            Product.platform == platform,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_url(self, url: str) -> Product | None:
        """Get product by URL."""
        stmt = select(Product).where(Product.url == url)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_category(
        self, category: str, platform: str = "amazon_us", limit: int = 100
    ) -> list[Product]:
        """Get products by category."""
        stmt = (
            select(Product)
            .where(Product.category == category, Product.platform == platform)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        platform: str,
        asin: str,
        url: str,
        title: str,
        category: str,
        brand: str | None = None,
        image_url: str | None = None,
    ) -> Product:
        """Create a new product."""
        product = Product(
            platform=platform,
            asin=asin,
            url=url,
            title=title,
            category=category,
            brand=brand,
            image_url=image_url,
        )
        self.session.add(product)
        await self.session.flush()
        return product

    async def get_or_create(
        self,
        platform: str,
        asin: str,
        url: str,
        title: str,
        category: str,
        brand: str | None = None,
        image_url: str | None = None,
    ) -> tuple[Product, bool]:
        """Get existing product or create new one. Returns (product, created)."""
        existing = await self.get_by_asin(asin, platform)
        if existing:
            return existing, False
        product = await self.create(
            platform=platform,
            asin=asin,
            url=url,
            title=title,
            category=category,
            brand=brand,
            image_url=image_url,
        )
        return product, True

    async def get_trending_by_category(
        self, category: str, platform: str = "amazon_us", limit: int = 10
    ) -> list[Product]:
        """Get trending products in a category based on recent metrics."""
        # Get products with their latest metrics
        stmt = (
            select(Product)
            .where(Product.category == category, Product.platform == platform)
            .options(selectinload(Product.daily_metrics))
            .limit(limit * 2)  # Get more to filter
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search(
        self, query: str, platform: str = "amazon_us", limit: int = 50
    ) -> list[Product]:
        """Search products by title."""
        stmt = (
            select(Product)
            .where(Product.title.ilike(f"%{query}%"), Product.platform == platform)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
