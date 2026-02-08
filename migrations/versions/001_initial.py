"""Initial migration - create all tables

Revision ID: 001_initial
Revises: 
Create Date: 2026-02-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Products table
    op.create_table(
        'products',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('platform', sa.String(50), nullable=False, index=True),
        sa.Column('asin', sa.String(20), nullable=False, index=True),
        sa.Column('url', sa.Text, nullable=False),
        sa.Column('title', sa.Text, nullable=False),
        sa.Column('category', sa.String(200), nullable=False, index=True),
        sa.Column('brand', sa.String(200), nullable=True),
        sa.Column('image_url', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Daily metrics table
    op.create_table(
        'daily_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date', sa.Date, nullable=False, index=True),
        sa.Column('price', sa.Numeric(12, 2), nullable=False),
        sa.Column('original_price', sa.Numeric(12, 2), nullable=True),
        sa.Column('discount_percent', sa.Numeric(5, 2), nullable=True),
        sa.Column('rank', sa.Integer, nullable=True, index=True),
        sa.Column('reviews', sa.Integer, nullable=False, default=0),
        sa.Column('rating', sa.Numeric(3, 2), nullable=False, default=0.0),
        sa.Column('seller_count', sa.Integer, nullable=False, default=1),
        sa.Column('in_stock', sa.Boolean, nullable=False, default=True),
        sa.Column('delivery_days', sa.Integer, nullable=True),
        sa.Column('buybox_owner', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Sellers table
    op.create_table(
        'sellers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('platform', sa.String(50), nullable=False, index=True),
        sa.Column('seller_id', sa.String(50), nullable=False, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Seller metrics table
    op.create_table(
        'seller_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('seller_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sellers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date', sa.Date, nullable=False, index=True),
        sa.Column('total_products', sa.Integer, nullable=False, default=0),
        sa.Column('avg_rating', sa.Numeric(3, 2), nullable=False, default=0.0),
        sa.Column('total_reviews', sa.Integer, nullable=False, default=0),
        sa.Column('fulfillment_type', sa.String(50), nullable=False, default='unknown'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Brands table (Phase 3)
    op.create_table(
        'brands',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('platform', sa.String(50), nullable=False, index=True),
        sa.Column('name', sa.String(200), nullable=False, index=True),
        sa.Column('slug', sa.String(200), nullable=False, index=True),
        sa.Column('category', sa.String(200), nullable=True),
        sa.Column('logo_url', sa.Text, nullable=True),
        sa.Column('storefront_url', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Brand metrics table (Phase 3)
    op.create_table(
        'brand_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('brand_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('brands.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date', sa.Date, nullable=False, index=True),
        sa.Column('product_count', sa.Integer, nullable=False, default=0),
        sa.Column('avg_price', sa.Numeric(12, 2), nullable=False, default=0),
        sa.Column('avg_rating', sa.Numeric(3, 2), nullable=False, default=0.0),
        sa.Column('total_reviews', sa.Integer, nullable=False, default=0),
        sa.Column('review_velocity', sa.Numeric(10, 4), nullable=False, default=0.0),
        sa.Column('avg_rank', sa.Integer, nullable=True),
        sa.Column('revenue_estimate', sa.Numeric(14, 2), nullable=False, default=0),
        sa.Column('market_share_percent', sa.Numeric(5, 2), nullable=False, default=0.0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Alert subscriptions table (Phase 5)
    op.create_table(
        'alert_subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.String(100), nullable=False, index=True),
        sa.Column('alert_type', sa.String(50), nullable=False, index=True),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=True),
        sa.Column('brand_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('brands.id', ondelete='CASCADE'), nullable=True),
        sa.Column('category', sa.String(200), nullable=True),
        sa.Column('platform', sa.String(50), nullable=False, default='amazon_us'),
        sa.Column('threshold_value', sa.Numeric(12, 2), nullable=True),
        sa.Column('threshold_percent', sa.Numeric(5, 2), nullable=True),
        sa.Column('notification_channel', sa.String(50), nullable=False, default='mcp'),
        sa.Column('webhook_url', sa.Text, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Alert events table (Phase 5)
    op.create_table(
        'alert_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('alert_subscriptions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_data', sa.Text, nullable=False),
        sa.Column('previous_value', sa.String(100), nullable=True),
        sa.Column('current_value', sa.String(100), nullable=True),
        sa.Column('triggered_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('acknowledged', sa.Boolean, nullable=False, default=False),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Create unique constraints
    op.create_unique_constraint('uq_products_platform_asin', 'products', ['platform', 'asin'])
    op.create_unique_constraint('uq_sellers_platform_seller_id', 'sellers', ['platform', 'seller_id'])
    op.create_unique_constraint('uq_brands_platform_slug', 'brands', ['platform', 'slug'])


def downgrade() -> None:
    op.drop_table('alert_events')
    op.drop_table('alert_subscriptions')
    op.drop_table('brand_metrics')
    op.drop_table('brands')
    op.drop_table('seller_metrics')
    op.drop_table('sellers')
    op.drop_table('daily_metrics')
    op.drop_table('products')
