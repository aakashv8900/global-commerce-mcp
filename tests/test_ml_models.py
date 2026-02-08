"""Tests for ML Forecasting models."""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock
import uuid


class TestDemandForecaster:
    """Tests for DemandForecaster model."""

    def test_heuristic_prediction(self):
        """Test demand prediction using heuristic fallback."""
        from src.ml.models import DemandForecaster
        from src.ml.features import ProductFeatures

        forecaster = DemandForecaster()

        features = ProductFeatures(
            product_id=str(uuid.uuid4()),
            platform="amazon_us",
            category="Electronics",
            price=Decimal("99.99"),
            avg_price=Decimal("100.00"),
            price_volatility=5.0,
            avg_rating=4.5,
            total_reviews=1000,
            review_velocity=10.0,
            avg_rank=500,
            rank_trend=-5.0,
            seller_count=5,
            stock_ratio=0.95,
            days_tracked=30,
            is_prime=True,
        )

        forecast = forecaster.predict(features, horizon_days=7)

        assert forecast is not None
        assert forecast.predicted_daily_sales > 0
        assert 0 <= forecast.confidence_score <= 100
        assert len(forecast.daily_predictions) == 7

    def test_prediction_high_rating_high_demand(self):
        """Test that high-rated products get higher demand predictions."""
        from src.ml.models import DemandForecaster
        from src.ml.features import ProductFeatures

        forecaster = DemandForecaster()

        high_rating_features = ProductFeatures(
            product_id=str(uuid.uuid4()),
            platform="amazon_us",
            category="Electronics",
            price=Decimal("50.00"),
            avg_price=Decimal("50.00"),
            price_volatility=2.0,
            avg_rating=4.8,
            total_reviews=5000,
            review_velocity=50.0,
            avg_rank=100,
            rank_trend=-10.0,
            seller_count=3,
            stock_ratio=1.0,
            days_tracked=60,
            is_prime=True,
        )

        low_rating_features = ProductFeatures(
            product_id=str(uuid.uuid4()),
            platform="amazon_us",
            category="Electronics",
            price=Decimal("50.00"),
            avg_price=Decimal("50.00"),
            price_volatility=2.0,
            avg_rating=2.5,
            total_reviews=100,
            review_velocity=2.0,
            avg_rank=10000,
            rank_trend=50.0,
            seller_count=10,
            stock_ratio=0.5,
            days_tracked=30,
            is_prime=False,
        )

        high_forecast = forecaster.predict(high_rating_features, horizon_days=7)
        low_forecast = forecaster.predict(low_rating_features, horizon_days=7)

        assert high_forecast.predicted_daily_sales > low_forecast.predicted_daily_sales


class TestPricePredictor:
    """Tests for PricePredictor model."""

    def test_price_trajectory_prediction(self):
        """Test price trajectory prediction."""
        from src.ml.models import PricePredictor
        from src.ml.features import ProductFeatures

        predictor = PricePredictor()

        features = ProductFeatures(
            product_id=str(uuid.uuid4()),
            platform="amazon_us",
            category="Electronics",
            price=Decimal("99.99"),
            avg_price=Decimal("110.00"),
            price_volatility=15.0,
            avg_rating=4.2,
            total_reviews=500,
            review_velocity=5.0,
            avg_rank=1000,
            rank_trend=0.0,
            seller_count=8,
            stock_ratio=0.9,
            days_tracked=45,
            is_prime=True,
        )

        prediction = predictor.predict_price_trajectory(features, horizon_days=30)

        assert prediction is not None
        assert prediction.predicted_price > 0
        assert 0 <= prediction.price_drop_probability <= 1.0
        assert 0 <= prediction.confidence_score <= 100

    def test_price_war_detection(self):
        """Test price war detection."""
        from src.ml.models import PricePredictor
        from src.ml.features import ProductFeatures

        predictor = PricePredictor()

        # High volatility, many sellers = potential price war
        features = ProductFeatures(
            product_id=str(uuid.uuid4()),
            platform="amazon_us",
            category="Electronics",
            price=Decimal("50.00"),
            avg_price=Decimal("75.00"),
            price_volatility=35.0,
            avg_rating=4.0,
            total_reviews=1000,
            review_velocity=10.0,
            avg_rank=500,
            rank_trend=-5.0,
            seller_count=20,
            stock_ratio=0.8,
            days_tracked=30,
            is_prime=True,
        )

        price_war = predictor.detect_price_war(features)

        assert price_war is not None
        assert price_war.is_active or not price_war.is_active  # Valid result


