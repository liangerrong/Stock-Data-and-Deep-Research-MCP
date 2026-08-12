import json
import os
import tempfile
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from src.core.yfinance_client import (
    fetch_hk_market_snapshot,
    fetch_hk_financial_history,
    search_hk_stock_code,
    _akshare_code_to_yf,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ticker_mock(info=None, financials=None, balance_sheet=None, cashflow=None):
    """Return a MagicMock that behaves like yf.Ticker(...)."""
    ticker_instance = MagicMock()
    ticker_instance.info = info or {}
    ticker_instance.financials = financials if financials is not None else pd.DataFrame()
    ticker_instance.balance_sheet = balance_sheet if balance_sheet is not None else pd.DataFrame()
    ticker_instance.cashflow = cashflow if cashflow is not None else pd.DataFrame()
    return ticker_instance


def _make_financial_table(columns=None, index=None):
    """Create a small financial DataFrame in yfinance orientation (columns=periods, index=items)."""
    if columns is None:
        columns = pd.to_datetime(["2023-12-31", "2022-12-31", "2021-12-31"])
    if index is None:
        index = ["TotalRevenue", "NetIncome"]
    data = {col: [float(i * 100) for i in range(len(index))] for col in columns}
    return pd.DataFrame(data, index=index)


# ---------------------------------------------------------------------------
# fetch_hk_market_snapshot
# ---------------------------------------------------------------------------

class TestFetchHkMarketSnapshot:
    def test_normal(self):
        info = {
            "shortName": "Tencent Holdings",
            "currentPrice": 345.0,
            "sharesOutstanding": 9_500_000_000,
            "currency": "HKD",
        }
        ticker_mock = _make_ticker_mock(info=info)

        with patch("src.core.yfinance_client.yf.Ticker", return_value=ticker_mock):
            result = fetch_hk_market_snapshot("0700.HK")

        assert result["stock_code"] == "0700.HK"
        assert result["stock_name"] == "Tencent Holdings"
        assert result["current_price"] == 345.0
        assert result["circulating_shares"] == 9_500_000_000
        assert result["currency"] == "HKD"

    def test_empty_info_raises(self):
        ticker_mock = _make_ticker_mock(info={})
        with patch("src.core.yfinance_client.yf.Ticker", return_value=ticker_mock):
            with pytest.raises(ValueError, match="No data returned"):
                fetch_hk_market_snapshot("INVALID.HK")

    def test_price_fallback_to_regular_market_price(self):
        info = {
            "shortName": "HSBC",
            "regularMarketPrice": 62.5,
            "sharesOutstanding": 20_000_000_000,
            "currency": "HKD",
        }
        ticker_mock = _make_ticker_mock(info=info)
        with patch("src.core.yfinance_client.yf.Ticker", return_value=ticker_mock):
            result = fetch_hk_market_snapshot("0005.HK")

        assert result["current_price"] == 62.5

    def test_missing_optional_fields_use_defaults(self):
        info = {"shortName": "SomeStock"}
        ticker_mock = _make_ticker_mock(info=info)
        with patch("src.core.yfinance_client.yf.Ticker", return_value=ticker_mock):
            result = fetch_hk_market_snapshot("9999.HK")

        assert result["current_price"] == 0.0
        assert result["circulating_shares"] == 0.0
        assert result["currency"] == "HKD"


# ---------------------------------------------------------------------------
# fetch_hk_financial_history
# ---------------------------------------------------------------------------

class TestFetchHkFinancialHistory:
    def _default_ticker_mock(self, years=3):
        fin = _make_financial_table()
        bal = _make_financial_table(index=["TotalAssets", "TotalLiabilities"])
        cf = _make_financial_table(index=["OperatingCashFlow"])
        return _make_ticker_mock(financials=fin, balance_sheet=bal, cashflow=cf)

    def test_normal(self):
        ticker_mock = self._default_ticker_mock()
        with patch("src.core.yfinance_client.yf.Ticker", return_value=ticker_mock):
            df = fetch_hk_financial_history("0700.HK", years=3)

        assert "报告日" in df.columns
        assert len(df) <= 3
        # Should have columns from all three tables
        assert "TotalRevenue" in df.columns
        assert "TotalAssets" in df.columns
        assert "OperatingCashFlow" in df.columns

    def test_all_empty_raises(self):
        ticker_mock = _make_ticker_mock()
        with patch("src.core.yfinance_client.yf.Ticker", return_value=ticker_mock):
            with pytest.raises(ValueError, match="Could not find financial report data"):
                fetch_hk_financial_history("EMPTY.HK")

    def test_years_truncation(self):
        # 3-column table; request only 1 year
        fin = _make_financial_table()
        ticker_mock = _make_ticker_mock(financials=fin)
        with patch("src.core.yfinance_client.yf.Ticker", return_value=ticker_mock):
            df = fetch_hk_financial_history("0700.HK", years=1)

        assert len(df) == 1

    def test_partial_table_missing(self):
        # Only financials available, balance_sheet and cashflow empty
        fin = _make_financial_table()
        ticker_mock = _make_ticker_mock(financials=fin)
        with patch("src.core.yfinance_client.yf.Ticker", return_value=ticker_mock):
            df = fetch_hk_financial_history("0700.HK", years=3)

        assert "报告日" in df.columns
        assert "TotalRevenue" in df.columns


# ---------------------------------------------------------------------------
# _akshare_code_to_yf
# ---------------------------------------------------------------------------

class TestAkshareCodeToYf:
    def test_standard_5digit(self):
        assert _akshare_code_to_yf("00700") == "0700.HK"

    def test_4digit(self):
        assert _akshare_code_to_yf("0005") == "0005.HK"

    def test_leading_zeros_strip_and_pad(self):
        assert _akshare_code_to_yf("00001") == "0001.HK"

    def test_short_code(self):
        # single non-zero digit should still pad to 4
        assert _akshare_code_to_yf("1") == "0001.HK"

    def test_all_zeros(self):
        assert _akshare_code_to_yf("000") == "0000.HK"


# ---------------------------------------------------------------------------
# search_hk_stock_code
# ---------------------------------------------------------------------------

class TestSearchHkStockCode:
    def test_exact_match_from_cache(self):
        cache = {"腾讯控股": "0700.HK", "汇丰控股": "0005.HK"}
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read = lambda: json.dumps(cache)
            with patch("src.core.yfinance_client.json.load", return_value=cache):
                result = search_hk_stock_code("腾讯控股")
        assert result == "0700.HK"

    def test_partial_match_from_cache(self):
        cache = {"腾讯控股有限公司": "0700.HK"}
        with patch("os.path.exists", return_value=True), \
             patch("src.core.yfinance_client.json.load", return_value=cache), \
             patch("builtins.open", create=True):
            result = search_hk_stock_code("腾讯")
        assert result == "0700.HK"

    def test_not_found_raises(self):
        cache = {"腾讯控股": "0700.HK"}
        with patch("os.path.exists", return_value=True), \
             patch("src.core.yfinance_client.json.load", return_value=cache), \
             patch("builtins.open", create=True):
            with pytest.raises(ValueError, match="Could not find HK stock"):
                search_hk_stock_code("XXXX不存在")

    def test_no_cache_searches_yfinance_and_saves(self):
        """When cache is absent, use yfinance Search and persist the match."""
        with patch("src.core.yfinance_client._load_hk_cache", return_value=None), \
             patch("src.core.yfinance_client._search_yfinance", return_value="0700.HK") as mock_search, \
             patch("src.core.yfinance_client._save_hk_cache") as mock_save:
            result = search_hk_stock_code("腾讯控股")

        mock_search.assert_called_once_with("腾讯控股")
        mock_save.assert_called_once_with({"腾讯控股": "0700.HK"})
        assert result == "0700.HK"
