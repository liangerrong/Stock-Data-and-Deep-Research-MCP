import os
import tempfile
import pytest
import pandas as pd
from unittest.mock import patch
from src.tools.get_financials import handle_get_financials


@pytest.fixture
def quarterly_df():
    return pd.DataFrame({
        "报告日": ["20240930"],
        "总资产": [1100],
        "净利润": [120],
    })


@pytest.fixture
def annual_df():
    return pd.DataFrame({
        "报告日": ["20231231", "20221231"],
        "总资产": [1000, 900],
        "净利润": [100, 90],
    })


@pytest.fixture
def snapshot():
    return {
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "current_price": 1500.0,
        "circulating_shares": 1256000000.0,
    }


class TestQuarterlyReportIntegration:
    @patch("src.tools.get_financials.fetch_market_snapshot")
    @patch("src.tools.get_financials.fetch_financial_history")
    @patch("src.tools.get_financials.fetch_latest_quarterly_report")
    def test_quarterly_section_appears_before_annual(
        self, mock_quarterly, mock_annual, mock_snapshot,
        snapshot, quarterly_df, annual_df
    ):
        mock_snapshot.return_value = snapshot
        mock_annual.return_value = annual_df
        mock_quarterly.return_value = quarterly_df

        with tempfile.TemporaryDirectory() as tmpdir:
            result = handle_get_financials("600519", years=3, output_dir=tmpdir)

            assert "Data saved successfully" in result

            # Read the file and verify section ordering
            files = os.listdir(tmpdir)
            assert len(files) == 1
            md_file = os.path.join(tmpdir, files[0])
            content = open(md_file, encoding="utf-8").read()

            # Quarterly section should appear before Annual section
            snapshot_pos = content.find("# Market Snapshot")
            quarterly_pos = content.find("# Latest Quarterly Report")
            annual_pos = content.find("# Annual Financial History")

            assert snapshot_pos >= 0
            assert quarterly_pos >= 0
            assert annual_pos >= 0
            # Order: Snapshot -> Quarterly -> Annual
            assert snapshot_pos < quarterly_pos < annual_pos

    @patch("src.tools.get_financials.fetch_market_snapshot")
    @patch("src.tools.get_financials.fetch_financial_history")
    @patch("src.tools.get_financials.fetch_latest_quarterly_report")
    def test_quarterly_none_still_produces_valid_output(
        self, mock_quarterly, mock_annual, mock_snapshot,
        snapshot, annual_df
    ):
        """When quarterly returns None, the file should still be valid without that section."""
        mock_snapshot.return_value = snapshot
        mock_annual.return_value = annual_df
        mock_quarterly.return_value = None

        with tempfile.TemporaryDirectory() as tmpdir:
            result = handle_get_financials("600519", years=3, output_dir=tmpdir)

            assert "Data saved successfully" in result

            files = os.listdir(tmpdir)
            md_file = os.path.join(tmpdir, files[0])
            content = open(md_file, encoding="utf-8").read()

            assert "# Market Snapshot" in content
            assert "# Annual Financial History" in content
            # Quarterly section should not be present
            assert "# Latest Quarterly Report" not in content


class TestHkQuarterlyReportIntegration:
    @patch("src.tools.get_financials.fetch_hk_market_snapshot")
    @patch("src.tools.get_financials.fetch_hk_financial_history")
    @patch("src.tools.get_financials.fetch_hk_latest_quarterly_report")
    def test_hk_quarterly_section_appears_before_annual(
        self, mock_quarterly, mock_annual, mock_snapshot
    ):
        mock_snapshot.return_value = {
            "stock_code": "0700.HK",
            "stock_name": "Tencent Holdings",
            "current_price": 345.0,
            "circulating_shares": 9_500_000_000,
            "currency": "HKD",
        }
        mock_annual.return_value = pd.DataFrame({
            "报告日": ["2023-12-31", "2022-12-31"],
            "TotalRevenue": [609015000000, 554552000000],
        })
        mock_quarterly.return_value = pd.DataFrame({
            "报告日": ["2024-09-30"],
            "TotalRevenue": [167200000000],
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            result = handle_get_financials("0700.HK", years=2, output_dir=tmpdir)

            assert "Data saved successfully" in result

            files = os.listdir(tmpdir)
            md_file = os.path.join(tmpdir, files[0])
            content = open(md_file, encoding="utf-8").read()

            quarterly_pos = content.find("# Latest Quarterly Report")
            annual_pos = content.find("# Annual Financial History")
            assert quarterly_pos >= 0
            assert annual_pos >= 0
            assert quarterly_pos < annual_pos
