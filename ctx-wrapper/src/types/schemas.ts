/**
 * Output schemas for CTX Protocol compliance.
 * Each tool must declare its response structure.
 */

export const ProductAnalysisSchema = {
    type: "object",
    properties: {
        product: {
            type: "object",
            properties: {
                asin: { type: "string" },
                title: { type: "string" },
                platform: { type: "string" },
                price: { type: "number" },
                currency: { type: "string" },
                category: { type: "string" },
                brand: { type: "string" },
                imageUrl: { type: "string" },
            },
            required: ["asin", "title", "platform", "price"],
        },
        intelligence: {
            type: "object",
            properties: {
                demandScore: { type: "number", minimum: 0, maximum: 100 },
                competitionScore: { type: "number", minimum: 0, maximum: 100 },
                trendScore: { type: "number", minimum: -100, maximum: 100 },
                riskScore: { type: "number", minimum: 0, maximum: 100 },
                revenueEstimate: {
                    type: "object",
                    properties: {
                        monthly: { type: "number" },
                        daily: { type: "number" },
                        confidence: { type: "string" },
                    },
                },
                discountCycle: {
                    type: "object",
                    properties: {
                        nextExpectedDate: { type: "string" },
                        probability: { type: "number" },
                        typicalDiscount: { type: "number" },
                    },
                },
            },
            required: ["demandScore", "competitionScore", "trendScore", "riskScore"],
        },
        insights: {
            type: "array",
            items: { type: "string" },
        },
    },
    required: ["product", "intelligence", "insights"],
} as const;

export const PriceComparisonSchema = {
    type: "object",
    properties: {
        baseProduct: {
            type: "object",
            properties: {
                title: { type: "string" },
                platform: { type: "string" },
                price: { type: "number" },
                currency: { type: "string" },
            },
            required: ["title", "platform", "price", "currency"],
        },
        comparisons: {
            type: "array",
            items: {
                type: "object",
                properties: {
                    platform: { type: "string" },
                    price: { type: "number" },
                    currency: { type: "string" },
                    priceUsd: { type: "number" },
                    savings: { type: "number" },
                    savingsPercent: { type: "number" },
                    url: { type: "string" },
                },
                required: ["platform", "price", "currency", "priceUsd"],
            },
        },
        arbitrage: {
            type: "object",
            properties: {
                opportunity: { type: "boolean" },
                bestSource: { type: "string" },
                potentialProfit: { type: "number" },
                shippingEstimate: { type: "number" },
                dutyEstimate: { type: "number" },
            },
        },
    },
    required: ["baseProduct", "comparisons"],
} as const;

export const TrendingProductsSchema = {
    type: "object",
    properties: {
        category: { type: "string" },
        platform: { type: "string" },
        products: {
            type: "array",
            items: {
                type: "object",
                properties: {
                    rank: { type: "number" },
                    asin: { type: "string" },
                    title: { type: "string" },
                    price: { type: "number" },
                    rating: { type: "number" },
                    reviews: { type: "number" },
                    trendScore: { type: "number" },
                    demandSignals: {
                        type: "array",
                        items: { type: "string" },
                    },
                },
                required: ["rank", "title", "price", "trendScore"],
            },
        },
        trendInsights: {
            type: "array",
            items: { type: "string" },
        },
    },
    required: ["category", "platform", "products"],
} as const;

export const SellerAnalysisSchema = {
    type: "object",
    properties: {
        seller: {
            type: "object",
            properties: {
                id: { type: "string" },
                name: { type: "string" },
                platform: { type: "string" },
                rating: { type: "number" },
                totalRatings: { type: "number" },
                positiveFeedback: { type: "number" },
            },
            required: ["id", "name", "platform"],
        },
        metrics: {
            type: "object",
            properties: {
                productCount: { type: "number" },
                avgPrice: { type: "number" },
                priceRange: {
                    type: "object",
                    properties: {
                        min: { type: "number" },
                        max: { type: "number" },
                    },
                },
                categoryDistribution: {
                    type: "object",
                    additionalProperties: { type: "number" },
                },
                buyboxWinRate: { type: "number" },
            },
        },
        competitivePosition: {
            type: "object",
            properties: {
                tier: { type: "string", enum: ["top", "mid", "low"] },
                strengths: { type: "array", items: { type: "string" } },
                weaknesses: { type: "array", items: { type: "string" } },
            },
        },
    },
    required: ["seller", "metrics"],
} as const;

export const BrandAnalysisSchema = {
    type: "object",
    properties: {
        brand: {
            type: "object",
            properties: {
                name: { type: "string" },
                platform: { type: "string" },
                category: { type: "string" },
                logoUrl: { type: "string" },
            },
            required: ["name", "platform"],
        },
        healthScore: { type: "number", minimum: 0, maximum: 100 },
        metrics: {
            type: "object",
            properties: {
                avgRating: { type: "number" },
                totalReviews: { type: "number" },
                reviewVelocity: { type: "number" },
                revenueEstimate: { type: "number" },
                marketSharePercent: { type: "number" },
                productCount: { type: "number" },
            },
        },
        trend: {
            type: "string",
            enum: ["growing", "stable", "declining"],
        },
        insights: {
            type: "array",
            items: { type: "string" },
        },
    },
    required: ["brand", "healthScore", "metrics", "trend"],
} as const;

export const DemandForecastSchema = {
    type: "object",
    properties: {
        productId: { type: "string" },
        horizonDays: { type: "number" },
        prediction: {
            type: "object",
            properties: {
                dailySales: { type: "number" },
                totalSales: { type: "number" },
                confidenceScore: { type: "number" },
                confidenceInterval: {
                    type: "object",
                    properties: {
                        low: { type: "number" },
                        high: { type: "number" },
                    },
                },
            },
            required: ["dailySales", "totalSales", "confidenceScore"],
        },
        dailyPredictions: {
            type: "array",
            items: {
                type: "object",
                properties: {
                    date: { type: "string" },
                    sales: { type: "number" },
                },
            },
        },
        factors: {
            type: "array",
            items: {
                type: "object",
                properties: {
                    factor: { type: "string" },
                    impact: { type: "string", enum: ["positive", "negative", "neutral"] },
                    weight: { type: "number" },
                },
            },
        },
    },
    required: ["productId", "horizonDays", "prediction"],
} as const;

export const AlertSubscriptionSchema = {
    type: "object",
    properties: {
        subscriptionId: { type: "string" },
        status: { type: "string", enum: ["active", "inactive"] },
        alertType: { type: "string" },
        productId: { type: "string" },
        platform: { type: "string" },
        threshold: {
            type: "object",
            properties: {
                value: { type: "number" },
                percent: { type: "number" },
            },
        },
        createdAt: { type: "string" },
    },
    required: ["subscriptionId", "status", "alertType"],
} as const;
