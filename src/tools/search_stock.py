import logging
from src.core.akshare_client import search_stock_code

logger = logging.getLogger(__name__)

def handle_search_stock(stock_name: str) -> str:
    """
    Handler for the search_stock MCP tool.
    Searches for a stock name and returns the corresponding 6-digit stock code.
    """
    try:
        stock_code = search_stock_code(stock_name)
        return f"Found stock code for {stock_name}: {stock_code}"
    except ValueError as ve:
        return f"Error: {str(ve)}"
    except Exception as e:
        logger.error(f"Error executing search_stock for {stock_name}: {e}")
        return f"An unexpected error occurred: {str(e)}"
