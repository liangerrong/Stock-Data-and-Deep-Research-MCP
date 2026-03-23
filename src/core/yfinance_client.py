import os
import json
import pandas as pd
import yfinance as yf

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
HK_CACHE_FILE = os.path.join(CURRENT_DIR, ".hk_stock_codes_cache.json")


def create_ticker_obj(ticker: str) -> yf.Ticker:
    """Create a yfinance Ticker object."""
    return yf.Ticker(ticker)


def fetch_hk_market_snapshot(ticker: str, ticker_obj: yf.Ticker | None = None) -> dict:
    """
    Fetches the current market snapshot for a HK stock via yfinance.

    Args:
        ticker: The yfinance ticker (e.g., '0700.HK').
        ticker_obj: Optional pre-created yf.Ticker object for sharing requests.

    Returns:
        Dictionary with stock_code, stock_name, current_price, circulating_shares, currency.
    """
    t = ticker_obj if ticker_obj is not None else create_ticker_obj(ticker)
    info = t.info
    if not info:
        raise ValueError(f"No data returned from yfinance for ticker: {ticker}")

    stock_name = info.get("shortName") or info.get("longName") or "N/A"
    current_price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
    circulating_shares = info.get("sharesOutstanding") or 0.0
    currency = info.get("currency") or "HKD"

    return {
        "stock_code": ticker,
        "stock_name": stock_name,
        "current_price": current_price,
        "circulating_shares": circulating_shares,
        "currency": currency,
    }


def fetch_hk_financial_history(ticker: str, years: int = 3, ticker_obj: yf.Ticker | None = None) -> pd.DataFrame:
    """
    Fetches annual financial statements for a HK stock via yfinance.

    Args:
        ticker: The yfinance ticker (e.g., '0700.HK').
        years: Number of recent annual periods to include (default: 3).
        ticker_obj: Optional pre-created yf.Ticker object for sharing requests.

    Returns:
        A pandas DataFrame with merged financials keyed by '报告日'.
    """
    t = ticker_obj if ticker_obj is not None else create_ticker_obj(ticker)
    tables = {
        "income": t.financials,
        "balance": t.balance_sheet,
        "cashflow": t.cashflow,
    }

    merged_df = None

    for name, raw in tables.items():
        if raw is None or raw.empty:
            continue

        # Transpose so rows = periods, columns = line items
        df = raw.T.copy()
        df = df.head(years)

        # Insert '报告日' column (YYYY-MM-DD string)
        df.insert(0, "报告日", df.index.strftime("%Y-%m-%d"))
        df = df.reset_index(drop=True)

        if merged_df is None:
            merged_df = df
        else:
            merged_df = pd.merge(merged_df, df, on="报告日", how="outer", suffixes=("", "_dup"))
            dup_cols = [c for c in merged_df.columns if c.endswith("_dup")]
            merged_df.drop(columns=dup_cols, inplace=True)

    if merged_df is None or merged_df.empty:
        raise ValueError(f"Could not find financial report data for ticker: {ticker}")

    return merged_df


def fetch_hk_latest_quarterly_report(ticker: str, ticker_obj: yf.Ticker | None = None) -> pd.DataFrame | None:
    """
    Fetches the latest quarterly financial report for a HK stock via yfinance.

    Returns only the single most recent quarterly row merged across all three report types.
    Returns None if no quarterly data is available.

    Args:
        ticker: The yfinance ticker (e.g., '0700.HK').
        ticker_obj: Optional pre-created yf.Ticker object for sharing requests.

    Returns:
        A single-row DataFrame with merged quarterly data, or None if unavailable.
    """
    t = ticker_obj if ticker_obj is not None else create_ticker_obj(ticker)
    tables = {
        "income": t.quarterly_financials,
        "balance": t.quarterly_balance_sheet,
        "cashflow": t.quarterly_cashflow,
    }

    merged_df = None

    for name, raw in tables.items():
        if raw is None or raw.empty:
            continue

        # Transpose so rows = periods, columns = line items
        df = raw.T.copy()
        # Take only the latest quarter
        df = df.head(1)

        # Insert '报告日' column (YYYY-MM-DD string)
        df.insert(0, "报告日", df.index.strftime("%Y-%m-%d"))
        df = df.reset_index(drop=True)

        if merged_df is None:
            merged_df = df
        else:
            merged_df = pd.merge(merged_df, df, on="报告日", how="inner", suffixes=("", "_dup"))
            dup_cols = [c for c in merged_df.columns if c.endswith("_dup")]
            merged_df.drop(columns=dup_cols, inplace=True)

    if merged_df is None or merged_df.empty:
        return None

    return merged_df


def _akshare_code_to_yf(raw_code: str) -> str:
    """Convert akshare HK code (e.g. '00700') to yfinance ticker (e.g. '0700.HK')."""
    # Strip leading zeros then re-pad to at least 4 digits
    stripped = raw_code.lstrip("0") or "0"
    padded = stripped.zfill(4)
    return f"{padded}.HK"


def _build_hk_cache() -> dict:
    """Build name->ticker mapping from akshare HK spot data."""
    import akshare as ak  # only imported here to avoid hard dependency
    df = ak.stock_hk_spot_em()
    mapping = {}
    for _, row in df.iterrows():
        name = str(row.get("名称", "")).strip()
        code = str(row.get("代码", "")).strip()
        if name and code:
            mapping[name] = _akshare_code_to_yf(code)
    return mapping


def search_hk_stock_code(stock_name: str) -> str:
    """
    Search for a HK stock yfinance ticker given a full or partial company name.

    Args:
        stock_name: The company name or partial name.

    Returns:
        The yfinance ticker string (e.g., '0700.HK').
    """
    mapping = None
    if os.path.exists(HK_CACHE_FILE):
        try:
            with open(HK_CACHE_FILE, "r", encoding="utf-8") as f:
                mapping = json.load(f)
        except Exception:
            pass

    if mapping is None:
        mapping = _build_hk_cache()
        try:
            with open(HK_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(mapping, f, ensure_ascii=False)
        except Exception:
            pass

    # Exact match
    if stock_name in mapping:
        return mapping[stock_name]

    # Partial match
    for name, ticker in mapping.items():
        if stock_name in name:
            return ticker

    raise ValueError(f"Could not find HK stock name matching: {stock_name}")
