import asyncio
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ashare-mcp")

# Create the MCP server instance
server = Server("ashare-mcp")

from src.tools.get_financials import handle_get_financials
from src.tools.search_stock import handle_search_stock
import mcp.types as types

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_financials",
            description="Fetch the current market snapshot and recent years of financial data, save them to the specified directory (or current directory by default), and return the local file paths. Supports A-shares (e.g., '600519') and HK stocks in yfinance format (e.g., '0700.HK').",
            inputSchema={
                "type": "object",
                "properties": {
                    "stock_code": {
                        "type": "string",
                        "description": "The stock code. A-shares: 6-digit code (e.g., '600519'). HK stocks: ticker with .HK suffix (e.g., '0700.HK')."
                    },
                    "years": {
                        "type": "integer",
                        "description": "Number of recent years of financial data to fetch (default: 3)"
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Optional absolute path to the directory where the output files should be saved. Defaults to current directory."
                    }
                },
                "required": ["stock_code"]
            }
        ),
        types.Tool(
            name="search_stock",
            description="Find the stock code or ticker corresponding to a given company name. Supports A-shares (market='cn') and HK stocks (market='hk').",
            inputSchema={
                "type": "object",
                "properties": {
                    "stock_name": {
                        "type": "string",
                        "description": "The name of the company (e.g., '贵州茅台' or '腾讯控股')"
                    },
                    "market": {
                        "type": "string",
                        "enum": ["cn", "hk"],
                        "description": "Market to search: 'cn' for A-shares (default), 'hk' for Hong Kong stocks."
                    }
                },
                "required": ["stock_name"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    if name == "get_financials":
        stock_code = arguments.get("stock_code")
        years = arguments.get("years", 3)
        output_dir = arguments.get("output_dir")
        
        if not stock_code:
            raise ValueError("stock_code string argument is required")
            
        result = handle_get_financials(stock_code, years, output_dir)
        return [types.TextContent(type="text", text=result)]
        
    elif name == "search_stock":
        stock_name = arguments.get("stock_name")

        if not stock_name:
            raise ValueError("stock_name string argument is required")

        market = arguments.get("market", "cn")
        result = handle_search_stock(stock_name, market)
        return [types.TextContent(type="text", text=result)]
        
    raise ValueError(f"Unknown tool: {name}")

async def main():
    logger.info("Starting ashare-mcp server...")
    
    # Run the server over stdio
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
