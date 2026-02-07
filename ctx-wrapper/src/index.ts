/**
 * CommerceSignal MCP Server for CTX Protocol
 *
 * Express + MCP SDK + CTX middleware for marketplace monetization.
 */

import express, { Request, Response, NextFunction } from "express";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import {
    ListToolsRequestSchema,
    CallToolRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { createContextMiddleware } from "@ctxprotocol/sdk";

import { TOOLS, getToolByName } from "./tools/index.js";
import { getBackendClient } from "./backend/client.js";

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

// CTX Protocol middleware - handles payment verification & request signing
// This is required for paid tools on the CTX marketplace
if (process.env.CTX_ENABLED === "true") {
    app.use("/mcp", createContextMiddleware());
    console.log("✓ CTX Protocol middleware enabled");
}

// Health check endpoint
app.get("/health", (_req: Request, res: Response) => {
    res.json({ status: "ok", service: "commerce-signal-mcp", version: "1.0.0" });
});

// Create MCP server instance
const mcpServer = new Server(
    {
        name: "commerce-signal",
        version: "1.0.0",
    },
    {
        capabilities: {
            tools: {},
        },
    }
);

// Handle list_tools request
mcpServer.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
        tools: TOOLS,
    };
});

// Handle call_tool request
mcpServer.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    const backend = getBackendClient();

    try {
        let result: object;

        switch (name) {
            case "analyze_product":
                result = await backend.analyzeProduct(args?.url as string);
                break;

            case "compare_global_prices":
                result = await backend.compareGlobalPrices(
                    args?.url as string,
                    args?.includeRegions as string[]
                );
                break;

            case "detect_trending_products":
                result = await backend.detectTrending(
                    args?.category as string,
                    (args?.platform as string) || "amazon_us",
                    (args?.limit as number) || 10
                );
                break;

            case "analyze_seller":
                result = await backend.analyzeSeller(
                    args?.sellerId as string,
                    (args?.platform as string) || "amazon_us"
                );
                break;

            case "analyze_brand":
                result = await backend.analyzeBrand(
                    args?.brandName as string,
                    (args?.platform as string) || "amazon_us",
                    args?.category as string
                );
                break;

            case "forecast_demand":
                result = await backend.forecastDemand(
                    args?.productUrl as string,
                    (args?.horizonDays as number) || 7
                );
                break;

            case "subscribe_alert":
                result = await backend.subscribeAlert(
                    args?.productUrl as string,
                    args?.alertType as string,
                    args?.thresholdPercent as number
                );
                break;

            default:
                throw new Error(`Unknown tool: ${name}`);
        }

        // Return both text (for backward compat) and structuredContent (for CTX)
        return {
            content: [
                {
                    type: "text",
                    text: JSON.stringify(result, null, 2),
                },
            ],
            structuredContent: result, // Required by CTX Protocol
        };
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error";
        return {
            content: [
                {
                    type: "text",
                    text: `Error: ${message}`,
                },
            ],
            isError: true,
        };
    }
});

// SSE endpoint for MCP transport
const transports = new Map<string, SSEServerTransport>();

app.get("/mcp/sse", async (req: Request, res: Response) => {
    console.log("New SSE connection");

    const transport = new SSEServerTransport("/mcp/messages", res);
    const sessionId = crypto.randomUUID();
    transports.set(sessionId, transport);

    res.on("close", () => {
        transports.delete(sessionId);
        console.log(`SSE connection closed: ${sessionId}`);
    });

    await mcpServer.connect(transport);
});

app.post("/mcp/messages", async (req: Request, res: Response) => {
    // Handle incoming messages from MCP client
    const sessionId = req.headers["x-session-id"] as string;
    const transport = transports.get(sessionId);

    if (transport) {
        // Forward message to transport
        await transport.handlePostMessage(req, res);
    } else {
        res.status(400).json({ error: "Invalid session" });
    }
});

// Error handler
app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
    console.error("Server error:", err);
    res.status(500).json({ error: err.message });
});

// Start server
app.listen(PORT, () => {
    console.log(`
╔═══════════════════════════════════════════════════════════╗
║           CommerceSignal MCP for CTX Protocol             ║
╠═══════════════════════════════════════════════════════════╣
║  Server running on port ${PORT}                              ║
║  MCP endpoint: http://localhost:${PORT}/mcp/sse               ║
║  Health check: http://localhost:${PORT}/health                ║
╠═══════════════════════════════════════════════════════════╣
║  Tools available: ${TOOLS.length}                                       ║
║  CTX Protocol: ${process.env.CTX_ENABLED === "true" ? "Enabled ✓" : "Disabled (set CTX_ENABLED=true)"}     ║
╚═══════════════════════════════════════════════════════════╝
  `);
});

export { app, mcpServer };
