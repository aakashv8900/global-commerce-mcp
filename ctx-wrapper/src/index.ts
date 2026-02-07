/**
 * CommerceSignal MCP Server (Streamable HTTP + SSE)
 * Production-ready for CTX Protocol + Inspector
 */

import express, { Request, Response, NextFunction } from "express";
import crypto from "crypto";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import {
  ListToolsRequestSchema,
  CallToolRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

import { TOOLS } from "./tools/index.js";
import { getBackendClient } from "./backend/client.js";

// Optional CTX SDK (for monetization)
let createContextMiddleware: any = null;
try {
  const ctxSdk = await import("@ctxprotocol/sdk");
  createContextMiddleware = ctxSdk.createContextMiddleware;
} catch {
  console.log("CTX SDK not installed — running without monetization middleware");
}

const app = express();
const PORT: number = process.env.PORT
  ? parseInt(process.env.PORT, 10)
  : 3000;

app.use(express.json());

/**
 * Enable CTX middleware if explicitly enabled
 */
if (process.env.CTX_ENABLED === "true" && createContextMiddleware) {
  app.use("/mcp", createContextMiddleware());
  console.log("✓ CTX middleware enabled");
} else {
  console.log("ℹ CTX middleware disabled");
}

/**
 * Health Check
 */
app.get("/health", (_req: Request, res: Response) => {
  res.json({
    status: "ok",
    service: "commerce-signal-mcp",
    version: "1.0.0",
  });
});

/**
 * Simple test endpoint
 */
app.get("/test/tools", (_req: Request, res: Response) => {
  res.json({
    success: true,
    toolCount: TOOLS.length,
    tools: TOOLS.map((t) => ({
      name: t.name,
      description: t.description,
    })),
  });
});

/**
 * Create MCP Server
 */
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

/**
 * list_tools handler
 */
mcpServer.setRequestHandler(ListToolsRequestSchema, async () => {
  return { tools: TOOLS };
});

/**
 * call_tool handler
 */
mcpServer.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  const backend = getBackendClient();

  try {
    let result: any;

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

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(result, null, 2),
        },
      ],
      structuredContent: result, // required for CTX monetization
    };
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unknown error";

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

/**
 * Create Streamable HTTP Transport
 */
const streamableTransport = new StreamableHTTPServerTransport({
  sessionIdGenerator: () => crypto.randomUUID(),
});

/**
 * SSE Transport - Map of session ID to transport
 */
const sseTransports = new Map<string, SSEServerTransport>();

/**
 * Create a new MCP Server for SSE (separate from streamable)
 */
function createSSEServer(): Server {
  const server = new Server(
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

  // Register same handlers
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return { tools: TOOLS };
  });

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    const backend = getBackendClient();

    try {
      let result: any;

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

      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        structuredContent: result,
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      return {
        content: [{ type: "text", text: `Error: ${message}` }],
        isError: true,
      };
    }
  });

  return server;
}

/**
 * Global Error Handler
 */
app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
  console.error("Server error:", err);
  res.status(500).json({ error: err.message });
});

/**
 * Start Server
 */
async function start() {
  try {
    // 1️⃣ Connect MCP to Streamable HTTP transport
    await mcpServer.connect(streamableTransport);

    // 2️⃣ Mount /mcp endpoint with auto-transport detection
    // Handles both SSE (for Inspector) and StreamableHTTP (for production)
    app.all("/mcp", async (req: Request, res: Response) => {
      const acceptHeader = req.headers.accept || "";
      const isSSERequest = req.method === "GET" && acceptHeader.includes("text/event-stream");

      if (isSSERequest) {
        // SSE transport for MCP Inspector
        console.log("SSE connection on /mcp (Inspector mode)");
        const sessionId = crypto.randomUUID();
        const sseTransport = new SSEServerTransport("/messages", res);
        sseTransports.set(sessionId, sseTransport);

        const sseServer = createSSEServer();

        res.on("close", () => {
          console.log(`SSE session ${sessionId} closed`);
          sseTransports.delete(sessionId);
        });

        try {
          await sseServer.connect(sseTransport);
          console.log(`SSE session ${sessionId} connected`);
        } catch (error) {
          console.error("SSE connection error:", error);
          sseTransports.delete(sessionId);
        }
      } else {
        // StreamableHTTP for production clients
        await streamableTransport.handleRequest(req, res);
      }
    });

    // 3️⃣ SSE endpoint - GET /sse for SSE connections (Inspector compatible)
    app.get("/sse", async (req: Request, res: Response) => {
      console.log("New SSE connection request");

      const sessionId = crypto.randomUUID();
      const sseTransport = new SSEServerTransport("/messages", res);
      sseTransports.set(sessionId, sseTransport);

      // Create a new MCP server for this SSE session
      const sseServer = createSSEServer();

      res.on("close", () => {
        console.log(`SSE session ${sessionId} closed`);
        sseTransports.delete(sessionId);
      });

      try {
        await sseServer.connect(sseTransport);
        console.log(`SSE session ${sessionId} connected`);
      } catch (error) {
        console.error("SSE connection error:", error);
        sseTransports.delete(sessionId);
      }
    });

    // 4️⃣ SSE message endpoint - POST /messages for SSE messages
    app.post("/messages", async (req: Request, res: Response) => {
      const sessionId = req.query.sessionId as string;
      const transport = sseTransports.get(sessionId);

      if (!transport) {
        res.status(400).json({ error: "Invalid or expired session" });
        return;
      }

      try {
        await transport.handlePostMessage(req, res);
      } catch (error) {
        console.error("SSE message error:", error);
        res.status(500).json({ error: "Failed to handle message" });
      }
    });

    // 5️⃣ Start Express
    app.listen(PORT, "0.0.0.0", () => {
      console.log(`
╔═══════════════════════════════════════════════════════════╗
║     CommerceSignal MCP (StreamableHTTP + SSE Ready)      ║
╠═══════════════════════════════════════════════════════════╣
║  Running on port ${PORT}                                       ║
║  StreamableHTTP: http://localhost:${PORT}/mcp                  ║
║  SSE (Inspector): http://localhost:${PORT}/sse                 ║
║  Health: http://localhost:${PORT}/health                       ║
║  Tools: ${TOOLS.length}                                              ║
╚═══════════════════════════════════════════════════════════╝
      `);
    });
  } catch (err) {
    console.error("Failed to start MCP server:", err);
    process.exit(1);
  }
}

start();

export { app, mcpServer };