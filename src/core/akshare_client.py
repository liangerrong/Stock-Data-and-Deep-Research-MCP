import os
import json
import datetime
import pandas as pd
import akshare as ak

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(CURRENT_DIR, ".stock_codes_cache.json")


def get_exchange_prefixed_code(stock_code: str) -> str:
    """Return the Eastmoney-style market-prefixed A-share code."""
    code = str(stock_code).strip().upper()
    if code.startswith(("SH", "SZ", "BJ")):
        return code
    if not (code.isdigit() and len(code) == 6):
        raise ValueError(f"Invalid A-share stock code: {stock_code}")
    if code.startswith(("4", "8", "92")):
        return f"BJ{code}"
    if code.startswith(("5", "6", "9")):
        return f"SH{code}"
    return f"SZ{code}"


def fetch_company_profile(stock_code: str) -> pd.DataFrame:
    """Fetch company profile data from CNInfo through AkShare."""
    return ak.stock_profile_cninfo(symbol=stock_code)


def fetch_main_business_composition(stock_code: str) -> pd.DataFrame:
    """Fetch historical product, industry, and geography composition."""
    return ak.stock_zygc_em(symbol=get_exchange_prefixed_code(stock_code))


def fetch_financial_abstract(stock_code: str) -> pd.DataFrame:
    """Fetch the historical financial abstract used for cross-checks."""
    return ak.stock_financial_abstract(symbol=stock_code)


def fetch_financial_indicators(stock_code: str, start_year: str) -> pd.DataFrame:
    """Fetch historical financial ratios and operating indicators."""
    return ak.stock_financial_analysis_indicator(
        symbol=stock_code,
        start_year=str(start_year),
    )


