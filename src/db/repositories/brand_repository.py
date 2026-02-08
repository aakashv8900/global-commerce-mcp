"""Brand repository for brand-level data access."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Brand, BrandMetric, Product, DailyMetric


class BrandRepository:
    """Repository for brand CRUD operations and aggregations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        platform: str,
        name: str,
        slug: str,
        category: str | None = None,
        logo_url: str | None = None,
        storefront_url: str | None = None,
    ) -> Brand:
        """Create a new brand."""
        brand = Brand(
            platform=platform,
            name=name,
            slug=slug,
            category=category,
            logo_url=logo_url,
            storefront_url=storefront_url,
        )
        self.session.add(brand)
        await self.session.flush()
        return brand

    async def get_by_id(self, brand_id: uuid.UUID) -> Brand | None:
        """Get brand by ID."""
        result = await self.session.execute(
            select(Brand).where(Brand.id == brand_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str, platform: str = "amazon_us") -> Brand | None:
        """Get brand by name and platform."""
        result = await self.session.execute(
            select(Brand).where(
                and_(
                    func.lower(Brand.name) == name.lower(),
                    Brand.platform == platform
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str, platform: str = "amazon_us") -> Brand | None:
        """Get brand by slug and platform."""
        result = await self.session.execute(
            select(Brand).where(
                and_(Brand.slug == slug, Brand.platform == platform)
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        name: str,
        platform: str = "amazon_us",
        category: str | None = None,
    ) -> tuple[Brand, bool]:
        """Get existing brand or create new one. Returns (brand, created)."""
        existing = await self.get_by_name(name, platform)
        if existing:
            return existing, False

        slug = name.lower().replace(" ", "-").replace("'", "")
        brand = await self.create(
            platform=platform,
            name=name,
            slug=slug,
            category=category,
        )
        return brand, True

    async def get_all(
        self,
        platform: str | None = None,
        category: str | None = None,
        limit: int = 100,
    ) -> list[Brand]:
        """Get all brands with optional filters."""
        query = select(Brand)

        if platform:
            query = query.where(Brand.platform == platform)
        if category:
            query = query.where(Brand.category == category)

        query = query.order_by(Brand.name).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_with_metrics(
        self,
        brand_id: uuid.UUID,
        days: int = 30,
    ) -> tuple[Brand | None, list[BrandMetric]]:
        """Get brand with recent metrics."""
        brand = await self.get_by_id(brand_id)
        if not brand:
            return None, []

        since = date.today() - timedelta(days=days)
        result = await self.session.execute(
            select(BrandMetric)
            .where(
                and_(
                    BrandMetric.brand_id == brand_id,
                    BrandMetric.date >= since
                )
            )
            .order_by(BrandMetric.date.desc())
        )
        metrics = list(result.scalars().all())
        return brand, metrics

    async def search(
        self,
        query: str,
        platform: str | None = None,
        limit: int = 20,
    ) -> list[Brand]:
        """Search brands by name."""
        stmt = select(Brand).where(
            Brand.name.ilike(f"%{query}%")
        )

        if platform:
            stmt = stmt.where(Brand.platform == platform)

        stmt = stmt.order_by(Brand.name).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_top_brands_by_revenue(
        self,
        platform: str = "amazon_us",
        category: str | None = None,
        limit: int = 10,
    ) -> list[tuple[Brand, Decimal]]:
        """Get top brands by estimated revenue."""
        # Get latest metrics for each brand
        subquery = (
            select(
                BrandMetric.brand_id,
                func.max(BrandMetric.date).label("latest_date")
            )
            .group_by(BrandMetric.brand_id)
            .subquery()
        )

        query = (
            select(Brand, BrandMetric.revenue_estimate)
            .join(BrandMetric, Brand.id == BrandMetric.brand_id)
            .join(
                subquery,
                and_(
                    BrandMetric.brand_id == subquery.c.brand_id,
                    BrandMetric.date == subquery.c.latest_date
                )
            )
            .where(Brand.platform == platform)
        )

        if category:
            query = query.where(Brand.category == category)

        query = query.order_by(BrandMetric.revenue_estimate.desc()).limit(limit)
        result = await self.session.execute(query)
        return [(row[0], row[1]) for row in result.all()]


class BrandMetricRepository:
    """Repository for brand metrics."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        brand_id: uuid.UUID,
        metric_date: date,
        product_count: int,
        avg_price: Decimal,
        avg_rating: float,
        total_reviews: int,
        review_velocity: float,
        avg_rank: int | None = None,
        revenue_estimate: Decimal = Decimal("0"),
        market_share_percent: float = 0.0,
    ) -> BrandMetric:
        """Create a new brand metric entry."""
        metric = BrandMetric(
            brand_id=brand_id,
            date=metric_date,
            product_count=product_count,
            avg_price=avg_price,
            avg_rating=avg_rating,
            total_reviews=total_reviews,
            review_velocity=review_velocity,
            avg_rank=avg_rank,
            revenue_estimate=revenue_estimate,
            market_share_percent=market_share_percent,
        )
        self.session.add(metric)
        await self.session.flush()
        return metric

    async def get_latest(self, brand_id: uuid.UUID) -> BrandMetric | None:
        """Get latest metric for a brand."""
        result = await self.session.execute(
            select(BrandMetric)
            .where(BrandMetric.brand_id == brand_id)
            .order_by(BrandMetric.date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_history(
        self,
        brand_id: uuid.UUID,
        days: int = 30,
    ) -> list[BrandMetric]:
        """Get metric history for a brand."""
        since = date.today() - timedelta(days=days)
        result = await self.session.execute(
            select(BrandMetric)
            .where(
                and_(
                    BrandMetric.brand_id == brand_id,
                    BrandMetric.date >= since
                )
            )
            .order_by(BrandMetric.date.asc())
        )
        return list(result.scalars().all())

    async def aggregate_from_products(
        self,
        brand_name: str,
        platform: str = "amazon_us",
    ) -> dict:
        """Aggregate metrics from products belonging to a brand."""
        # Get products for this brand
        result = await self.session.execute(
            select(Product)
            .where(
                and_(
                    func.lower(Product.brand) == brand_name.lower(),
                    Product.platform == platform
                )
            )
        )
        products = list(result.scalars().all())

        if not products:
            return {}

        product_ids = [p.id for p in products]

        # Get latest metrics for each product
        today = date.today()
        week_ago = today - timedelta(days=7)

        result = await self.session.execute(
            select(DailyMetric)
            .where(
                and_(
                    DailyMetric.product_id.in_(product_ids),
                    DailyMetric.date >= week_ago
                )
            )
            .order_by(DailyMetric.date.desc())
        )
        metrics = list(result.scalars().all())

        if not metrics:
            return {}

        # Calculate aggregates
        latest_by_product = {}
        for m in metrics:
            if m.product_id not in latest_by_product:
                latest_by_product[m.product_id] = m

        latest_metrics = list(latest_by_product.values())

        total_reviews = sum(m.reviews for m in latest_metrics)
        avg_price = sum(m.price for m in latest_metrics) / len(latest_metrics)
        avg_rating = sum(m.rating for m in latest_metrics) / len(latest_metrics)
        ranks = [m.rank for m in latest_metrics if m.rank]
        avg_rank = sum(ranks) // len(ranks) if ranks else None

        return {
            "product_count": len(products),
            "avg_price": avg_price,
            "avg_rating": avg_rating,
            "total_reviews": total_reviews,
            "avg_rank": avg_rank,
        }
