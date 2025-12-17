"""
MCP Server for Stock Analysis Tools
Powered by FastMCP
"""
from mcp.server.fastmcp import FastMCP, Context
from typing import List, Optional, Literal
from pydantic import Field
import json
import logging
import sys

# Setup logging to stderr (as MCP uses stdin/stdout for communication)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("mcp-server")

from interface import StockAnalysisTools

# Initialize FastMCP Server
mcp = FastMCP("Stock Analysis Tools")

# Initialize underlying toolset
tools = StockAnalysisTools()

@mcp.tool()
def get_stock_info(
    name_or_code: str = Field(description="The stock name (e.g., 'Moutai') or code (e.g., '600519')")
) -> str:
    """
    Search for a stock by name or code to get its standardized symbol.
    Always use this first if you are unsure about the stock code.
    """
    logger.info(f"Tool call: get_stock_info({name_or_code})")
    result = tools.get_stock_info(name_or_code)
    return json.dumps(result, ensure_ascii=False)

@mcp.tool()
def get_stock_daily_data(
    stock_code: str = Field(description="Standard stock code (e.g., '600519.SH') returned by get_stock_info"),
    start_date: str = Field(description="Start date in YYYY-MM-DD format"),
    end_date: str = Field(description="End date in YYYY-MM-DD format (optional, defaults to today)", default=None)
) -> str:
    """
    Get daily stock market data (Open, High, Low, Close, Volume).
    """
    logger.info(f"Tool call: get_stock_daily_data({stock_code}, {start_date}, {end_date})")
    data = tools.get_stock_daily(stock_code, start_date, end_date)
    # MCP expects string returns typically, or structured. FastMCP handles Dict/List, but let's be explicit with JSON string for complex data to ensure client compatibility or return raw list if client supports it.
    # FastMCP documentation often suggests returning native types which it serializes. 
    # Let's return native types (List[Dict]) and let FastMCP handle JSON serialization.
    # Wait, doc says "Return value: Any".
    # User requested: "input schema... returning format".
    # I will return the Python object, FastMCP will serialize it to JSON.
    return json.dumps(data, ensure_ascii=False) # Returning string to be safe and consistent with previous tool

@mcp.tool()
def get_financial_report(
    stock_code: str = Field(description="Standard stock code"),
    report_type: Literal["balance_sheet", "profit_sheet", "cash_flow_sheet", "all"] = Field(
        default="all", 
        description="Type of financial report to fetch. 'all' fetches all three."
    ),
    limit: int = Field(default=4, description="Number of recent periods to fetch (e.g. 4 quarters)")
) -> str:
    """
    Get financial statements (Balance Sheet, Profit Statement, Cash Flow).
    Useful for fundamental analysis (ROE, Net Profit, Debt, etc.).
    """
    logger.info(f"Tool call: get_financial_report({stock_code}, {report_type})")
    data = tools.get_financial_report(stock_code, report_type, limit)
    return json.dumps(data, ensure_ascii=False)

@mcp.tool()
def calculate_technical_indicators(
    daily_data_json: str = Field(description="The JSON string output from get_stock_daily_data")
) -> str:
    """
    Calculate technical indicators (MA, RSI, Trend) from daily data.
    Input must be the raw JSON string returned by get_stock_daily_data.
    """
    logger.info("Tool call: calculate_technical_indicators")
    try:
        data_list = json.loads(daily_data_json)
        result = tools.calculate_indicators(data_list)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error calculating indicators: {e}")
        return json.dumps({"error": str(e)})

if __name__ == "__main__":
    mcp.run(transport="stdio")

