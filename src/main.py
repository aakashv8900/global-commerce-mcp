"""CommerceSignal MCP Server - Main Entry Point."""

import asyncio
import sys

from mcp.server.stdio import stdio_server

from src.config import settings
from src.db.database import init_db
from src.mcp import create_mcp_server
from src.jobs import create_scheduler


async def run_mcp_server():
    """Run the MCP server in stdio mode."""
    print(f"Starting CommerceSignal MCP v{settings.mcp_server_version}", file=sys.stderr)

    # Initialize database
    await init_db()

    # Create MCP server
    server = create_mcp_server()

    # Run with stdio transport
    async with stdio_server() as streams:
        await server.run(
            streams[0],
            streams[1],
            server.create_initialization_options(),
        )


async def run_with_scheduler():
    """Run the MCP server with background scheduler."""
    # Initialize database
    await init_db()

    # Start scheduler
    scheduler = create_scheduler()
    scheduler.start()
    print("Scheduler started", file=sys.stderr)

    # Run MCP server
    await run_mcp_server()


def main():
    """Main entry point."""
    try:
        asyncio.run(run_mcp_server())
    except KeyboardInterrupt:
        print("\nShutting down...", file=sys.stderr)


if __name__ == "__main__":
    main()
