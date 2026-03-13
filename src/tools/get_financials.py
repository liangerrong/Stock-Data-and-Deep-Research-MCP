import os
import pandas as pd
from typing import Dict, Any
from src.core.akshare_client import fetch_market_snapshot, fetch_financial_history
from src.core.yfinance_client import fetch_hk_market_snapshot, fetch_hk_financial_history
from src.utils.file_utils import save_dataframe_to_markdown


def _is_hk_stock(stock_code: str) -> bool:
    return stock_code.upper().endswith(".HK")


def get_output_dir(output_dir: str = None) -> str:
    # Use specified directory if provided and valid, else current working directory
    if output_dir and os.path.exists(output_dir) and os.path.isdir(output_dir):
        return output_dir
    return os.getcwd()

def handle_get_financials(stock_code: str, years: int = 3, output_dir: str = None) -> str:
    """
    Handler for the get_financials MCP tool.
    Fetches financial history and market snapshot, saves them locally, 
    and returns their file paths.
    """
    try:
        # Route to HK or A-share based on stock code format
        if _is_hk_stock(stock_code):
            ticker = stock_code.upper()
            snapshot = fetch_hk_market_snapshot(ticker)
            financials_df = fetch_hk_financial_history(ticker, years)
        else:
            snapshot = fetch_market_snapshot(stock_code)
            financials_df = fetch_financial_history(stock_code, years)

        # Convert snapshot to a dataframe so we can save it via our utils
        snapshot_df = pd.DataFrame([snapshot])
        
        # Determine output path
        actual_output_dir = get_output_dir(output_dir)
        combined_file = os.path.join(actual_output_dir, f"{stock_code}_financial_data.md")
        
        # Save both dataframes to a single markdown file
        os.makedirs(actual_output_dir, exist_ok=True)
        with open(combined_file, 'w', encoding='utf-8') as f:
            f.write(f"# Market Snapshot for {stock_code}\n\n")
            f.write(snapshot_df.to_markdown(index=False))
            f.write("\n\n# Financial History\n\n")
            f.write(financials_df.to_markdown(index=False))
            
        combined_path = os.path.abspath(combined_file)
        return f"Data saved successfully. Financial Data: {combined_path}"
        
    except ValueError as ve:
        return f"Error fetching financial data: {str(ve)}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"
