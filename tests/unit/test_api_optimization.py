"""Tests verifying that the API call optimization works correctly.

A-shares: fetch_raw_sina_reports() is called once, its result is reused by
          fetch_financial_history() and fetch_latest_quarterly_report().
HK:       A single yf.Ticker instance is shared across all three HK functions.
"""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock, call
from src.core.akshare_client import (
    fetch_raw_sina_reports,
    fetch_financial_history,
    fetch_latest_quarterly_report,
)
from src.core.yfinance_client import (
    create_ticker_obj,
    fetch_hk_market_snapshot,
    fetch_hk_financial_history,
    fetch_hk_latest_quarterly_report,
)


# ---------------------------------------------------------------------------
# A-share: shared raw reports
# ---------------------------------------------------------------------------

class TestFetchRawSinaReports:
    @patch("src.core.akshare_client.ak.stock_financial_report_sina")
    def test_calls_api_exactly_3_times(self, mock_report):
        mock_report.return_value = pd.DataFrame({
            "报告日": ["20240930", "20231231"],
            "总资产": [1100, 1000],
        })

        raw = fetch_raw_sina_reports("600519")

        assert mock_report.call_count == 3
        assert "资产负债表" in raw
        assert "利润表" in raw
        assert "现金流量表" in raw

    @patch("src.core.akshare_client.ak.stock_financial_report_sina")
    def test_partial_api_failure(self, mock_report):
        """If one report type fails, others should still be returned."""
        def side_effect(*args, **kwargs):
            if kwargs.get("symbol") == "现金流量表":
                raise Exception("network error")
            return pd.DataFrame({"报告日": ["20231231"], "col": [1]})

        mock_report.side_effect = side_effect
        raw = fetch_raw_sina_reports("600519")

        assert raw["资产负债表"] is not None
        assert raw["利润表"] is not None
        assert raw["现金流量表"] is None


class TestSharedRawReportsOptimization:
    @patch("src.core.akshare_client.ak.stock_financial_report_sina")
    def test_no_extra_api_calls_when_raw_reports_provided(self, mock_report):
        """When raw_reports is provided, no additional API calls should be made."""
        raw_reports = {
            "资产负债表": pd.DataFrame({
                "报告日": ["20240930", "20231231", "20221231"],
                "总资产": [1100, 1000, 900],
            }),
            "利润表": pd.DataFrame({
                "报告日": ["20240930", "20231231", "20221231"],
                "净利润": [120, 100, 90],
            }),
            "现金流量表": None,
        }

        annual = fetch_financial_history("600519", years=2, raw_reports=raw_reports)
        quarterly = fetch_latest_quarterly_report("600519", raw_reports=raw_reports)

        # API should NOT be called at all
        mock_report.assert_not_called()

        # Annual should have 2 rows (years=2), only 1231 dates
        assert len(annual) == 2
        assert all(str(d).endswith("1231") for d in annual["报告日"])

        # Quarterly should have 1 row, the 0930 date
        assert len(quarterly) == 1
        assert quarterly["报告日"].iloc[0] == "20240930"

    @patch("src.core.akshare_client.ak.stock_financial_report_sina")
    def test_end_to_end_3_api_calls_total(self, mock_report):
        """Full flow: fetch_raw + annual + quarterly = only 3 API calls."""
        mock_report.return_value = pd.DataFrame({
            "报告日": ["20240930", "20231231", "20221231"],
            "总资产": [1100, 1000, 900],
        })

        raw = fetch_raw_sina_reports("600519")
        annual = fetch_financial_history("600519", years=2, raw_reports=raw)
        quarterly = fetch_latest_quarterly_report("600519", raw_reports=raw)

        # Only 3 calls total (in fetch_raw_sina_reports), NOT 6
        assert mock_report.call_count == 3


# ---------------------------------------------------------------------------
# HK: shared Ticker instance
# ---------------------------------------------------------------------------

def _make_financial_table(columns=None, index=None):
    if columns is None:
        columns = pd.to_datetime(["2023-12-31", "2022-12-31"])
    if index is None:
        index = ["TotalRevenue", "NetIncome"]
    data = {col: [float(i * 100) for i in range(len(index))] for col in columns}
    return pd.DataFrame(data, index=index)


def _make_quarterly_table(columns=None, index=None):
    if columns is None:
        columns = pd.to_datetime(["2024-09-30", "2024-06-30"])
    if index is None:
        index = ["TotalRevenue", "NetIncome"]
    data = {col: [float(i * 100) for i in range(len(index))] for col in columns}
    return pd.DataFrame(data, index=index)


class TestSharedTickerOptimization:
    @patch("src.core.yfinance_client.yf.Ticker")
    def test_single_ticker_creation(self, mock_ticker_class):
        """create_ticker_obj should create exactly one Ticker instance."""
        mock_instance = MagicMock()
        mock_instance.info = {
            "shortName": "Tencent",
            "currentPrice": 345.0,
            "sharesOutstanding": 9_500_000_000,
            "currency": "HKD",
        }
        mock_instance.financials = _make_financial_table()
        mock_instance.balance_sheet = _make_financial_table(index=["TotalAssets"])
        mock_instance.cashflow = _make_financial_table(index=["OperatingCashFlow"])
        mock_instance.quarterly_financials = _make_quarterly_table()
        mock_instance.quarterly_balance_sheet = _make_quarterly_table(index=["TotalAssets"])
        mock_instance.quarterly_cashflow = _make_quarterly_table(index=["OperatingCashFlow"])

        mock_ticker_class.return_value = mock_instance

        t = create_ticker_obj("0700.HK")
        snap = fetch_hk_market_snapshot("0700.HK", ticker_obj=t)
        annual = fetch_hk_financial_history("0700.HK", years=2, ticker_obj=t)
        quarterly = fetch_hk_latest_quarterly_report("0700.HK", ticker_obj=t)

        # Ticker class should only be instantiated ONCE
        assert mock_ticker_class.call_count == 1

        # All results should be valid
        assert snap["stock_name"] == "Tencent"
        assert len(annual) <= 2
        assert len(quarterly) == 1
