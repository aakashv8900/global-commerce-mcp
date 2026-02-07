"""Intelligence output formatter for human-readable responses."""

from dataclasses import dataclass
from decimal import Decimal

from .engine import ProductIntelligence, TrendingProduct
from .arbitrage import GlobalPriceComparison


class IntelligenceFormatter:
    """Formats intelligence data into readable output."""

    def format_product_analysis(self, intel: ProductIntelligence) -> str:
        """Format product intelligence as a readable report."""
        lines = []

        # Header
        lines.append(f"# Product Analysis: {intel.title[:60]}...")
        lines.append(f"**ASIN:** {intel.asin} | **Platform:** {intel.platform.upper()}")
        lines.append("")

        # Executive Summary
        lines.append("## 📊 Executive Summary")
        lines.append(f"**Overall Score:** {intel.overall_score}/100")
        lines.append(f"**Confidence:** {intel.confidence * 100:.0f}%")
        lines.append("")
        lines.append(f"> {intel.verdict}")
        lines.append("")

        # Key Metrics
        lines.append("## 📈 Key Metrics")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(
            f"| **Est. Monthly Revenue** | ${intel.revenue.estimated_monthly_revenue:,.2f} |"
        )
        lines.append(
            f"| **Est. Daily Sales** | {intel.revenue.estimated_daily_sales:.1f} units |"
        )
        lines.append(f"| **Current Price** | ${intel.current_price:,.2f} |")
        lines.append(f"| **BSR Rank** | #{intel.current_rank:,} |" if intel.current_rank else "| **BSR Rank** | N/A |")
        lines.append(f"| **Reviews** | {intel.current_reviews:,} |")
        lines.append(f"| **Rating** | {intel.current_rating:.1f}⭐ |")
        lines.append("")

        # Scores
        lines.append("## 🎯 Intelligence Scores")
        lines.append(f"| Score | Value | Interpretation |")
        lines.append(f"|-------|-------|----------------|")
        lines.append(
            f"| **Demand** | {intel.demand.score:.0f}/100 | {intel.demand.interpretation[:50]} |"
        )
        lines.append(
            f"| **Competition** | {intel.competition.score:.0f}/100 | {intel.competition.barrier_to_entry} barrier |"
        )
        lines.append(
            f"| **Trend** | {intel.trend.score:+.0f} | {intel.trend.trend_direction} |"
        )
        lines.append(
            f"| **Risk** | {intel.risk.score:.0f}/100 | {intel.risk.risk_level} |"
        )
        lines.append("")

        # Discount Prediction
        if intel.discount_prediction.next_predicted_discount:
            lines.append("## 💰 Discount Prediction")
            lines.append(intel.discount_prediction.interpretation)
            lines.append("")

        # Risk Flags
        if intel.risk.flags:
            lines.append("## ⚠️ Risk Flags")
            for flag in intel.risk.flags:
                lines.append(f"- **{flag.severity.upper()}**: {flag.description}")
            lines.append("")

        # Actionable Insights
        lines.append("## 💡 Actionable Insights")
        for i, insight in enumerate(intel.insights, 1):
            lines.append(f"{i}. {insight}")
        lines.append("")

        # Methodology
        lines.append("---")
        lines.append(f"*Analysis date: {intel.analysis_date} | {intel.revenue.methodology}*")

        return "\n".join(lines)

    def format_trending_products(self, products: list[TrendingProduct], category: str) -> str:
        """Format trending products list."""
        lines = []

        lines.append(f"# 🔥 Trending Products: {category}")
        lines.append("")
        lines.append("| Rank | ASIN | Title | Trend Score | Review Velocity |")
        lines.append("|------|------|-------|-------------|-----------------|")

        for i, product in enumerate(products, 1):
            title_short = product.title[:40] + "..." if len(product.title) > 40 else product.title
            lines.append(
                f"| {i} | {product.asin} | {title_short} | {product.trend_score:+.0f} | {product.review_velocity:.1f}/day |"
            )

        lines.append("")
        lines.append(f"*Showing top {len(products)} trending products*")

        return "\n".join(lines)

    def format_price_comparison(
        self,
        product_title: str,
        prices: dict[str, Decimal],
        arbitrage_opportunities: list[dict],
    ) -> str:
        """Format global price comparison."""
        lines = []

        lines.append(f"# 🌍 Global Price Comparison")
        lines.append(f"**Product:** {product_title}")
        lines.append("")

        lines.append("## Regional Prices")
        lines.append("| Region | Price | Tax-Adjusted |")
        lines.append("|--------|-------|--------------|")

        for region, price in prices.items():
            lines.append(f"| {region} | ${price:,.2f} | ${price * Decimal('1.1'):,.2f} |")

        lines.append("")

        if arbitrage_opportunities:
            lines.append("## 📈 Arbitrage Opportunities")
            for opp in arbitrage_opportunities:
                lines.append(
                    f"- **{opp['from']} → {opp['to']}**: {opp['margin']:.1f}% margin"
                )
            lines.append("")

        return "\n".join(lines)

    def format_global_price_comparison(self, comparison: GlobalPriceComparison) -> str:
        """Format GlobalPriceComparison from arbitrage analyzer."""
        lines = []

        lines.append("# 🌍 Global Price Comparison")
        lines.append(f"**Product:** {comparison.product_title[:60]}...")
        lines.append("")

        # Regional Prices Table
        lines.append("## 💰 Regional Prices")
        lines.append("| Region | Platform | Price | Price (USD) | Tax-Adjusted |")
        lines.append("|--------|----------|-------|-------------|--------------|")

        for rp in comparison.regional_prices:
            currency_symbol = "₹" if rp.currency.value == "INR" else "$" if rp.currency.value == "USD" else rp.currency.value
            stock_emoji = "✅" if rp.in_stock else "❌"
            lines.append(
                f"| {rp.country} | {rp.platform} | {currency_symbol}{rp.price:,.2f} | ${rp.price_usd:,.2f} | ${rp.price_with_tax_usd:,.2f} {stock_emoji} |"
            )

        lines.append("")

        # Price Spread
        lines.append("## 📊 Price Analysis")
        lines.append(f"- **Spread:** {comparison.price_spread_percent:.1f}%")
        if comparison.lowest_price:
            lines.append(f"- **Lowest:** {comparison.lowest_price.platform} ({comparison.lowest_price.country}) at ${comparison.lowest_price.price_usd:,.2f}")
        if comparison.highest_price:
            lines.append(f"- **Highest:** {comparison.highest_price.platform} ({comparison.highest_price.country}) at ${comparison.highest_price.price_usd:,.2f}")
        lines.append("")

        # Arbitrage Opportunities
        if comparison.arbitrage_opportunities:
            lines.append("## 📈 Arbitrage Opportunities")
            for opp in comparison.arbitrage_opportunities:
                emoji = "🔥" if opp.margin_percent >= 30 else "✅" if opp.margin_percent >= 20 else "👍"
                lines.append(f"### {emoji} {opp.buy_from.platform} → {opp.sell_to.platform}")
                lines.append(f"| Detail | Value |")
                lines.append(f"|--------|-------|")
                lines.append(f"| **Buy at** | ${opp.buy_from.price_usd:,.2f} ({opp.buy_from.country}) |")
                lines.append(f"| **Sell at** | ${opp.sell_to.price_with_tax_usd:,.2f} ({opp.sell_to.country}) |")
                lines.append(f"| **Shipping** | ${opp.shipping_cost_usd:,.2f} |")
                lines.append(f"| **Import Tax** | ${opp.import_tax_estimate_usd:,.2f} |")
                lines.append(f"| **Net Margin** | ${opp.net_margin_usd:,.2f} ({opp.margin_percent:.1f}%) |")
                lines.append(f"| **Status** | {'✅ Profitable' if opp.is_profitable else '❌ Not Profitable'} |")
                lines.append(f"\n{opp.notes}")
                lines.append("")
        else:
            lines.append("## 📈 Arbitrage Opportunities")
            lines.append("No profitable arbitrage opportunities found after accounting for shipping and import duties.")
            lines.append("")

        # Recommendation
        lines.append("## 🎯 Recommendation")
        lines.append(comparison.recommendation)
        lines.append("")

        lines.append("---")
        lines.append("*Cross-border arbitrage analysis | Currency rates may fluctuate*")

        return "\n".join(lines)
