/**
 * HTTP client for Python backend communication.
 */

import axios, { AxiosInstance } from "axios";

export interface BackendConfig {
    baseUrl: string;
    timeout?: number;
}

export class BackendClient {
    private client: AxiosInstance;

    constructor(config: BackendConfig) {
        this.client = axios.create({
            baseURL: config.baseUrl,
            timeout: config.timeout || 30000,
            headers: {
                "Content-Type": "application/json",
            },
        });
    }

    async analyzeProduct(url: string): Promise<object> {
        const response = await this.client.post("/api/analyze-product", { url });
        return response.data;
    }

    async compareGlobalPrices(
        url: string,
        regions?: string[]
    ): Promise<object> {
        const response = await this.client.post("/api/compare-prices", {
            url,
            regions,
        });
        return response.data;
    }

    async detectTrending(
        category: string,
        platform: string,
        limit: number
    ): Promise<object> {
        const response = await this.client.post("/api/detect-trending", {
            category,
            platform,
            limit,
        });
        return response.data;
    }

    async analyzeSeller(sellerId: string, platform: string): Promise<object> {
        const response = await this.client.post("/api/analyze-seller", {
            seller_id: sellerId,
            platform,
        });
        return response.data;
    }

    async analyzeBrand(
        brandName: string,
        platform: string,
        category?: string
    ): Promise<object> {
        const response = await this.client.post("/api/analyze-brand", {
            brand_name: brandName,
            platform,
            category,
        });
        return response.data;
    }

    async forecastDemand(
        productUrl: string,
        horizonDays: number
    ): Promise<object> {
        const response = await this.client.post("/api/forecast-demand", {
            product_url: productUrl,
            horizon_days: horizonDays,
        });
        return response.data;
    }

    async subscribeAlert(
        productUrl: string,
        alertType: string,
        thresholdPercent?: number
    ): Promise<object> {
        const response = await this.client.post("/api/subscribe-alert", {
            product_url: productUrl,
            alert_type: alertType,
            threshold_percent: thresholdPercent,
        });
        return response.data;
    }

    async healthCheck(): Promise<boolean> {
        try {
            const response = await this.client.get("/health");
            return response.status === 200;
        } catch {
            return false;
        }
    }
}

// Singleton instance
let backendClient: BackendClient | null = null;

export function getBackendClient(): BackendClient {
    if (!backendClient) {
        const baseUrl = process.env.PYTHON_BACKEND_URL || "http://localhost:8000";
        backendClient = new BackendClient({ baseUrl });
    }
    return backendClient;
}
