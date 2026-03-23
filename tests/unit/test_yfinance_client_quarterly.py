import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from src.core.yfinance_client import fetch_hk_latest_quarterly_report


def _make_quarterly_table(index=None):
    """Create a small quarterly financial DataFrame in yfinance orientation."""
    columns = pd.to_datetime(["2024-09-30", "2024-06-30", "2024-03-31", "2023-12-31"])
    if index is None:
        index = ["TotalRevenue", "NetIncome"]
    data = {col: [float((i + 1) * 100) for i in range(len(index))] for col in columns}
    return pd.DataFrame(data, index=index)


class TestFetchHkLatestQuarterlyReport:
    def test_normal_returns_latest_quarter(self):
        qf = _make_quarterly_table()
        qb = _make_quarterly_table(index=["TotalAssets", "TotalLiabilities"])
        qc = _make_quarterly_table(index=["OperatingCashFlow"])

        ticker_mock = MagicMock()
        ticker_mock.quarterly_financials = qf
        ticker_mock.quarterly_balance_sheet = qb
        ticker_mock.quarterly_cashflow = qc

        with patch("src.core.yfinance_client.yf.Ticker", return_value=ticker_mock):
            df = fetch_hk_latest_quarterly_report("0700.HK")

        assert df is not None
        assert len(df) == 1
        assert "报告日" in df.columns
        assert "TotalRevenue" in df.columns
        assert "TotalAssets" in df.columns
        assert "OperatingCashFlow" in df.columns

    def test_all_empty_returns_none(self):
        ticker_mock = MagicMock()
        ticker_mock.quarterly_financials = pd.DataFrame()
        ticker_mock.quarterly_balance_sheet = pd.DataFrame()
        ticker_mock.quarterly_cashflow = pd.DataFrame()

        with patch("src.core.yfinance_client.yf.Ticker", return_value=ticker_mock):
            df = fetch_hk_latest_quarterly_report("EMPTY.HK")

        assert df is None

    def test_partial_tables_available(self):
        """Only quarterly financials available, others empty."""
        qf = _make_quarterly_table()

        ticker_mock = MagicMock()
        ticker_mock.quarterly_financials = qf
        ticker_mock.quarterly_balance_sheet = pd.DataFrame()
        ticker_mock.quarterly_cashflow = pd.DataFrame()

        with patch("src.core.yfinance_client.yf.Ticker", return_value=ticker_mock):
            df = fetch_hk_latest_quarterly_report("0700.HK")

        assert df is not None
        assert len(df) == 1
        assert "TotalRevenue" in df.columns
