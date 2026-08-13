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
    quote_currency = str(info.get("currency") or "HKD").upper()
    financial_currency = str(info.get("financialCurrency") or "").upper() or "UNRESOLVED"
    shares_outstanding = info.get("sharesOutstanding") or 0.0

    return {
        "stock_code": ticker,
        "stock_name": stock_name,
        "current_price": current_price,
        # Kept for backwards compatibility. Yahoo exposes shares outstanding,
        # not an independently verified free-float share count for HK stocks.
        "circulating_shares": circulating_shares,
        "shares_outstanding": shares_outstanding,
        "share_count_basis": "Yahoo Finance sharesOutstanding; not verified free float",
        "currency": quote_currency,
        "quote_currency": quote_currency,
        "financial_currency": financial_currency,
        "exchange": info.get("exchange") or info.get("fullExchangeName") or "HKG",
        "source_provider": "Yahoo Finance via yfinance",
    }


def fetch_hk_security_metadata(ticker: str, ticker_obj: yf.Ticker | None = None) -> dict:
    """Return market identity and explicitly separated quote/financial currencies."""
    t = ticker_obj if ticker_obj is not None else create_ticker_obj(ticker)
    info = t.info
    if not info:
        raise ValueError(f"No metadata returned from yfinance for ticker: {ticker}")
    return {
        "ticker": ticker,
        "market": "HK",
        "exchange": info.get("exchange") or info.get("fullExchangeName") or "HKG",
        "short_name": info.get("shortName") or "N/A",
        "long_name": info.get("longName") or "N/A",
        "quote_currency": str(info.get("currency") or "HKD").upper(),
        "financial_currency": str(info.get("financialCurrency") or "").upper() or "UNRESOLVED",
        "instrument_type": info.get("quoteType") or "EQUITY",
        "shares_outstanding": info.get("sharesOutstanding") or 0.0,
        "metadata_source": "Yahoo Finance info via yfinance",
    }


