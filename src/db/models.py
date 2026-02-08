"""SQLAlchemy models for CommerceSignal."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Platform(str, Enum):
    """Supported e-commerce platforms."""

    AMAZON_US = "amazon_us"
    FLIPKART_IN = "flipkart_in"
    WALMART_US = "walmart_us"
    ALIBABA_CN = "alibaba_cn"
    EBAY_US = "ebay_us"
    SHOPIFY = "shopify"



class Product(Base):
    """Product entity representing an e-commerce product."""

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    asin: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    brand: Mapped[str | None] = mapped_column(String(200), nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    daily_metrics: Mapped[list["DailyMetric"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Product(asin={self.asin}, title={self.title[:50]}...)>"


class DailyMetric(Base):
    """Daily metrics snapshot for a product."""

    __tablename__ = "daily_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    original_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    discount_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    reviews: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rating: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.0)
    seller_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    in_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    delivery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    buybox_owner: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    product: Mapped["Product"] = relationship(back_populates="daily_metrics")

    def __repr__(self) -> str:
        return f"<DailyMetric(product_id={self.product_id}, date={self.date}, price={self.price})>"


class Seller(Base):
    """Seller entity for seller analysis."""

    __tablename__ = "sellers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    seller_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    metrics: Mapped[list["SellerMetric"]] = relationship(
        back_populates="seller", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Seller(seller_id={self.seller_id}, name={self.name})>"


class SellerMetric(Base):
    """Periodic metrics snapshot for a seller."""

    __tablename__ = "seller_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    total_products: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_rating: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.0)
    total_reviews: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fulfillment_type: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    seller: Mapped["Seller"] = relationship(back_populates="metrics")

    def __repr__(self) -> str:
        return f"<SellerMetric(seller_id={self.seller_id}, date={self.date})>"


# ============================================================================
# Phase 3: Brand Intelligence Models
# ============================================================================

class Brand(Base):
    """Brand entity for brand-level intelligence."""

    __tablename__ = "brands"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    storefront_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    metrics: Mapped[list["BrandMetric"]] = relationship(
        back_populates="brand", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Brand(name={self.name}, platform={self.platform})>"


class BrandMetric(Base):
    """Daily metrics snapshot for a brand."""

    __tablename__ = "brand_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    product_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    avg_rating: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.0)
    total_reviews: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_velocity: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=0.0)
    avg_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    revenue_estimate: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    market_share_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    brand: Mapped["Brand"] = relationship(back_populates="metrics")

    def __repr__(self) -> str:
        return f"<BrandMetric(brand_id={self.brand_id}, date={self.date})>"


# ============================================================================
# Phase 5: Alerts & Subscriptions Models
# ============================================================================

class AlertType(str, Enum):
    """Types of alerts."""
    PRICE_DROP = "price_drop"
    STOCKOUT = "stockout"
    TREND_CHANGE = "trend_change"
    ARBITRAGE = "arbitrage"
    COMPETITOR = "competitor"
    RANK_CHANGE = "rank_change"


class NotificationChannel(str, Enum):
    """Notification delivery channels."""
    WEBHOOK = "webhook"
    MCP = "mcp"
    EMAIL = "email"


class AlertSubscription(Base):
    """User subscription to alerts."""

    __tablename__ = "alert_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=True
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=True
    )
    category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="amazon_us")
    threshold_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    threshold_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    notification_channel: Mapped[str] = mapped_column(String(50), nullable=False, default="mcp")
    webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    events: Mapped[list["AlertEvent"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AlertSubscription(id={self.id}, type={self.alert_type})>"


class AlertEvent(Base):
    """Triggered alert event."""

    __tablename__ = "alert_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alert_subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    previous_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    current_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    subscription: Mapped["AlertSubscription"] = relationship(back_populates="events")

    def __repr__(self) -> str:
        return f"<AlertEvent(id={self.id}, type={self.event_type})>"

