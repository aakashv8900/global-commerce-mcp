"""Feature engineering for ML models."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
import numpy as np

from src.db.models import Product, DailyMetric


@dataclass
class ProductFeatures:
    """Engineered features for a product."""
    product_id: str

    # Current state
    current_price: float
    current_rank: float
    current_reviews: int
    current_rating: float

    # Price features
    price_mean_7d: float
    price_std_7d: float
    price_min_30d: float
    price_max_30d: float
    price_trend_7d: float  # slope
    discount_frequency: float  # % of days with discount

    # Rank features
    rank_mean_7d: float
    rank_std_7d: float
    rank_improvement_7d: float
    rank_improvement_30d: float
    best_rank_30d: float

    # Review features
    review_velocity_7d: float
    review_velocity_30d: float
    review_acceleration: float  # change in velocity

    # Seasonality features
    day_of_week: int
    day_of_month: int
    is_weekend: bool
    is_month_end: bool

    # Category features
    category_encoded: int


class FeatureEngineer:
    """Engineers features for ML models from raw metrics."""

    # Category encoding mapping
    CATEGORY_ENCODING = {
        "Electronics": 0,
        "Home & Kitchen": 1,
        "Toys & Games": 2,
        "Sports & Outdoors": 3,
        "Beauty & Personal Care": 4,
        "Health & Household": 5,
        "Clothing": 6,
        "Books": 7,
        "Mobiles": 8,
        "Fashion": 9,
        "Appliances": 10,
        "Grocery": 11,
    }

    def engineer_features(
        self,
        product: Product,
        metrics: list[DailyMetric],
    ) -> ProductFeatures | None:
        """Engineer features from product metrics."""
        if len(metrics) < 7:
            return None

        # Sort by date descending
        sorted_metrics = sorted(metrics, key=lambda m: m.date, reverse=True)

        # Get windows
        latest = sorted_metrics[0]
        last_7 = sorted_metrics[:7]
        last_30 = sorted_metrics[:30] if len(sorted_metrics) >= 30 else sorted_metrics

        # Current state
        current_price = float(latest.price)
        current_rank = float(latest.rank) if latest.rank else 0.0
        current_reviews = latest.reviews
        current_rating = float(latest.rating)

        # Price features
        prices_7d = [float(m.price) for m in last_7]
        prices_30d = [float(m.price) for m in last_30]
        price_mean_7d = np.mean(prices_7d)
        price_std_7d = np.std(prices_7d)
        price_min_30d = min(prices_30d)
        price_max_30d = max(prices_30d)
        price_trend_7d = self._calculate_slope(prices_7d)
        discount_frequency = sum(1 for m in last_30 if m.discount_percent and m.discount_percent > 0) / len(last_30)

        # Rank features
        ranks_7d = [float(m.rank) for m in last_7 if m.rank]
        ranks_30d = [float(m.rank) for m in last_30 if m.rank]

        if ranks_7d:
            rank_mean_7d = np.mean(ranks_7d)
            rank_std_7d = np.std(ranks_7d)
            rank_improvement_7d = ranks_7d[-1] - ranks_7d[0] if len(ranks_7d) > 1 else 0
        else:
            rank_mean_7d = 0.0
            rank_std_7d = 0.0
            rank_improvement_7d = 0.0

        if ranks_30d:
            rank_improvement_30d = ranks_30d[-1] - ranks_30d[0] if len(ranks_30d) > 1 else 0
            best_rank_30d = min(ranks_30d)
        else:
            rank_improvement_30d = 0.0
            best_rank_30d = 0.0

        # Review features
        reviews_7d = [m.reviews for m in last_7]
        reviews_30d = [m.reviews for m in last_30]

        review_velocity_7d = (reviews_7d[0] - reviews_7d[-1]) / 7 if len(reviews_7d) > 1 else 0
        review_velocity_30d = (reviews_30d[0] - reviews_30d[-1]) / len(reviews_30d) if len(reviews_30d) > 1 else 0

        # Review acceleration (change in velocity)
        if len(reviews_7d) >= 7 and len(sorted_metrics) >= 14:
            prev_7d = sorted_metrics[7:14]
            prev_velocity = (prev_7d[0].reviews - prev_7d[-1].reviews) / 7 if len(prev_7d) > 1 else 0
            review_acceleration = review_velocity_7d - prev_velocity
        else:
            review_acceleration = 0.0

        # Seasonality features
        today = date.today()
        day_of_week = today.weekday()
        day_of_month = today.day
        is_weekend = day_of_week >= 5
        is_month_end = day_of_month >= 25

        # Category encoding
        category_encoded = self.CATEGORY_ENCODING.get(product.category, -1)

        return ProductFeatures(
            product_id=str(product.id),
            current_price=current_price,
            current_rank=current_rank,
            current_reviews=current_reviews,
            current_rating=current_rating,
            price_mean_7d=price_mean_7d,
            price_std_7d=price_std_7d,
            price_min_30d=price_min_30d,
            price_max_30d=price_max_30d,
            price_trend_7d=price_trend_7d,
            discount_frequency=discount_frequency,
            rank_mean_7d=rank_mean_7d,
            rank_std_7d=rank_std_7d,
            rank_improvement_7d=rank_improvement_7d,
            rank_improvement_30d=rank_improvement_30d,
            best_rank_30d=best_rank_30d,
            review_velocity_7d=review_velocity_7d,
            review_velocity_30d=review_velocity_30d,
            review_acceleration=review_acceleration,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            is_weekend=is_weekend,
            is_month_end=is_month_end,
            category_encoded=category_encoded,
        )

    def features_to_array(self, features: ProductFeatures) -> np.ndarray:
        """Convert features to numpy array for model input."""
        return np.array([
            features.current_price,
            features.current_rank,
            features.current_reviews,
            features.current_rating,
            features.price_mean_7d,
            features.price_std_7d,
            features.price_min_30d,
            features.price_max_30d,
            features.price_trend_7d,
            features.discount_frequency,
            features.rank_mean_7d,
            features.rank_std_7d,
            features.rank_improvement_7d,
            features.rank_improvement_30d,
            features.best_rank_30d,
            features.review_velocity_7d,
            features.review_velocity_30d,
            features.review_acceleration,
            features.day_of_week,
            features.day_of_month,
            float(features.is_weekend),
            float(features.is_month_end),
            features.category_encoded,
        ])

    def _calculate_slope(self, values: list[float]) -> float:
        """Calculate linear regression slope."""
        if len(values) < 2:
            return 0.0
        x = np.arange(len(values))
        slope, _ = np.polyfit(x, values, 1)
        return float(slope)

    @staticmethod
    def get_feature_names() -> list[str]:
        """Get ordered list of feature names."""
        return [
            "current_price",
            "current_rank",
            "current_reviews",
            "current_rating",
            "price_mean_7d",
            "price_std_7d",
            "price_min_30d",
            "price_max_30d",
            "price_trend_7d",
            "discount_frequency",
            "rank_mean_7d",
            "rank_std_7d",
            "rank_improvement_7d",
            "rank_improvement_30d",
            "best_rank_30d",
            "review_velocity_7d",
            "review_velocity_30d",
            "review_acceleration",
            "day_of_week",
            "day_of_month",
            "is_weekend",
            "is_month_end",
            "category_encoded",
        ]