def fetch_hk_raw_reports(
    ticker: str,
    quarterly: bool = False,
    ticker_obj: yf.Ticker | None = None,
) -> dict[str, pd.DataFrame]:
    """Return separate HK statements with issuer financial-currency metadata.

    Yahoo's statement tables do not carry a currency column themselves.  The
    currency is therefore inherited from the same security's
    ``info.financialCurrency`` and the inheritance is made explicit in every
    row instead of being silently assumed from the HKD trading currency.
    """
    t = ticker_obj if ticker_obj is not None else create_ticker_obj(ticker)
    info = t.info or {}
    financial_currency = str(info.get("financialCurrency") or "").upper() or "UNRESOLVED"
    if quarterly:
        tables = {
            "资产负债表": t.quarterly_balance_sheet,
            "利润表": t.quarterly_income_stmt,
            "现金流量表": t.quarterly_cashflow,
        }
    else:
        tables = {
            "资产负债表": t.balance_sheet,
            "利润表": t.income_stmt,
            "现金流量表": t.cashflow,
        }

    reports: dict[str, pd.DataFrame] = {}
    for statement, raw in tables.items():
        if raw is None or raw.empty:
            reports[statement] = pd.DataFrame()
            continue
        frame = raw.T.copy()
        frame.insert(0, "报告日", [value.strftime("%Y%m%d") for value in frame.index])
        frame = frame.reset_index(drop=True)
        frame["数据源"] = "Yahoo Finance via yfinance"
        frame["是否审计"] = "未确认"
        frame["公告日期"] = pd.NA
        frame["币种"] = financial_currency
        frame["币种来源"] = "Yahoo Finance info.financialCurrency"
        frame["类型"] = "合并口径未确认"
        reports[statement] = frame
    return reports


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

        # Transpose so rows = periods, columns = line items; keep ALL years so
        # that the completeness filter below (not head(years) here) decides which
        # periods are actually fully populated across all three statement types.
        df = raw.T.copy()

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

    # Drop rows where less than half the data columns are populated.  This
    # removes years that only exist in one statement type (e.g. income-only
    # forward estimates) which would otherwise produce large NaN sections.
    data_cols = [c for c in merged_df.columns if c != "报告日"]
    min_populated = max(1, len(data_cols) // 2)
    completeness = merged_df[data_cols].notna().sum(axis=1)
    merged_df = merged_df[completeness >= min_populated]

    if merged_df.empty:
        raise ValueError(f"Could not find financial report data for ticker: {ticker}")

    merged_df = (
        merged_df.sort_values("报告日", ascending=False)
        .head(years)
        .reset_index(drop=True)
    )
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

        # Insert '报告日' column (YYYY-MM-DD string)
        df.insert(0, "报告日", df.index.strftime("%Y-%m-%d"))
        df = df.reset_index(drop=True)

        if merged_df is None:
            merged_df = df
        else:
            # Use outer join so mismatched quarter dates across tables don't drop rows
            merged_df = pd.merge(merged_df, df, on="报告日", how="outer", suffixes=("", "_dup"))
            dup_cols = [c for c in merged_df.columns if c.endswith("_dup")]
            merged_df.drop(columns=dup_cols, inplace=True)

    if merged_df is None or merged_df.empty:
        return None

    # Among the 4 most recent dates, pick the one with the most populated columns.
    # This avoids selecting a date that only exists in one table (which would
    # produce a mostly-NaN row), preferring a slightly older date with full data.
    data_cols = [c for c in merged_df.columns if c != "报告日"]
    candidates = merged_df.sort_values("报告日", ascending=False).head(4).copy()
    candidates["_completeness"] = candidates[data_cols].notna().sum(axis=1)
    best = (
        candidates.sort_values("_completeness", ascending=False)
        .head(1)
        .drop(columns=["_completeness"])
        .reset_index(drop=True)
    )
    return best


def _akshare_code_to_yf(raw_code: str) -> str:
    """Convert akshare HK code (e.g. '00700') to yfinance ticker (e.g. '0700.HK')."""
    stripped = raw_code.lstrip("0") or "0"
    padded = stripped.zfill(4)
    return f"{padded}.HK"


def _search_yfinance(stock_name: str) -> str | None:
    """
    Search HK stocks via yfinance Search API.
    Returns the first HK ticker found, or None if nothing matches.
    """
    try:
        results = yf.Search(stock_name, max_results=10)
        quotes = results.quotes if hasattr(results, "quotes") else []
        for q in quotes:
            exchange = q.get("exchange", "")
            ticker = q.get("symbol", "")
            # Accept tickers ending in .HK or from HKG/HKE exchange
            if ticker.endswith(".HK") or exchange in ("HKG", "HKE", "HKSE"):
                if not ticker.endswith(".HK"):
                    ticker = ticker + ".HK"
                return ticker
    except Exception:
        pass
    return None


def _load_hk_cache() -> dict | None:
    """Load the local HK name->ticker cache if it exists and is non-empty."""
    if not os.path.exists(HK_CACHE_FILE):
        return None
    try:
        with open(HK_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if data else None
    except Exception:
        return None


def _save_hk_cache(mapping: dict) -> None:
    try:
        with open(HK_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False)
    except Exception:
        pass


def search_hk_stock_code(stock_name: str) -> str:
    """
    Search for a HK stock yfinance ticker given a full or partial company name.

    Strategy:
    1. Check the local cache for an exact or partial name match.
    2. Fall back to yfinance Search API (does not require bulk download).
    3. If a new match is found via yfinance, persist it to the local cache.

    Args:
        stock_name: The company name or partial name (Chinese or English).

    Returns:
        The yfinance ticker string (e.g., '0700.HK').

    Raises:
        ValueError: If no matching HK stock is found.
    """
    mapping = _load_hk_cache() or {}

    # Exact match from cache
    if stock_name in mapping:
        return mapping[stock_name]

    # Partial match from cache
    for name, ticker in mapping.items():
        if stock_name in name or name in stock_name:
            return ticker

    # Cache miss: try yfinance Search (no bulk download, no eastmoney dependency)
    ticker = _search_yfinance(stock_name)
    if ticker:
        # Persist to cache so subsequent calls are instant
        mapping[stock_name] = ticker
        _save_hk_cache(mapping)
        return ticker

    raise ValueError(
        f"Could not find HK stock name matching: '{stock_name}'. "
        "Try using the English name or the 4-digit stock code (e.g. '0700.HK')."
    )