def fetch_share_changes(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch historical share-capital changes from CNInfo."""
    return ak.stock_share_change_cninfo(
        symbol=stock_code,
        start_date=start_date,
        end_date=end_date,
    )


def fetch_disclosure_reports(
    stock_code: str,
    category: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Fetch disclosure titles and auditable CNInfo links."""
    return ak.stock_zh_a_disclosure_report_cninfo(
        symbol=stock_code,
        market="沪深京",
        category=category,
        start_date=start_date,
        end_date=end_date,
    )


def fetch_dividend_history(stock_code: str) -> pd.DataFrame:
    """Fetch dividend and distribution history from Eastmoney."""
    return ak.stock_fhps_detail_em(symbol=stock_code)

def fetch_market_snapshot(stock_code: str) -> dict:
    """
    Fetches the current market snapshot including price and circulating shares.
    
    Args:
        stock_code: The 6-digit stock code (e.g., '600519').
        
    Returns:
        Dictionary with stock_code, stock_name, current_price, circulating_shares
    """
    # Fetch individual company basic info via cninfo (巨潮资讯) to avoid EM blocks
    stock_name = 'N/A'
    circulating_shares = 0.0
    
    try:
        info_df = ak.stock_profile_cninfo(symbol=stock_code)
        if not info_df.empty:
            # Company name
            stock_name = str(info_df["公司简称"].iloc[0])
            
            # The API provides circulating share directly (usually in units of shares, or sometimes 10k shares depending on the source). 
            # We'll try to extract "流通股本"
            if "流通股本" in info_df.columns:
                circulating_shares = float(info_df["流通股本"].iloc[0])
    except Exception:
        pass
        
    # As fallback or complement, fetch the latest single day K-line point for the exact closing price
    current_price = 0.0
    try:
        # Calculate a short window (e.g. 7 days back) to guarantee at least one trading day
        today = datetime.datetime.now()
        start_date_str = (today - datetime.timedelta(days=7)).strftime("%Y%m%d")
        end_date_str = today.strftime("%Y%m%d")
        
        hist_df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", start_date=start_date_str, end_date=end_date_str)
        if not hist_df.empty:
            current_price = float(hist_df.iloc[-1]["收盘"])
    except Exception:
        pass
        
    return {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "current_price": current_price,
        "circulating_shares": circulating_shares
    }

def fetch_raw_sina_reports(stock_code: str) -> dict[str, pd.DataFrame | None]:
    """
    Fetches the raw financial reports securely one time.
    Returns a dictionary of DataFrames, keys are the report types.
    """
    report_types = ['资产负债表', '利润表', '现金流量表']
    results = {}
    for report in report_types:
        try:
            df = ak.stock_financial_report_sina(stock=stock_code, symbol=report)
            if df is not None and not df.empty:
                results[report] = df
            else:
                results[report] = None
        except Exception:
            results[report] = None
    return results


def fetch_financial_history(stock_code: str, years: int = 3, raw_reports: dict | None = None) -> pd.DataFrame:
    """
    Fetches the raw financial reports (资产负债表, 利润表, 现金流量表) for the last N years (Annual reports only).
    
    Args:
        stock_code: The 6-digit stock code.
        years: The number of recent years to fetch (default: 3).
        raw_reports: Optional pre-fetched reports from fetch_raw_sina_reports.
        
    Returns:
        A pandas DataFrame containing the merged financial reports.
    """
    if raw_reports is None:
        raw_reports = fetch_raw_sina_reports(stock_code)
        
    merged_df = None
    
    for report_name, df in raw_reports.items():
        if df is None or df.empty:
            continue
            
        # Filter for Annual reports only (December 31st) -> date ends with '1231'
        df = df[df['报告日'].astype(str).str.endswith('1231')].copy()
        
        # Sort by date descending and take top N years
        df = df.sort_values(by='报告日', ascending=False).head(years)
        
        # Merge logic
        if merged_df is None:
            merged_df = df
        else:
            # Drop identical index columns before merge if necessary, using '报告日' as the key
            merged_df = pd.merge(merged_df, df, on='报告日', how='outer', suffixes=('', '_dup'))
            
            # Remove duplicated columns from the merge
            dup_cols = [c for c in merged_df.columns if c.endswith('_dup')]
            merged_df.drop(columns=dup_cols, inplace=True)
            
    if merged_df is None or merged_df.empty:
        raise ValueError(f"Could not find financial report data for stock code: {stock_code}")
        
    return merged_df

def fetch_latest_quarterly_report(stock_code: str, raw_reports: dict | None = None) -> pd.DataFrame | None:
    """
    Fetches the latest quarterly (non-annual) financial report.
    
    Quarterly reports have 报告日 ending in 0331, 0630, or 0930.
    Returns only the single most recent quarterly row merged across all three report types.
    Returns None if no quarterly data is available.
    
    Args:
        stock_code: The 6-digit stock code.
        raw_reports: Optional pre-fetched reports from fetch_raw_sina_reports.
        
    Returns:
        A single-row DataFrame with merged quarterly data, or None if unavailable.
    """
    if raw_reports is None:
        raw_reports = fetch_raw_sina_reports(stock_code)
        
    merged_df = None
    
    for report_name, df in raw_reports.items():
        if df is None or df.empty:
            continue
            
        # Filter for quarterly reports only (NOT ending in 1231)
        df = df[~df['报告日'].astype(str).str.endswith('1231')].copy()
        
        if df.empty:
            continue
        
        # Sort by date descending and take the latest quarter only
        df = df.sort_values(by='报告日', ascending=False).head(1)
        
        # Merge logic
        if merged_df is None:
            merged_df = df
        else:
            merged_df = pd.merge(merged_df, df, on='报告日', how='inner', suffixes=('', '_dup'))
            dup_cols = [c for c in merged_df.columns if c.endswith('_dup')]
            merged_df.drop(columns=dup_cols, inplace=True)
            
    if merged_df is None or merged_df.empty:
        return None
        
    return merged_df

def search_stock_code(stock_name: str) -> str:
    """
    Search for a stock code given a full or partial stock name.
    
    Args:
        stock_name: The company name or acronym.
        
    Returns:
        The 6-digit stock code.
    """
    mapping = None
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                mapping = json.load(f)
        except Exception:
            pass
            
    if mapping is None:
        df = ak.stock_info_a_code_name()
        mapping = dict(zip(df['name'], df['code']))
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(mapping, f, ensure_ascii=False)
        except Exception:
            pass
            
    # Check for exact match
    if stock_name in mapping:
        return mapping[stock_name]
        
    # Check for partial match
    for name, code in mapping.items():
        if stock_name in name:
            return code
            
    raise ValueError(f"Could not find stock name matching: {stock_name}")
