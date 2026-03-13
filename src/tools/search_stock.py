import logging
from src.core.akshare_client import search_stock_code
from src.core.yfinance_client import search_hk_stock_code

logger = logging.getLogger(__name__)

def handle_search_stock(stock_name: str, market: str = "cn") -> str:
    """
    Handler for the search_stock MCP tool.
    Searches for a stock name and returns the corresponding stock code/ticker.
    """
    try:
        if market.lower() == "hk":
            ticker = search_hk_stock_code(stock_name)
            return f"Found HK stock ticker for {stock_name}: {ticker}"
        else:
            stock_code = search_stock_code(stock_name)
            return f"Found stock code for {stock_name}: {stock_code}"
    except ValueError as ve:
        return f"Error: {str(ve)}"
    except Exception as e:
        logger.error(f"Error executing search_stock for {stock_name}: {e}")
        return f"An unexpected error occurred: {str(e)}"
