"""Demand forecasting model using gradient boosting."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
import json
import os

import numpy as np

from src.ml.features import FeatureEngineer, ProductFeatures


@dataclass
class DemandForecast:
    """Demand forecast result."""
    product_id: str
    forecast_date: date
    horizon_days: int

    # Predictions
    predicted_daily_sales: list[float]
    predicted_total_sales: float
    confidence_lower: list[float]
    confidence_upper: list[float]

    # Insights
    trend: str  # "increasing", "stable", "decreasing"
    seasonality_detected: bool
    peak_day: int  # day of week with highest predicted sales
    confidence_score: float  # 0-100


@dataclass
class ModelMetrics:
    """Model evaluation metrics."""
    mae: float
    mape: float
    rmse: float
    r2: float


class DemandForecaster:
    """
    Demand forecasting using LightGBM gradient boosting.

    Predicts daily sales for 7-day and 30-day horizons.
    """

    def __init__(self, model_path: str | None = None):
        self.model = None
        self.model_path = model_path or "models/demand_forecaster.json"
        self.feature_engineer = FeatureEngineer()
        self._load_model()

    def _load_model(self) -> None:
        """Load trained model if exists."""
        if os.path.exists(self.model_path):
            try:
                import lightgbm as lgb
                self.model = lgb.Booster(model_file=self.model_path)
            except Exception:
                self.model = None

    def train(
        self,
        features_list: list[ProductFeatures],
        targets: list[float],
        validation_split: float = 0.2,
    ) -> ModelMetrics:
        """
        Train the demand forecasting model.

        Args:
            features_list: List of ProductFeatures for each training sample
            targets: List of actual daily sales values
            validation_split: Fraction for validation

        Returns:
            ModelMetrics with evaluation results
        """
        import lightgbm as lgb
        from sklearn.model_selection import train_test_split

        # Convert features to arrays
        X = np.array([
            self.feature_engineer.features_to_array(f)
            for f in features_list
        ])
        y = np.array(targets)

        # Split data
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=validation_split, random_state=42
        )

        # Create datasets
        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

        # Model parameters
        params = {
            "objective": "regression",
            "metric": ["mae", "rmse"],
            "boosting_type": "gbdt",
            "num_leaves": 31,
            "learning_rate": 0.05,
            "feature_fraction": 0.9,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "verbose": -1,
        }

        # Train
        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=500,
            valid_sets=[val_data],
            callbacks=[lgb.early_stopping(50)],
        )

        # Save model
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        self.model.save_model(self.model_path)

        # Evaluate
        return self.evaluate(X_val, y_val)

    def predict(
        self,
        features: ProductFeatures,
        horizon_days: int = 7,
    ) -> DemandForecast:
        """
        Predict demand for a product.

        Args:
            features: Engineered features for the product
            horizon_days: Number of days to forecast (7 or 30)

        Returns:
            DemandForecast with predictions and confidence intervals
        """
        if self.model is None:
            # Return heuristic prediction if no model
            return self._heuristic_prediction(features, horizon_days)

        feature_array = self.feature_engineer.features_to_array(features)

        # Generate predictions for each day
        predictions = []
        confidence_lower = []
        confidence_upper = []

        base_prediction = float(self.model.predict([feature_array])[0])

        for day in range(horizon_days):
            # Adjust for day of week seasonality
            adjusted_day = (features.day_of_week + day) % 7
            weekend_factor = 1.2 if adjusted_day >= 5 else 1.0

            daily_pred = base_prediction * weekend_factor
            predictions.append(max(0, daily_pred))

            # Confidence intervals (wider as we go further out)
            uncertainty = 0.1 + (day * 0.02)
            confidence_lower.append(max(0, daily_pred * (1 - uncertainty)))
            confidence_upper.append(daily_pred * (1 + uncertainty))

        # Determine trend
        if len(predictions) >= 3:
            early_avg = np.mean(predictions[:3])
            late_avg = np.mean(predictions[-3:])
            if late_avg > early_avg * 1.1:
                trend = "increasing"
            elif late_avg < early_avg * 0.9:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"

        # Find peak day
        peak_day = int(np.argmax(predictions) % 7)

        return DemandForecast(
            product_id=features.product_id,
            forecast_date=date.today(),
            horizon_days=horizon_days,
            predicted_daily_sales=predictions,
            predicted_total_sales=sum(predictions),
            confidence_lower=confidence_lower,
            confidence_upper=confidence_upper,
            trend=trend,
            seasonality_detected=features.is_weekend or abs(features.price_trend_7d) > 0.5,
            peak_day=peak_day,
            confidence_score=self._calculate_confidence(features),
        )

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> ModelMetrics:
        """Evaluate model on test data."""
        if self.model is None:
            return ModelMetrics(mae=0, mape=0, rmse=0, r2=0)

        predictions = self.model.predict(X)

        mae = float(np.mean(np.abs(predictions - y)))
        mape = float(np.mean(np.abs((predictions - y) / (y + 1e-8))) * 100)
        rmse = float(np.sqrt(np.mean((predictions - y) ** 2)))

        ss_res = np.sum((y - predictions) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2 = float(1 - (ss_res / (ss_tot + 1e-8)))

        return ModelMetrics(mae=mae, mape=mape, rmse=rmse, r2=r2)

    def _heuristic_prediction(
        self,
        features: ProductFeatures,
        horizon_days: int,
    ) -> DemandForecast:
        """Fallback heuristic prediction when no model is available."""
        # Estimate base daily sales from review velocity
        # Assumption: 2-5% of buyers leave reviews
        review_to_sales_ratio = 25  # 1 review = ~25 sales
        base_daily_sales = features.review_velocity_7d * review_to_sales_ratio

        # Adjust for rank
        if features.current_rank > 0:
            if features.current_rank < 1000:
                base_daily_sales *= 1.5
            elif features.current_rank > 100000:
                base_daily_sales *= 0.5

        predictions = []
        confidence_lower = []
        confidence_upper = []

        for day in range(horizon_days):
            adjusted_day = (features.day_of_week + day) % 7
            weekend_factor = 1.15 if adjusted_day >= 5 else 1.0
            daily_pred = max(1, base_daily_sales * weekend_factor)

            predictions.append(daily_pred)
            confidence_lower.append(daily_pred * 0.6)
            confidence_upper.append(daily_pred * 1.5)

        return DemandForecast(
            product_id=features.product_id,
            forecast_date=date.today(),
            horizon_days=horizon_days,
            predicted_daily_sales=predictions,
            predicted_total_sales=sum(predictions),
            confidence_lower=confidence_lower,
            confidence_upper=confidence_upper,
            trend="stable",
            seasonality_detected=False,
            peak_day=6,  # Saturday default
            confidence_score=40.0,  # Low confidence for heuristic
        )

    def _calculate_confidence(self, features: ProductFeatures) -> float:
        """Calculate prediction confidence based on data quality."""
        confidence = 50.0

        # More data = higher confidence
        if features.current_reviews > 1000:
            confidence += 20
        elif features.current_reviews > 100:
            confidence += 10

        # Low price variance = more predictable
        if features.price_std_7d < features.price_mean_7d * 0.1:
            confidence += 10

        # Stable rank = more reliable
        if features.rank_std_7d < features.rank_mean_7d * 0.2:
            confidence += 10

        # Consistent review velocity
        if features.review_velocity_7d > 0 and abs(features.review_acceleration) < 1:
            confidence += 10

        return min(95.0, confidence)
