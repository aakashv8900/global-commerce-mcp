"""Currency conversion and pricing utilities."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
import httpx
from functools import lru_cache


class Currency(str, Enum):
    """Supported currencies."""
    USD = "USD"
    INR = "INR"
    GBP = "GBP"
    EUR = "EUR"
    JPY = "JPY"


@dataclass
class ConversionRate:
    """Currency conversion rate."""
    from_currency: Currency
    to_currency: Currency
    rate: Decimal
    source: str


# Fallback exchange rates (updated manually as backup)
FALLBACK_RATES = {
    ("USD", "INR"): Decimal("83.00"),
    ("INR", "USD"): Decimal("0.012"),
    ("USD", "GBP"): Decimal("0.79"),
    ("GBP", "USD"): Decimal("1.27"),
    ("USD", "EUR"): Decimal("0.92"),
    ("EUR", "USD"): Decimal("1.09"),
    ("USD", "JPY"): Decimal("150.00"),
    ("JPY", "USD"): Decimal("0.0067"),
}

# Tax rates by country (estimated)
TAX_RATES = {
    "US": Decimal("0.08"),      # Average US sales tax
    "IN": Decimal("0.18"),      # India GST
    "UK": Decimal("0.20"),      # UK VAT
    "DE": Decimal("0.19"),      # Germany VAT
    "JP": Decimal("0.10"),      # Japan consumption tax
}

# Shipping cost estimates (USD)
SHIPPING_ESTIMATES = {
    ("US", "IN"): Decimal("25.00"),
    ("IN", "US"): Decimal("30.00"),
    ("US", "UK"): Decimal("20.00"),
    ("UK", "US"): Decimal("20.00"),
    ("US", "DE"): Decimal("22.00"),
    ("DE", "US"): Decimal("22.00"),
}


class CurrencyConverter:
    """Currency conversion service."""

    # Free exchange rate API
    API_URL = "https://api.exchangerate-api.com/v4/latest"

    def __init__(self):
        self._cache: dict[str, Decimal] = {}

    async def get_rate(self, from_currency: Currency, to_currency: Currency) -> ConversionRate:
        """Get conversion rate between two currencies."""
        if from_currency == to_currency:
            return ConversionRate(from_currency, to_currency, Decimal("1.0"), "identity")

        cache_key = f"{from_currency.value}_{to_currency.value}"
        
        if cache_key in self._cache:
            return ConversionRate(
                from_currency, to_currency, self._cache[cache_key], "cache"
            )

        # Try to fetch live rate
        try:
            rate = await self._fetch_live_rate(from_currency, to_currency)
            self._cache[cache_key] = rate
            return ConversionRate(from_currency, to_currency, rate, "api")
        except Exception:
            # Fall back to static rates
            fallback_key = (from_currency.value, to_currency.value)
            if fallback_key in FALLBACK_RATES:
                return ConversionRate(
                    from_currency, to_currency, FALLBACK_RATES[fallback_key], "fallback"
                )
            
            # Last resort: calculate via USD
            if from_currency != Currency.USD and to_currency != Currency.USD:
                to_usd = FALLBACK_RATES.get((from_currency.value, "USD"), Decimal("1"))
                from_usd = FALLBACK_RATES.get(("USD", to_currency.value), Decimal("1"))
                rate = to_usd * from_usd
                return ConversionRate(from_currency, to_currency, rate, "fallback_calculated")

        return ConversionRate(from_currency, to_currency, Decimal("1.0"), "unknown")

    async def _fetch_live_rate(self, from_currency: Currency, to_currency: Currency) -> Decimal:
        """Fetch live exchange rate from API."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{self.API_URL}/{from_currency.value}")
            response.raise_for_status()
            data = response.json()
            rate = data["rates"].get(to_currency.value)
            if rate:
                return Decimal(str(rate))
            raise ValueError(f"Rate not found for {to_currency.value}")

    async def convert(
        self,
        amount: Decimal,
        from_currency: Currency,
        to_currency: Currency,
    ) -> Decimal:
        """Convert amount from one currency to another."""
        rate = await self.get_rate(from_currency, to_currency)
        return round(amount * rate.rate, 2)


@dataclass
class TaxAdjustedPrice:
    """Price with tax adjustments."""
    base_price: Decimal
    currency: Currency
    country: str
    tax_rate: Decimal
    price_with_tax: Decimal


@dataclass
class RegionalPrice:
    """Product price in a specific region."""
    platform: str
    country: str
    currency: Currency
    price: Decimal
    price_usd: Decimal
    price_with_tax_usd: Decimal
    in_stock: bool
    url: str | None = None


def calculate_tax_adjusted_price(
    base_price: Decimal,
    currency: Currency,
    country: str,
) -> TaxAdjustedPrice:
    """Calculate price with regional tax."""
    tax_rate = TAX_RATES.get(country, Decimal("0.10"))
    price_with_tax = base_price * (1 + tax_rate)

    return TaxAdjustedPrice(
        base_price=base_price,
        currency=currency,
        country=country,
        tax_rate=tax_rate,
        price_with_tax=round(price_with_tax, 2),
    )


def estimate_shipping(from_country: str, to_country: str) -> Decimal:
    """Estimate shipping cost between countries."""
    key = (from_country.upper(), to_country.upper())
    return SHIPPING_ESTIMATES.get(key, Decimal("35.00"))  # Default international shipping
