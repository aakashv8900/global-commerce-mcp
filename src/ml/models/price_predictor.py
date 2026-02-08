"""Price prediction and optimization model."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
import numpy as np

from src.ml.features import FeatureEngineer, ProductFeatures


@dataclass
class PricePrediction:
    """Price trajectory prediction result."""
    product_id: str
    prediction_date: date
    horizon_days: int

    # Current state
    current_price: float
    current_discount: float

    # Predictions
    predicted_prices: list[float]
    confidence_lower: list[float]
    confidence_upper: list[float]

    # Analysis
    expected_price_change: float  # % change
    probability_price_drop: float  # 0-1
    optimal_buy_window: tuple[int, int]  # (start_day, end_day)
    price_volatility: str  # "low", "medium", "high"

    # Recommendations
    recommendation: str
    confidence_score: float


@dataclass
class PriceWarAlert:
    """Price war detection result."""
    is_price_war: bool
    severity: str  # "mild", "moderate", "severe"
    competitors_involved: int
    price_drop_velocity: float  # % per day
    estimated_floor_price: float
    recommendation: str


class PricePredictor:
    """
    Predicts price trajectories and detects pricing patterns.

    Uses historical price data to forecast future prices and
    identify optimal buying windows.
    """

    def __init__(self):
        self.feature_engineer = FeatureEngineer()

    def predict_price_trajectory(
        self,
        features: ProductFeatures,
        horizon_days: int = 30,
    ) -> PricePrediction:
        """
        Predict future price trajectory.

        Args:
            features: Engineered features for the product
            horizon_days: Number of days to predict

        Returns:
            PricePrediction with trajectory and analysis
        """
        current_price = features.current_price
        price_trend = features.price_trend_7d
        price_volatility = features.price_std_7d / (features.price_mean_7d + 1e-8)

        # Classify volatility
        if price_volatility < 0.05:
            volatility_class = "low"
        elif price_volatility < 0.15:
            volatility_class = "medium"
        else:
            volatility_class = "high"

        # Generate price predictions
        predictions = []
        confidence_lower = []
        confidence_upper = []

        for day in range(horizon_days):
            # Base trend extrapolation
            trend_effect = price_trend * day

            # Reversion to mean
            mean_reversion = (features.price_mean_7d - current_price) * 0.05 * day

            # Seasonality (month-end discounts)
            future_day = (features.day_of_month + day) % 30
            if future_day >= 25 or future_day <= 5:
                seasonality = -current_price * 0.05  # 5% month-end discount
            else:
                seasonality = 0

            predicted_price = current_price + trend_effect + mean_reversion + seasonality
            predicted_price = max(features.price_min_30d * 0.9, predicted_price)  # Floor

            predictions.append(predicted_price)

            # Confidence intervals widen over time
            uncertainty = price_volatility * np.sqrt(day + 1) * current_price
            confidence_lower.append(max(0, predicted_price - uncertainty * 1.96))
            confidence_upper.append(predicted_price + uncertainty * 1.96)

        # Calculate expected change
        expected_change = ((predictions[-1] - current_price) / current_price) * 100

        # Probability of price drop
        drops = sum(1 for p in predictions if p < current_price * 0.95)
        prob_drop = drops / horizon_days

        # Find optimal buy window (lowest predicted prices)
        min_idx = int(np.argmin(predictions))
        window_start = max(0, min_idx - 2)
        window_end = min(horizon_days - 1, min_idx + 2)

        # Generate recommendation
        recommendation = self._generate_recommendation(
            expected_change, prob_drop, volatility_class, features.discount_frequency
        )

        # Calculate confidence
        confidence = self._calculate_confidence(features, volatility_class)

        return PricePrediction(
            product_id=features.product_id,
            prediction_date=date.today(),
            horizon_days=horizon_days,
            current_price=current_price,
            current_discount=features.discount_frequency * 100,
            predicted_prices=predictions,
            confidence_lower=confidence_lower,
            confidence_upper=confidence_upper,
            expected_price_change=expected_change,
            probability_price_drop=prob_drop,
            optimal_buy_window=(window_start, window_end),
            price_volatility=volatility_class,
            recommendation=recommendation,
            confidence_score=confidence,
        )

    def recommend_price(
        self,
        features: ProductFeatures,
        target_margin_percent: float = 20.0,
        cost_price: float | None = None,
    ) -> dict:
        """
        Recommend optimal pricing strategy.

        Args:
            features: Product features
            target_margin_percent: Desired profit margin
            cost_price: Product cost (if known)

        Returns:
            Dictionary with pricing recommendations
        """
        current_price = features.current_price

        # Estimate competitive price range
        price_min = features.price_min_30d
        price_max = features.price_max_30d
        price_mean = features.price_mean_7d

        recommendations = {
            "current_price": current_price,
            "competitive_range": {
                "min": price_min,
                "max": price_max,
                "mean": price_mean,
            },
            "strategies": [],
        }

        # Premium strategy
        if features.current_rating >= 4.5 and features.current_reviews > 500:
            premium_price = price_mean * 1.1
            recommendations["strategies"].append({
                "name": "Premium Positioning",
                "price": premium_price,
                "rationale": "Strong ratings and reviews support premium pricing",
            })

        # Competitive strategy
        competitive_price = price_mean * 0.95
        recommendations["strategies"].append({
            "name": "Competitive",
            "price": competitive_price,
            "rationale": "Slightly below market average for increased velocity",
        })

        # Value strategy
        if features.current_rank > 50000:
            value_price = price_min * 1.05
            recommendations["strategies"].append({
                "name": "Value/Volume",
                "price": value_price,
                "rationale": "Low price to improve rank and visibility",
            })

        # If cost is known, add margin-based recommendation
        if cost_price:
            margin_price = cost_price * (1 + target_margin_percent / 100)
            recommendations["margin_based_price"] = margin_price
            recommendations["current_margin"] = ((current_price - cost_price) / cost_price) * 100

        return recommendations

    def detect_price_war(
        self,
        price_history: list[float],
        seller_count_history: list[int],
    ) -> PriceWarAlert:
        """
        Detect if a price war is occurring.

        Args:
            price_history: Recent price history (newest first)
            seller_count_history: Seller count history (same order)

        Returns:
            PriceWarAlert with detection results
        """
        if len(price_history) < 7:
            return PriceWarAlert(
                is_price_war=False,
                severity="none",
                competitors_involved=0,
                price_drop_velocity=0,
                estimated_floor_price=price_history[0] if price_history else 0,
                recommendation="Insufficient data for analysis",
            )

        # Calculate price drop velocity
        recent_prices = price_history[:7]
        price_changes = [
            (recent_prices[i] - recent_prices[i + 1]) / recent_prices[i + 1] * 100
            for i in range(len(recent_prices) - 1)
        ]
        avg_daily_drop = np.mean(price_changes)

        # Check seller count changes
        recent_sellers = seller_count_history[:7]
        seller_increase = recent_sellers[0] - recent_sellers[-1] if len(recent_sellers) > 1 else 0

        # Determine if price war
        is_price_war = avg_daily_drop < -1.0 or (avg_daily_drop < -0.5 and seller_increase > 2)

        # Classify severity
        if avg_daily_drop < -3.0:
            severity = "severe"
        elif avg_daily_drop < -1.5:
            severity = "moderate"
        elif is_price_war:
            severity = "mild"
        else:
            severity = "none"

        # Estimate floor price
        min_observed = min(price_history)
        estimated_floor = min_observed * 0.95

        # Generate recommendation
        if severity == "severe":
            recommendation = "⚠️ Severe price war detected. Consider pausing sales or finding alternative products."
        elif severity == "moderate":
            recommendation = "🔶 Moderate price competition. Monitor closely and set floor price alerts."
        elif is_price_war:
            recommendation = "📊 Mild price pressure detected. Track competitor pricing daily."
        else:
            recommendation = "✅ No significant price war detected. Market conditions stable."

        return PriceWarAlert(
            is_price_war=is_price_war,
            severity=severity,
            competitors_involved=max(0, seller_increase),
            price_drop_velocity=avg_daily_drop,
            estimated_floor_price=estimated_floor,
            recommendation=recommendation,
        )

    def _generate_recommendation(
        self,
        expected_change: float,
        prob_drop: float,
        volatility: str,
        discount_frequency: float,
    ) -> str:
        """Generate actionable price recommendation."""
        if prob_drop > 0.6 and expected_change < -5:
            return "🔴 HIGH probability of significant price drop. Wait before purchasing."
        elif prob_drop > 0.4:
            return "🟡 Moderate chance of price decrease. Consider setting a price alert."
        elif expected_change > 5:
            return "🟢 Prices likely to increase. Good time to buy if needed."
        elif volatility == "high":
            return "📊 High price volatility. Monitor for flash sales and deals."
        elif discount_frequency > 0.3:
            return "💰 Frequent discounts on this product. Wait for next sale cycle."
        else:
            return "✅ Stable pricing expected. Current price is representative of market."

    def _calculate_confidence(
        self,
        features: ProductFeatures,
        volatility: str,
    ) -> float:
        """Calculate prediction confidence."""
        confidence = 50.0

        # Low volatility = higher confidence
        if volatility == "low":
            confidence += 25
        elif volatility == "medium":
            confidence += 10

        # More data points = higher confidence
        if features.current_reviews > 1000:
            confidence += 10

        # Consistent pricing history
        if features.price_std_7d < 5:
            confidence += 10

        return min(90.0, confidence)
