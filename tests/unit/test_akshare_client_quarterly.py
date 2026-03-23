import pytest
from unittest.mock import patch
import pandas as pd
from src.core.akshare_client import fetch_latest_quarterly_report


@pytest.fixture
def full_report_data():
    """Simulate data returned by stock_financial_report_sina with mixed report dates."""
    return pd.DataFrame({
        "报告日": [
            "20240930", "20240630", "20240331", "20231231",
            "20230930", "20230630", "20230331", "20221231",
        ],
        "总资产": [1100, 1050, 1020, 1000, 950, 920, 900, 850],
    })


@pytest.fixture
def income_report_data():
    return pd.DataFrame({
        "报告日": [
            "20240930", "20240630", "20240331", "20231231",
            "20230930",
        ],
        "净利润": [120, 110, 90, 100, 95],
    })


class TestFetchLatestQuarterlyReport:
    @patch("src.core.akshare_client.ak.stock_financial_report_sina")
    def test_returns_latest_quarterly_row(self, mock_report, full_report_data, income_report_data):
        """Should return only the single most recent quarterly (non-annual) report."""
        def side_effect(*args, **kwargs):
            symbol = kwargs.get("symbol")
            if symbol == "资产负债表":
                return full_report_data
            elif symbol == "利润表":
                return income_report_data
            else:
                return pd.DataFrame()

        mock_report.side_effect = side_effect

        df = fetch_latest_quarterly_report("600519")

        # Should have exactly 1 row (the latest quarter)
        assert len(df) == 1
        # The report date should be 20240930 (latest non-1231 date)
        assert df["报告日"].iloc[0] == "20240930"
        # Should have columns from both reports
        assert "总资产" in df.columns
        assert "净利润" in df.columns

    @patch("src.core.akshare_client.ak.stock_financial_report_sina")
    def test_excludes_annual_reports(self, mock_report):
        """Annual reports (ending in 1231) should be excluded from quarterly results."""
        df_annual_only = pd.DataFrame({
            "报告日": ["20231231", "20221231"],
            "总资产": [1000, 900],
        })

        mock_report.return_value = df_annual_only

        df = fetch_latest_quarterly_report("600519")

        assert df is None or df.empty

    @patch("src.core.akshare_client.ak.stock_financial_report_sina")
    def test_all_reports_empty(self, mock_report):
        """Should return None when all API calls return empty data."""
        mock_report.return_value = pd.DataFrame()

        df = fetch_latest_quarterly_report("600519")

        assert df is None or df.empty

    @patch("src.core.akshare_client.ak.stock_financial_report_sina")
    def test_api_exception_returns_none(self, mock_report):
        """Should return None when the API raises an exception."""
        mock_report.side_effect = Exception("Network error")

        df = fetch_latest_quarterly_report("600519")

        assert df is None

    @patch("src.core.akshare_client.ak.stock_financial_report_sina")
    def test_merges_across_report_types(self, mock_report):
        """Columns from different report types should be merged on 报告日."""
        df_assets = pd.DataFrame({
            "报告日": ["20240930", "20231231"],
            "总资产": [1100, 1000],
        })
        df_income = pd.DataFrame({
            "报告日": ["20240930", "20231231"],
            "净利润": [120, 100],
        })
        df_cashflow = pd.DataFrame({
            "报告日": ["20240930", "20231231"],
            "经营现金流": [200, 180],
        })

        def side_effect(*args, **kwargs):
            symbol = kwargs.get("symbol")
            if symbol == "资产负债表":
                return df_assets
            elif symbol == "利润表":
                return df_income
            elif symbol == "现金流量表":
                return df_cashflow
            return pd.DataFrame()

        mock_report.side_effect = side_effect

        df = fetch_latest_quarterly_report("600519")

        assert len(df) == 1
        assert "总资产" in df.columns
        assert "净利润" in df.columns
        assert "经营现金流" in df.columns
        assert df["报告日"].iloc[0] == "20240930"
