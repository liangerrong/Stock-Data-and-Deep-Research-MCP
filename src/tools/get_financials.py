import os
import pandas as pd
from typing import Dict, Any
from src.core.akshare_client import fetch_market_snapshot, fetch_financial_history, fetch_latest_quarterly_report
from src.core.yfinance_client import fetch_hk_market_snapshot, fetch_hk_financial_history, fetch_hk_latest_quarterly_report
from src.utils.file_utils import save_dataframe_to_markdown


def _is_hk_stock(stock_code: str) -> bool:
    return stock_code.upper().endswith(".HK")


def get_output_dir(output_dir: str = None) -> str:
    if not output_dir:
        return os.getcwd()

    actual_output_dir = os.path.abspath(os.path.expanduser(output_dir))
    os.makedirs(actual_output_dir, exist_ok=True)
    return actual_output_dir

def handle_get_financials(stock_code: str, years: int = 3, output_dir: str = None) -> str:
    """
    Handler for the get_financials MCP tool.
    Fetches financial history, latest quarterly report, and market snapshot,
    saves them locally, and returns their file paths.
    """
    try:
        # Route to HK or A-share based on stock code format
        if _is_hk_stock(stock_code):
            ticker = stock_code.upper()
            from src.core.yfinance_client import create_ticker_obj
            t_obj = create_ticker_obj(ticker)
            snapshot = fetch_hk_market_snapshot(ticker, ticker_obj=t_obj)
            quarterly_df = fetch_hk_latest_quarterly_report(ticker, ticker_obj=t_obj)
            financials_df = fetch_hk_financial_history(ticker, years, ticker_obj=t_obj)
        else:
            from src.core.akshare_client import fetch_raw_sina_reports
            snapshot = fetch_market_snapshot(stock_code)
            raw_reports = fetch_raw_sina_reports(stock_code)
            quarterly_df = fetch_latest_quarterly_report(stock_code, raw_reports=raw_reports)
            financials_df = fetch_financial_history(stock_code, years, raw_reports=raw_reports)

        # Convert snapshot to a dataframe so we can save it via our utils
        snapshot_df = pd.DataFrame([snapshot])
        
        # Determine output path
        actual_output_dir = get_output_dir(output_dir)
        combined_file = os.path.join(actual_output_dir, f"{stock_code}_financial_data.md")
        
        # Save all dataframes to a single markdown file
        os.makedirs(actual_output_dir, exist_ok=True)
        with open(combined_file, 'w', encoding='utf-8') as f:
            f.write(f"# Market Snapshot for {stock_code}\n\n")
            f.write(snapshot_df.to_markdown(index=False))

            # Write quarterly report section (before annual) if available
            if quarterly_df is not None and not quarterly_df.empty:
                f.write("\n\n# Latest Quarterly Report\n\n")
                f.write(quarterly_df.to_markdown(index=False))

            f.write("\n\n# Annual Financial History\n\n")
            f.write(financials_df.to_markdown(index=False))
            
        combined_path = os.path.abspath(combined_file)
        return f"Data saved successfully. Financial Data: {combined_path}"
        
    except ValueError as ve:
        return f"Error fetching financial data: {str(ve)}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"
