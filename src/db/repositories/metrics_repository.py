"""Metrics repository for database operations."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import DailyMetric


class MetricsRepository:
    """Repository for DailyMetric CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_latest(self, product_id: uuid.UUID) -> DailyMetric | None:
        """Get the most recent metric for a product."""
        stmt = (
            select(DailyMetric)
            .where(DailyMetric.product_id == product_id)
            .order_by(DailyMetric.date.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_date_range(
        self, product_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[DailyMetric]:
        """Get metrics for a product within a date range."""
        stmt = (
            select(DailyMetric)
            .where(
                DailyMetric.product_id == product_id,
                DailyMetric.date >= start_date,
                DailyMetric.date <= end_date,
            )
            .order_by(DailyMetric.date.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_last_n_days(
        self, product_id: uuid.UUID, days: int = 30
    ) -> list[DailyMetric]:
        """Get metrics for the last N days."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        return await self.get_by_date_range(product_id, start_date, end_date)

    async def create(
        self,
        product_id: uuid.UUID,
        metric_date: date,
        price: Decimal,
        reviews: int,
        rating: float,
        seller_count: int = 1,
        in_stock: bool = True,
        original_price: Decimal | None = None,
        discount_percent: float | None = None,
        rank: int | None = None,
        delivery_days: int | None = None,
        buybox_owner: str | None = None,
    ) -> DailyMetric:
        """Create a new daily metric."""
        metric = DailyMetric(
            product_id=product_id,
            date=metric_date,
            price=price,
            original_price=original_price,
            discount_percent=discount_percent,
            rank=rank,
            reviews=reviews,
            rating=rating,
            seller_count=seller_count,
            in_stock=in_stock,
            delivery_days=delivery_days,
            buybox_owner=buybox_owner,
        )
        self.session.add(metric)
        await self.session.flush()
        return metric

    async def get_review_velocity(
        self, product_id: uuid.UUID, days: int = 30
    ) -> float:
        """Calculate review velocity over the specified period."""
        metrics = await self.get_last_n_days(product_id, days)
        if len(metrics) < 2:
            return 0.0

        oldest = metrics[0]
        newest = metrics[-1]
        day_diff = (newest.date - oldest.date).days

        if day_diff == 0:
            return 0.0

        return (newest.reviews - oldest.reviews) / day_diff

    async def get_rank_improvement(
        self, product_id: uuid.UUID, days: int = 30
    ) -> float:
        """Calculate rank improvement over the specified period."""
        metrics = await self.get_last_n_days(product_id, days)
        if len(metrics) < 2:
            return 0.0

        oldest = metrics[0]
        newest = metrics[-1]

        if oldest.rank is None or newest.rank is None or oldest.rank == 0:
            return 0.0

        # Positive value = rank improved (lower rank is better)
        return (oldest.rank - newest.rank) / oldest.rank

    async def get_price_drops(
        self, product_id: uuid.UUID, days: int = 90
    ) -> list[tuple[date, Decimal]]:
        """Get all significant price drops in the period."""
        metrics = await self.get_last_n_days(product_id, days)
        if len(metrics) < 2:
            return []

        price_drops = []
        for i in range(1, len(metrics)):
            prev_price = metrics[i - 1].price
            curr_price = metrics[i].price
            
            # Consider it a drop if price decreased by more than 5%
            if prev_price > 0 and curr_price < prev_price * Decimal("0.95"):
                price_drops.append((metrics[i].date, curr_price))

        return price_drops

    async def get_stockout_frequency(
        self, product_id: uuid.UUID, days: int = 30
    ) -> float:
        """Calculate stockout frequency (% of days out of stock)."""
        metrics = await self.get_last_n_days(product_id, days)
        if not metrics:
            return 0.0

        out_of_stock_days = sum(1 for m in metrics if not m.in_stock)
        return out_of_stock_days / len(metrics)
