"""ML Model Training Pipeline."""

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import joblib

from src.db.database import async_session_maker
from src.db.repositories import ProductRepository, MetricsRepository
from src.ml.features import FeatureEngineer, ProductFeatures
from src.ml.models import DemandForecaster, PricePredictor, StockoutPredictor

logger = logging.getLogger(__name__)

# Default model storage location
MODEL_DIR = Path(__file__).parent / "trained_models"
MODEL_DIR.mkdir(exist_ok=True)


class TrainingConfig:
    """Configuration for model training."""

    def __init__(
        self,
        min_samples: int = 100,
        lookback_days: int = 90,
        validation_split: float = 0.2,
        model_dir: Path = MODEL_DIR,
    ):
        self.min_samples = min_samples
        self.lookback_days = lookback_days
        self.validation_split = validation_split
        self.model_dir = model_dir


class ModelTrainer:
    """
    Orchestrates training of all ML models.

    Handles data collection, feature engineering, training,
    validation, and model persistence.
    """

    def __init__(self, config: Optional[TrainingConfig] = None):
        self.config = config or TrainingConfig()
        self.feature_engineer = FeatureEngineer()

    async def collect_training_data(self) -> list[ProductFeatures]:
        """Collect training data from database."""
        features_list = []

        async with async_session_maker() as session:
            product_repo = ProductRepository(session)
            metrics_repo = MetricsRepository(session)

            # Get all products with sufficient data
            products = await product_repo.get_all()

            for product in products:
                # Get historical metrics
                metrics = await metrics_repo.get_last_n_days(
                    product.id, self.config.lookback_days
                )

                if len(metrics) >= 7:  # Minimum 7 days of data
                    features = self.feature_engineer.engineer_features(product, metrics)
                    if features:
                        features_list.append(features)

        logger.info(f"Collected {len(features_list)} training samples")
        return features_list

    async def train_demand_model(self, features_list: list[ProductFeatures]) -> dict:
        """Train demand forecasting model."""
        if len(features_list) < self.config.min_samples:
            logger.warning(
                f"Insufficient samples ({len(features_list)}) for demand model training"
            )
            return {"status": "skipped", "reason": "insufficient_data"}

        forecaster = DemandForecaster()

        # Prepare training data
        X = []
        y = []

        for features in features_list:
            X.append(self._features_to_array(features))
            # Use review velocity as proxy for demand
            y.append(features.review_velocity)

        # Train model
        try:
            forecaster.train(X, y)

            # Save model
            model_path = self.config.model_dir / "demand_forecaster.joblib"
            joblib.dump(forecaster, model_path)

            logger.info(f"Demand model trained and saved to {model_path}")
            return {
                "status": "success",
                "samples": len(X),
                "model_path": str(model_path),
            }

        except Exception as e:
            logger.error(f"Demand model training failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def train_price_model(self, features_list: list[ProductFeatures]) -> dict:
        """Train price prediction model."""
        if len(features_list) < self.config.min_samples:
            logger.warning("Insufficient samples for price model training")
            return {"status": "skipped", "reason": "insufficient_data"}

        predictor = PricePredictor()

        # Prepare training data
        X = []
        y = []

        for features in features_list:
            X.append(self._features_to_array(features))
            y.append(float(features.price_volatility))

        try:
            predictor.train(X, y)

            model_path = self.config.model_dir / "price_predictor.joblib"
            joblib.dump(predictor, model_path)

            logger.info(f"Price model trained and saved to {model_path}")
            return {
                "status": "success",
                "samples": len(X),
                "model_path": str(model_path),
            }

        except Exception as e:
            logger.error(f"Price model training failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def train_stockout_model(self, features_list: list[ProductFeatures]) -> dict:
        """Train stockout prediction model."""
        if len(features_list) < self.config.min_samples:
            logger.warning("Insufficient samples for stockout model training")
            return {"status": "skipped", "reason": "insufficient_data"}

        predictor = StockoutPredictor()

        # Prepare training data
        X = []
        y = []

        for features in features_list:
            X.append(self._features_to_array(features))
            # Use stock ratio as target (inverted for stockout probability)
            y.append(1.0 - features.stock_ratio)

        try:
            predictor.train(X, y)

            model_path = self.config.model_dir / "stockout_predictor.joblib"
            joblib.dump(predictor, model_path)

            logger.info(f"Stockout model trained and saved to {model_path}")
            return {
                "status": "success",
                "samples": len(X),
                "model_path": str(model_path),
            }

        except Exception as e:
            logger.error(f"Stockout model training failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def train_all_models(self) -> dict:
        """Train all models."""
        logger.info("Starting full model training pipeline")

        # Collect data
        features_list = await self.collect_training_data()

        if len(features_list) == 0:
            return {
                "status": "failed",
                "reason": "no_training_data",
                "models": {},
            }

        # Train each model
        results = {
            "demand": await self.train_demand_model(features_list),
            "price": await self.train_price_model(features_list),
            "stockout": await self.train_stockout_model(features_list),
        }

        # Summary
        successful = sum(1 for r in results.values() if r.get("status") == "success")

        return {
            "status": "complete",
            "total_samples": len(features_list),
            "models_trained": successful,
            "models": results,
        }

    def _features_to_array(self, features: ProductFeatures) -> list:
        """Convert ProductFeatures to array for training."""
        return [
            float(features.price),
            float(features.avg_price),
            features.price_volatility,
            features.avg_rating,
            features.total_reviews,
            features.review_velocity,
            features.avg_rank or 0,
            features.rank_trend,
            features.seller_count,
            features.stock_ratio,
            features.days_tracked,
            1.0 if features.is_prime else 0.0,
        ]


async def run_training_job():
    """Entry point for scheduled training job."""
    trainer = ModelTrainer()
    results = await trainer.train_all_models()
    logger.info(f"Training job completed: {results}")
    return results
