"""ML model inference pipeline."""

from dataclasses import dataclass
from typing import Optional

from src.db.models import Product, DailyMetric
from src.ml.features import FeatureEngineer, ProductFeatures
from src.ml.models import (
    DemandForecaster,
    DemandForecast,
    PricePredictor,
    PricePrediction,
    StockoutPredictor,
    StockoutPrediction,
)


@dataclass
class InferenceResult:
    """Combined inference result from all models."""
    demand: DemandForecast | None
    price: PricePrediction | None
    stockout: StockoutPrediction | None
    confidence: float


class ModelInference:
    """
    Unified inference pipeline for all ML models.

    Manages model loading, feature engineering, and prediction.
    """

    def __init__(self):
        self.feature_engineer = FeatureEngineer()
        self.demand_forecaster = DemandForecaster()
        self.price_predictor = PricePredictor()
        self.stockout_predictor = StockoutPredictor()

    def predict_all(
        self,
        product: Product,
        metrics: list[DailyMetric],
        horizon_days: int = 7,
    ) -> InferenceResult:
        """
        Run all prediction models for a product.

        Args:
            product: Product entity
            metrics: Historical metrics (at least 7 days)
            horizon_days: Forecast horizon

        Returns:
            InferenceResult with predictions from all models
        """
        # Engineer features
        features = self.feature_engineer.engineer_features(product, metrics)

        if not features:
            return InferenceResult(
                demand=None,
                price=None,
                stockout=None,
                confidence=0.0,
            )

        # Run predictions
        demand = self.demand_forecaster.predict(features, horizon_days)
        price = self.price_predictor.predict_price_trajectory(features, horizon_days)

        # Extract history for stockout prediction
        delivery_history = [m.delivery_days or 3 for m in metrics[:14]]
        seller_history = [m.seller_count for m in metrics[:14]]
        stock_history = [m.in_stock for m in metrics[:14]]

        stockout = self.stockout_predictor.predict_stockout_risk(
            features, delivery_history, seller_history, stock_history, horizon_days
        )

        # Calculate combined confidence
        confidence = (
            demand.confidence_score +
            price.confidence_score +
            (100 - stockout.stockout_probability * 100)
        ) / 3

        return InferenceResult(
            demand=demand,
            price=price,
            stockout=stockout,
            confidence=confidence,
        )

    def predict_demand(
        self,
        product: Product,
        metrics: list[DailyMetric],
        horizon_days: int = 7,
    ) -> DemandForecast | None:
        """Run demand forecast only."""
        features = self.feature_engineer.engineer_features(product, metrics)
        if not features:
            return None
        return self.demand_forecaster.predict(features, horizon_days)

    def predict_price(
        self,
        product: Product,
        metrics: list[DailyMetric],
        horizon_days: int = 30,
    ) -> PricePrediction | None:
        """Run price prediction only."""
        features = self.feature_engineer.engineer_features(product, metrics)
        if not features:
            return None
        return self.price_predictor.predict_price_trajectory(features, horizon_days)

    def predict_stockout(
        self,
        product: Product,
        metrics: list[DailyMetric],
        horizon_days: int = 7,
    ) -> StockoutPrediction | None:
        """Run stockout prediction only."""
        features = self.feature_engineer.engineer_features(product, metrics)
        if not features:
            return None

        delivery_history = [m.delivery_days or 3 for m in metrics[:14]]
        seller_history = [m.seller_count for m in metrics[:14]]
        stock_history = [m.in_stock for m in metrics[:14]]

        return self.stockout_predictor.predict_stockout_risk(
            features, delivery_history, seller_history, stock_history, horizon_days
        )
