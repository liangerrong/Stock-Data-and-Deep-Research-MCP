import os
import pandas as pd
from typing import Dict, Any
from src.core.akshare_client import fetch_market_snapshot, fetch_financial_history
from src.utils.file_utils import save_dataframe_to_markdown

def get_output_dir() -> str:
    # Use current working directory
    return os.getcwd()

def handle_get_financials(stock_code: str, years: int = 1) -> str:
    """
    Handler for the get_financials MCP tool.
    Fetches financial history and market snapshot, saves them locally, 
    and returns their file paths.
    """
    try:
        # Fetch market snapshot
        snapshot = fetch_market_snapshot(stock_code)
        
        # Convert snapshot to a dataframe so we can save it via our utils
        snapshot_df = pd.DataFrame([snapshot])
        
        # Fetch financial history
        financials_df = fetch_financial_history(stock_code, years)
        
        # Determine output paths
        output_dir = get_output_dir()
        market_file = os.path.join(output_dir, f"{stock_code}_market.md")
        financials_file = os.path.join(output_dir, f"{stock_code}_financials.md")
        
        # Save files
        market_path = save_dataframe_to_markdown(snapshot_df, market_file)
        financials_path = save_dataframe_to_markdown(financials_df, financials_file)
        
        return f"Data saved successfully. Financials: {financials_path}, Market Data: {market_path}"
        
    except ValueError as ve:
        return f"Error fetching financial data: {str(ve)}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"
