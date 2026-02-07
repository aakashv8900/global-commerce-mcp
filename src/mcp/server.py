"""MCP Server setup for CommerceSignal."""

import re
from mcp.server import Server
from mcp.types import Tool, TextContent

from src.config import settings
from .tools import (
    analyze_product_handler,
    compare_global_prices_handler,
    detect_trending_products_handler,
    analyze_seller_handler,
)


def create_mcp_server() -> Server:
    """Create and configure the MCP server."""
    server = Server(settings.mcp_server_name)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available MCP tools."""
        return [
            Tool(
                name="analyze_product",
                description="""Analyze an Amazon or Flipkart product by URL.
                
Returns comprehensive product intelligence including:
- Estimated monthly revenue and daily sales
- Demand score (0-100) based on review velocity and rank improvement
- Competition score (0-100) based on seller count and buybox volatility
- Trend score (-100 to +100) indicating market momentum
- Risk score (0-100) with specific risk flags
- Discount cycle prediction
- 5 actionable insights

Example: analyze_product("https://amazon.com/dp/B0XXXXXXXX")""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Product URL from Amazon US or Flipkart India",
                        }
                    },
                    "required": ["url"],
                },
            ),
            Tool(
                name="compare_global_prices",
                description="""Compare prices for a product across regions.
                
Returns:
- Region-wise pricing comparison
- Tax-adjusted arbitrage margins
- Spread percentage
- Buy recommendation

Note: Currently supports Amazon US. More regions coming in Phase 2.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Product URL to compare prices for",
                        }
                    },
                    "required": ["url"],
                },
            ),
            Tool(
                name="detect_trending_products",
                description="""Detect trending products in a category.
                
Returns top 10 trending products with:
- ASIN and title
- Trend score
- Review velocity (reviews/day)
- Rank improvement percentage

Categories: Electronics, Home & Kitchen, Toys & Games, Sports & Outdoors, 
Beauty & Personal Care, Health & Household, Clothing, Books""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Product category to analyze",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of products to return (default: 10, max: 25)",
                            "default": 10,
                        },
                    },
                    "required": ["category"],
                },
            ),
            Tool(
                name="analyze_seller",
                description="""Analyze an Amazon or Flipkart seller.
                
Returns seller intelligence:
- Competition index
- Review manipulation risk assessment
- Fulfillment pattern analysis
- Stockout frequency

Example: analyze_seller("A1234EXAMPLE5")""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "seller_id": {
                            "type": "string",
                            "description": "Seller ID from Amazon or Flipkart",
                        },
                        "platform": {
                            "type": "string",
                            "enum": ["amazon_us", "flipkart_in"],
                            "description": "E-commerce platform",
                            "default": "amazon_us",
                        },
                    },
                    "required": ["seller_id"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Handle tool calls."""
        handlers = {
            "analyze_product": analyze_product_handler,
            "compare_global_prices": compare_global_prices_handler,
            "detect_trending_products": detect_trending_products_handler,
            "analyze_seller": analyze_seller_handler,
        }

        handler = handlers.get(name)
        if not handler:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        try:
            result = await handler(arguments)
            return [TextContent(type="text", text=result)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    return server
