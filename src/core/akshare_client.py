import datetime
import pandas as pd
import akshare as ak

def fetch_market_snapshot(stock_code: str) -> dict:
    """
    Fetches the current market snapshot including price and circulating shares.
    
    Args:
        stock_code: The 6-digit stock code (e.g., '600519').
        
    Returns:
        Dictionary with stock_code, stock_name, current_price, circulating_shares
    """
    # Fetch real-time market data
    df = ak.stock_zh_a_spot_em()
    
    # Filter for the specific stock code
    stock_df = df[df["代码"] == stock_code]
    
    if stock_df.empty:
        raise ValueError(f"Could not find market data for stock code: {stock_code}")
        
    stock_info = stock_df.iloc[0]
    
    return {
        "stock_code": stock_code,
        "stock_name": stock_info["名称"],
        "current_price": stock_info["最新价"],
        "circulating_shares": stock_info.get("流通股本", 0.0)
    }

def fetch_financial_history(stock_code: str, years: int = 1) -> pd.DataFrame:
    """
    Fetches the financial indicators history for the last N years.
    
    Args:
        stock_code: The 6-digit stock code.
        years: The number of recent years to fetch.
        
    Returns:
        A pandas DataFrame containing the financial indicators.
    """
    current_year = datetime.datetime.now().year
    start_year = str(current_year - years)
    
    # Fetch financial analysis indicators
    df = ak.stock_financial_analysis_indicator(symbol=stock_code, start_year=start_year)
    
    if df.empty:
        raise ValueError(f"Could not find financial data for stock code: {stock_code}")
        
    # Return the latest N years (assuming 1 yearly report or multiple quarterlies, filter to latest periods if needed)
    # The dataframe returned depends on akshare logic, usually contains all periods from start_year.
    return df

def search_stock_code(stock_name: str) -> str:
    """
    Search for a stock code given a full or partial stock name.
    
    Args:
        stock_name: The company name or acronym.
        
    Returns:
        The 6-digit stock code.
    """
    df = ak.stock_info_a_code_name()
    
    # Check for exact match
    exact_match = df[df["name"] == stock_name]
    if not exact_match.empty:
        return exact_match.iloc[0]["code"]
        
    # Check for partial match
    partial_match = df[df["name"].str.contains(stock_name, na=False)]
    if not partial_match.empty:
        return partial_match.iloc[0]["code"]
        
    raise ValueError(f"Could not find stock name matching: {stock_name}")
