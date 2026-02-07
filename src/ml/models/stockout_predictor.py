"""Stockout prediction model."""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional
import numpy as np

from src.ml.features import FeatureEngineer, ProductFeatures


@dataclass
class StockoutPrediction:
    """Stockout risk prediction result."""
    product_id: str
    prediction_date: date
    horizon_days: int

    # Risk assessment
    stockout_probability: float  # 0-1
    risk_level: str  # "low", "medium", "high", "critical"
    estimated_days_until_stockout: int | None

    # Signals detected
    signals: list[str]

    # Recommendations
    recommendation: str
    alternative_products_suggested: bool


@dataclass
class SupplyConstraint:
    """Detected supply constraint."""
    product_id: str
    constraint_type: str  # "shipping_delay", "low_stock", "limited_sellers", "seasonal"
    severity: str
    evidence: list[str]
    expected_resolution_days: int | None


class StockoutPredictor:
    """
    Predicts stockout probability and detects supply constraints.

    Uses seller count, delivery time, and availability patterns
    to predict future stock issues.
    """

    def __init__(self):
        self.feature_engineer = FeatureEngineer()

    def predict_stockout_risk(
        self,
        features: ProductFeatures,
        delivery_days_history: list[int],
        seller_count_history: list[int],
        in_stock_history: list[bool],
        horizon_days: int = 7,
    ) -> StockoutPrediction:
        """
        Predict stockout probability for a product.

        Args:
            features: Product features
            delivery_days_history: Recent delivery time data
            seller_count_history: Recent seller count data
            in_stock_history: Recent availability data
            horizon_days: Prediction horizon

        Returns:
            StockoutPrediction with risk assessment
        """
        signals = []
        risk_score = 0.0

        # Signal 1: Delivery time increasing
        if len(delivery_days_history) >= 3:
            recent = np.mean(delivery_days_history[:3])
            older = np.mean(delivery_days_history[3:6]) if len(delivery_days_history) >= 6 else recent
            if recent > older * 1.3:
                signals.append("📦 Delivery times increasing")
                risk_score += 0.2
            if recent > 7:
                signals.append("⚠️ Extended delivery times (>7 days)")
                risk_score += 0.15

        # Signal 2: Seller count decreasing
        if len(seller_count_history) >= 3:
            recent_sellers = np.mean(seller_count_history[:3])
            older_sellers = np.mean(seller_count_history[3:6]) if len(seller_count_history) >= 6 else recent_sellers
            if recent_sellers < older_sellers * 0.7:
                signals.append("👥 Seller count declining")
                risk_score += 0.25
            if recent_sellers <= 1:
                signals.append("🔴 Single seller remaining")
                risk_score += 0.3

        # Signal 3: Stock availability issues
        if in_stock_history:
            out_of_stock_days = sum(1 for s in in_stock_history[:14] if not s)
            if out_of_stock_days > 0:
                signals.append(f"📊 Out of stock {out_of_stock_days} of last 14 days")
                risk_score += 0.1 * out_of_stock_days

        # Signal 4: High demand indicators
        if features.rank_improvement_7d < -1000:  # Rank improving rapidly
            signals.append("🔥 Rapid demand increase")
            risk_score += 0.15

        if features.review_velocity_7d > 10:  # High review velocity
            signals.append("📈 High review velocity")
            risk_score += 0.1

        # Signal 5: Price increases (often precede stockouts)
        if features.price_trend_7d > 0.5:
            signals.append("💰 Prices trending up")
            risk_score += 0.1

        # Normalize risk score
        stockout_probability = min(1.0, risk_score)

        # Determine risk level
        if stockout_probability > 0.7:
            risk_level = "critical"
        elif stockout_probability > 0.5:
            risk_level = "high"
        elif stockout_probability > 0.25:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Estimate days until stockout
        if stockout_probability > 0.7:
            estimated_days = 3
        elif stockout_probability > 0.5:
            estimated_days = 7
        elif stockout_probability > 0.25:
            estimated_days = 14
        else:
            estimated_days = None

        # Generate recommendation
        recommendation = self._generate_recommendation(risk_level, signals)

        return StockoutPrediction(
            product_id=features.product_id,
            prediction_date=date.today(),
            horizon_days=horizon_days,
            stockout_probability=stockout_probability,
            risk_level=risk_level,
            estimated_days_until_stockout=estimated_days,
            signals=signals,
            recommendation=recommendation,
            alternative_products_suggested=risk_level in ["high", "critical"],
        )

    def detect_supply_constraints(
        self,
        products_features: list[ProductFeatures],
        products_delivery_history: list[list[int]],
        products_seller_history: list[list[int]],
    ) -> list[SupplyConstraint]:
        """
        Detect supply constraints across multiple products.

        Useful for category-level supply chain analysis.
        """
        constraints = []

        for i, features in enumerate(products_features):
            delivery_history = products_delivery_history[i] if i < len(products_delivery_history) else []
            seller_history = products_seller_history[i] if i < len(products_seller_history) else []

            constraint = self._detect_single_constraint(
                features, delivery_history, seller_history
            )
            if constraint:
                constraints.append(constraint)

        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        constraints.sort(key=lambda c: severity_order.get(c.severity, 4))

        return constraints

    def _detect_single_constraint(
        self,
        features: ProductFeatures,
        delivery_history: list[int],
        seller_history: list[int],
    ) -> SupplyConstraint | None:
        """Detect constraint for a single product."""
        evidence = []

        # Check for shipping delays
        if delivery_history:
            avg_delivery = np.mean(delivery_history[:7]) if len(delivery_history) >= 7 else np.mean(delivery_history)
            if avg_delivery > 10:
                evidence.append(f"Average delivery: {avg_delivery:.0f} days")
                return SupplyConstraint(
                    product_id=features.product_id,
                    constraint_type="shipping_delay",
                    severity="high" if avg_delivery > 14 else "medium",
                    evidence=evidence,
                    expected_resolution_days=None,
                )

        # Check for limited sellers
        if seller_history:
            current_sellers = seller_history[0]
            if current_sellers <= 1:
                evidence.append(f"Only {current_sellers} seller(s)")
                return SupplyConstraint(
                    product_id=features.product_id,
                    constraint_type="limited_sellers",
                    severity="high",
                    evidence=evidence,
                    expected_resolution_days=None,
                )

        # Check for seasonal patterns
        if features.day_of_month >= 25 or features.day_of_month <= 5:
            if features.rank_improvement_7d < -500:
                evidence.append("Month-end demand surge")
                return SupplyConstraint(
                    product_id=features.product_id,
                    constraint_type="seasonal",
                    severity="low",
                    evidence=evidence,
                    expected_resolution_days=7,
                )

        return None

    def _generate_recommendation(
        self,
        risk_level: str,
        signals: list[str],
    ) -> str:
        """Generate actionable recommendation based on risk."""
        if risk_level == "critical":
            return "🚨 CRITICAL: Stockout imminent. Purchase immediately or identify alternatives."
        elif risk_level == "high":
            return "⚠️ HIGH RISK: Stock likely to run out soon. Consider purchasing within 3 days."
        elif risk_level == "medium":
            return "🔶 MODERATE RISK: Monitor stock levels. Set alerts for availability changes."
        else:
            return "✅ LOW RISK: Stock levels appear stable. No immediate action needed."
