/**
 * Tool definitions for CommerceSignal MCP.
 * Each tool includes inputSchema and outputSchema for CTX compliance.
 */

import {
    ProductAnalysisSchema,
    PriceComparisonSchema,
    TrendingProductsSchema,
    SellerAnalysisSchema,
    BrandAnalysisSchema,
    DemandForecastSchema,
    AlertSubscriptionSchema,
} from "../types/schemas.js";

export interface ToolDefinition {
    name: string;
    description: string;
    inputSchema: object;
    outputSchema: object;
}

export const TOOLS: ToolDefinition[] = [
    {
        name: "analyze_product",
        description:
            "Analyze an e-commerce product and get comprehensive intelligence including demand score, competition analysis, revenue estimates, trend detection, and actionable insights. Supports Amazon, Walmart, eBay, Alibaba, Flipkart, and Shopify stores.",
        inputSchema: {
            type: "object",
            properties: {
                url: {
                    type: "string",
                    description:
                        "Product URL from any supported platform (Amazon, Walmart, eBay, Alibaba/AliExpress, Flipkart, Shopify)",
                },
            },
            required: ["url"],
        },
        outputSchema: ProductAnalysisSchema,
    },
    {
        name: "compare_global_prices",
        description:
            "Compare prices for a product across multiple e-commerce platforms and regions. Identifies arbitrage opportunities, calculates potential profit after shipping and duties.",
        inputSchema: {
            type: "object",
            properties: {
                url: {
                    type: "string",
                    description: "Product URL to compare prices for",
                },
                includeRegions: {
                    type: "array",
                    items: { type: "string" },
                    description:
                        "Optional: specific regions to compare (e.g., ['us', 'eu', 'asia'])",
                },
            },
            required: ["url"],
        },
        outputSchema: PriceComparisonSchema,
    },
    {
        name: "detect_trending_products",
        description:
            "Discover trending and best-selling products in a category. Returns products with high demand signals and momentum indicators.",
        inputSchema: {
            type: "object",
            properties: {
                category: {
                    type: "string",
                    description:
                        "Product category (e.g., 'Electronics', 'Home & Kitchen', 'Toys')",
                },
                platform: {
                    type: "string",
                    description:
                        "Platform to search (amazon_us, walmart_us, ebay_us, alibaba_cn, flipkart_in, shopify). Default: amazon_us",
                    default: "amazon_us",
                },
                limit: {
                    type: "number",
                    description: "Maximum number of products to return (default: 10)",
                    default: 10,
                },
            },
            required: ["category"],
        },
        outputSchema: TrendingProductsSchema,
    },
    {
        name: "analyze_seller",
        description:
            "Analyze a seller's competitive position, product portfolio, pricing strategy, and market share. Useful for competitive intelligence.",
        inputSchema: {
            type: "object",
            properties: {
                sellerId: {
                    type: "string",
                    description: "Seller ID or URL",
                },
                platform: {
                    type: "string",
                    description:
                        "Platform (amazon_us, walmart_us, ebay_us, flipkart_in). Default: amazon_us",
                    default: "amazon_us",
                },
            },
            required: ["sellerId"],
        },
        outputSchema: SellerAnalysisSchema,
    },
    {
        name: "analyze_brand",
        description:
            "Get brand-level intelligence including health score, market share, review sentiment, and growth trends. Compares brand performance across categories.",
        inputSchema: {
            type: "object",
            properties: {
                brandName: {
                    type: "string",
                    description: "Brand name to analyze",
                },
                platform: {
                    type: "string",
                    description: "Platform to analyze (default: amazon_us)",
                    default: "amazon_us",
                },
                category: {
                    type: "string",
                    description: "Optional: specific category to focus on",
                },
            },
            required: ["brandName"],
        },
        outputSchema: BrandAnalysisSchema,
    },
    {
        name: "forecast_demand",
        description:
            "Predict future demand for a product using ML models. Returns daily sales predictions with confidence intervals.",
        inputSchema: {
            type: "object",
            properties: {
                productUrl: {
                    type: "string",
                    description: "Product URL to forecast demand for",
                },
                horizonDays: {
                    type: "number",
                    description: "Forecast horizon in days (7, 14, or 30)",
                    default: 7,
                },
            },
            required: ["productUrl"],
        },
        outputSchema: DemandForecastSchema,
    },
    {
        name: "subscribe_alert",
        description:
            "Subscribe to price drop, stockout, or trend change alerts for a product. Get notified when conditions are met.",
        inputSchema: {
            type: "object",
            properties: {
                productUrl: {
                    type: "string",
                    description: "Product URL to monitor",
                },
                alertType: {
                    type: "string",
                    enum: ["price_drop", "stockout", "trend_change", "rank_change"],
                    description: "Type of alert to subscribe to",
                },
                thresholdPercent: {
                    type: "number",
                    description:
                        "Threshold percentage for triggering alert (e.g., 10 for 10% price drop)",
                },
            },
            required: ["productUrl", "alertType"],
        },
        outputSchema: AlertSubscriptionSchema,
    },
];

export function getToolByName(name: string): ToolDefinition | undefined {
    return TOOLS.find((tool) => tool.name === name);
}
