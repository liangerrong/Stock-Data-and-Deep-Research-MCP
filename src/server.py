import sys

# === MUST BE FIRST: protect the MCP stdio binary protocol from library print() pollution ===
# MCP uses sys.stdout.buffer for JSON-RPC framing; any text written via print() / logging
# to sys.stdout corrupts the protocol and causes Cursor to close stdin (BrokenResourceError).
# This guard keeps .buffer pointing at the real binary stdout while routing text writes to stderr.
class _StdoutGuard:
    def __init__(self):
        self.buffer = sys.__stdout__.buffer

    def write(self, text: str) -> int:
        return sys.stderr.write(text)

    def flush(self) -> None:
        sys.stderr.flush()

    def fileno(self) -> int:
        return self.buffer.fileno()

    def isatty(self) -> bool:
        return False

sys.stdout = _StdoutGuard()
# ==========================================================================================

import asyncio
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server

# Configure logging — explicitly target stderr so log lines never touch the MCP pipe
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger("ashare-mcp")

# Create the MCP server instance
server = Server("ashare-mcp")

from src.tools.get_financials import handle_get_financials
from src.tools.build_historical_package import handle_build_historical_package
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
            description=(
                "Find the stock code or ticker for a given company name. "
                "For A-share companies listed on Shanghai/Shenzhen exchanges use market='cn' (default). "
                "For Hong Kong listed companies (港股), you MUST pass market='hk'; "
                "otherwise the search will only look in the A-share database and will fail. "
                "Examples: '贵州茅台' → cn, '腾讯控股' / 'Tencent' → hk."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "stock_name": {
                        "type": "string",
                        "description": "The company name in Chinese or English (e.g., '贵州茅台', '腾讯控股', 'Tencent')."
                    },
                    "market": {
                        "type": "string",
                        "enum": ["cn", "hk"],
                        "description": "Market to search: 'cn' for A-shares (default), 'hk' for Hong Kong stocks. Always set 'hk' for HK-listed companies."
                    }
                },
                "required": ["stock_name"]
            }
        ),
        types.Tool(
            name="build_historical_financial_package",
            description=(
                "Build an auditable A-share or Hong Kong historical financial research package for financial modeling. "
                "It saves separate annual/interim statements, normalized core actuals, all non-empty line items, "
                "product/industry/geography composition, financial indicators, share-capital history, dividends, "
                "source links, traceable units and currency roles, a manifest, and automated quality checks. "
                "For HK stocks it strictly separates HKD quote currency from issuer financial-statement currency "
                "and quarantines provider amounts whose currency transformation is unresolved."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "stock_code": {
                        "type": "string",
                        "description": "Six-digit A-share code (e.g. '000408') or HK ticker/code (e.g. '0700.HK' or '00700')."
                    },
                    "years": {
                        "type": "integer",
                        "minimum": 3,
                        "maximum": 10,
                        "default": 5,
                        "description": "Number of annual periods to include; must be between 3 and 10."
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Optional absolute output directory. Defaults to the current directory."
                    },
                    "include_latest_interim": {
                        "type": "boolean",
                        "default": True,
                        "description": "Include the latest available interim statement period."
                    }
                },
                "required": ["stock_code"]
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

    elif name == "build_historical_financial_package":
        stock_code = arguments.get("stock_code")
        if not stock_code:
            raise ValueError("stock_code string argument is required")
        result = handle_build_historical_package(
            stock_code=stock_code,
            years=arguments.get("years", 5),
            output_dir=arguments.get("output_dir"),
            include_latest_interim=arguments.get("include_latest_interim", True),
        )
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
