"""Cross-border arbitrage detection and analysis."""

from dataclasses import dataclass
from decimal import Decimal

from .currency import (
    Currency,
    CurrencyConverter,
    RegionalPrice,
    calculate_tax_adjusted_price,
    estimate_shipping,
)


@dataclass
class ArbitrageOpportunity:
    """A detected arbitrage opportunity."""
    buy_from: RegionalPrice
    sell_to: RegionalPrice
    price_difference_usd: Decimal
    shipping_cost_usd: Decimal
    import_tax_estimate_usd: Decimal
    net_margin_usd: Decimal
    margin_percent: float
    is_profitable: bool
    notes: str


@dataclass
class GlobalPriceComparison:
    """Comparison of prices across regions."""
    product_title: str
    regional_prices: list[RegionalPrice]
    lowest_price: RegionalPrice
    highest_price: RegionalPrice
    price_spread_percent: float
    arbitrage_opportunities: list[ArbitrageOpportunity]
    recommendation: str


class ArbitrageAnalyzer:
    """Analyzer for cross-border arbitrage opportunities."""

    # Minimum margin to be considered a viable opportunity
    MIN_MARGIN_PERCENT = 15.0

    # Import duty estimates by product category
    IMPORT_DUTY_RATES = {
        "Electronics": Decimal("0.05"),
        "Clothing": Decimal("0.12"),
        "Toys": Decimal("0.03"),
        "Beauty": Decimal("0.08"),
        "Books": Decimal("0.00"),
        "default": Decimal("0.05"),
    }

    def __init__(self):
        self.converter = CurrencyConverter()

    async def analyze_prices(
        self,
        product_title: str,
        regional_prices: list[RegionalPrice],
        category: str = "default",
    ) -> GlobalPriceComparison:
        """Analyze prices across regions for arbitrage opportunities."""
        if len(regional_prices) < 2:
            return GlobalPriceComparison(
                product_title=product_title,
                regional_prices=regional_prices,
                lowest_price=regional_prices[0] if regional_prices else None,
                highest_price=regional_prices[0] if regional_prices else None,
                price_spread_percent=0.0,
                arbitrage_opportunities=[],
                recommendation="Need prices from at least 2 regions for comparison",
            )

        # Sort by USD price
        sorted_prices = sorted(regional_prices, key=lambda p: p.price_usd)
        lowest = sorted_prices[0]
        highest = sorted_prices[-1]

        # Calculate spread
        spread_percent = 0.0
        if lowest.price_usd > 0:
            spread_percent = float(
                (highest.price_usd - lowest.price_usd) / lowest.price_usd * 100
            )

        # Find arbitrage opportunities
        opportunities = await self._find_opportunities(sorted_prices, category)

        # Generate recommendation
        recommendation = self._generate_recommendation(opportunities, spread_percent)

        return GlobalPriceComparison(
            product_title=product_title,
            regional_prices=regional_prices,
            lowest_price=lowest,
            highest_price=highest,
            price_spread_percent=round(spread_percent, 1),
            arbitrage_opportunities=opportunities,
            recommendation=recommendation,
        )

    async def _find_opportunities(
        self,
        sorted_prices: list[RegionalPrice],
        category: str,
    ) -> list[ArbitrageOpportunity]:
        """Find all viable arbitrage opportunities."""
        opportunities = []

        for buy in sorted_prices:
            if not buy.in_stock:
                continue

            for sell in sorted_prices:
                if buy.country == sell.country:
                    continue

                opportunity = await self._calculate_opportunity(buy, sell, category)
                if opportunity.is_profitable:
                    opportunities.append(opportunity)

        # Sort by margin descending
        opportunities.sort(key=lambda o: o.margin_percent, reverse=True)
        return opportunities[:5]  # Return top 5 opportunities

    async def _calculate_opportunity(
        self,
        buy: RegionalPrice,
        sell: RegionalPrice,
        category: str,
    ) -> ArbitrageOpportunity:
        """Calculate arbitrage opportunity between two regions."""
        # Price difference
        price_diff = sell.price_with_tax_usd - buy.price_usd

        # Shipping cost
        shipping = estimate_shipping(buy.country, sell.country)

        # Import duty estimate
        duty_rate = self.IMPORT_DUTY_RATES.get(category, self.IMPORT_DUTY_RATES["default"])
        import_tax = buy.price_usd * duty_rate

        # Net margin
        net_margin = price_diff - shipping - import_tax

        # Margin percent
        margin_percent = 0.0
        if buy.price_usd > 0:
            margin_percent = float(net_margin / buy.price_usd * 100)

        is_profitable = margin_percent >= self.MIN_MARGIN_PERCENT

        notes = self._generate_notes(buy, sell, net_margin, margin_percent)

        return ArbitrageOpportunity(
            buy_from=buy,
            sell_to=sell,
            price_difference_usd=round(price_diff, 2),
            shipping_cost_usd=shipping,
            import_tax_estimate_usd=round(import_tax, 2),
            net_margin_usd=round(net_margin, 2),
            margin_percent=round(margin_percent, 1),
            is_profitable=is_profitable,
            notes=notes,
        )

    def _generate_notes(
        self,
        buy: RegionalPrice,
        sell: RegionalPrice,
        net_margin: Decimal,
        margin_percent: float,
    ) -> str:
        """Generate notes for the opportunity."""
        notes = []

        if margin_percent >= 30:
            notes.append("🔥 High margin opportunity")
        elif margin_percent >= 20:
            notes.append("✅ Good margin")
        elif margin_percent >= 15:
            notes.append("👍 Viable margin")
        else:
            notes.append("⚠️ Low margin")

        if not buy.in_stock:
            notes.append("❌ Out of stock at source")

        if buy.platform != sell.platform:
            notes.append(f"Cross-platform: {buy.platform} → {sell.platform}")

        return " | ".join(notes)

    def _generate_recommendation(
        self,
        opportunities: list[ArbitrageOpportunity],
        spread_percent: float,
    ) -> str:
        """Generate overall recommendation."""
        if not opportunities:
            if spread_percent < 10:
                return "No significant price differences detected. Prices are well-aligned globally."
            return "Price differences exist but shipping/import costs eliminate margins."

        best = opportunities[0]
        return (
            f"Best opportunity: Buy from {best.buy_from.country} ({best.buy_from.platform}) "
            f"at ${best.buy_from.price_usd:.2f}, sell in {best.sell_to.country} "
            f"for {best.margin_percent:.1f}% margin (${best.net_margin_usd:.2f} net profit per unit)"
        )

    async def compare_amazon_flipkart(
        self,
        amazon_price_usd: Decimal,
        flipkart_price_inr: Decimal,
        product_title: str,
        category: str = "default",
    ) -> GlobalPriceComparison:
        """Quick comparison between Amazon US and Flipkart India."""
        # Convert Flipkart price to USD
        flipkart_usd = await self.converter.convert(
            flipkart_price_inr, Currency.INR, Currency.USD
        )

        regional_prices = [
            RegionalPrice(
                platform="Amazon",
                country="US",
                currency=Currency.USD,
                price=amazon_price_usd,
                price_usd=amazon_price_usd,
                price_with_tax_usd=amazon_price_usd * Decimal("1.08"),  # 8% tax
                in_stock=True,
            ),
            RegionalPrice(
                platform="Flipkart",
                country="IN",
                currency=Currency.INR,
                price=flipkart_price_inr,
                price_usd=flipkart_usd,
                price_with_tax_usd=flipkart_usd * Decimal("1.18"),  # 18% GST
                in_stock=True,
            ),
        ]

        return await self.analyze_prices(product_title, regional_prices, category)