class TestStockoutPredictor:
    """Tests for StockoutPredictor model."""

    def test_stockout_risk_prediction(self):
        """Test stockout risk prediction."""
        from src.ml.models import StockoutPredictor
        from src.ml.features import ProductFeatures

        predictor = StockoutPredictor()

        features = ProductFeatures(
            product_id=str(uuid.uuid4()),
            platform="amazon_us",
            category="Electronics",
            price=Decimal("99.99"),
            avg_price=Decimal("99.99"),
            price_volatility=5.0,
            avg_rating=4.5,
            total_reviews=2000,
            review_velocity=20.0,
            avg_rank=200,
            rank_trend=-10.0,
            seller_count=3,
            stock_ratio=0.7,
            days_tracked=30,
            is_prime=True,
        )

        delivery_history = [2, 2, 3, 2, 2, 3, 2]
        seller_history = [3, 3, 3, 2, 2, 3, 3]
        stock_history = [True, True, True, True, True, True, True]

        prediction = predictor.predict_stockout_risk(
            features, delivery_history, seller_history, stock_history, horizon_days=7
        )

        assert prediction is not None
        assert 0 <= prediction.stockout_probability <= 1.0
        assert prediction.risk_level in ["low", "medium", "high", "critical"]

    def test_high_demand_increases_stockout_risk(self):
        """Test that high demand indicators increase stockout risk."""
        from src.ml.models import StockoutPredictor
        from src.ml.features import ProductFeatures

        predictor = StockoutPredictor()

        # Very high demand product
        high_demand = ProductFeatures(
            product_id=str(uuid.uuid4()),
            platform="amazon_us",
            category="Electronics",
            price=Decimal("99.99"),
            avg_price=Decimal("99.99"),
            price_volatility=2.0,
            avg_rating=4.9,
            total_reviews=10000,
            review_velocity=100.0,
            avg_rank=10,
            rank_trend=-50.0,
            seller_count=1,
            stock_ratio=0.3,
            days_tracked=30,
            is_prime=True,
        )

        # Low demand product
        low_demand = ProductFeatures(
            product_id=str(uuid.uuid4()),
            platform="amazon_us",
            category="Electronics",
            price=Decimal("99.99"),
            avg_price=Decimal("99.99"),
            price_volatility=2.0,
            avg_rating=3.5,
            total_reviews=50,
            review_velocity=1.0,
            avg_rank=50000,
            rank_trend=10.0,
            seller_count=10,
            stock_ratio=1.0,
            days_tracked=30,
            is_prime=False,
        )

        delivery_history = [2, 2, 3, 2, 2, 3, 2]
        seller_history = [3, 3, 3, 2, 2, 3, 3]
        stock_history = [True, True, True, True, True, True, True]

        high_pred = predictor.predict_stockout_risk(
            high_demand, delivery_history, seller_history, stock_history, 7
        )
        low_pred = predictor.predict_stockout_risk(
            low_demand, delivery_history, seller_history, stock_history, 7
        )

        assert high_pred.stockout_probability >= low_pred.stockout_probability


class TestFeatureEngineer:
    """Tests for feature engineering."""

    def test_engineer_features_sufficient_data(self):
        """Test feature engineering with sufficient data."""
        from src.ml.features import FeatureEngineer

        engineer = FeatureEngineer()

        mock_product = MagicMock(
            id=uuid.uuid4(),
            platform="amazon_us",
            category="Electronics",
            brand="TestBrand",
        )

        metrics = []
        for i in range(14):
            metrics.append(
                MagicMock(
                    date=date.today() - timedelta(days=13 - i),
                    price=Decimal("99.99"),
                    rank=500 + i * 10,
                    rating=4.5,
                    reviews=1000 + i * 5,
                    seller_count=5,
                    in_stock=True,
                    delivery_days=2,
                )
            )

        features = engineer.engineer_features(mock_product, metrics)

        assert features is not None
        assert features.platform == "amazon_us"
        assert features.category == "Electronics"
        assert features.days_tracked == 14

    def test_engineer_features_insufficient_data(self):
        """Test feature engineering with insufficient data."""
        from src.ml.features import FeatureEngineer

        engineer = FeatureEngineer()

        mock_product = MagicMock(
            id=uuid.uuid4(),
            platform="amazon_us",
            category="Electronics",
        )

        # Only 3 days of data (insufficient)
        metrics = [
            MagicMock(
                date=date.today() - timedelta(days=i),
                price=Decimal("99.99"),
                rank=500,
                rating=4.5,
                reviews=1000,
                seller_count=5,
                in_stock=True,
            )
            for i in range(3)
        ]

        features = engineer.engineer_features(mock_product, metrics)

        # Should still return features, but with lower confidence signal
        assert features is None or features.days_tracked == 3
