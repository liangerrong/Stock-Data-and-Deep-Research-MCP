import os
import tempfile
import pytest
import pandas as pd
from unittest.mock import patch
from src.tools.get_financials import handle_get_financials


@pytest.fixture
def hk_snapshot():
    return {
        "stock_code": "0700.HK",
        "stock_name": "Tencent Holdings",
        "current_price": 345.0,
        "circulating_shares": 9_500_000_000,
        "currency": "HKD",
    }


@pytest.fixture
def hk_financials():
    return pd.DataFrame({
        "报告日": ["2023-12-31", "2022-12-31"],
        "TotalRevenue": [609015000000, 554552000000],
        "NetIncome": [115216000000, 188243000000],
        "TotalAssets": [1966459000000, 1800000000000],
    })


@patch("src.tools.get_financials.fetch_hk_market_snapshot")
@patch("src.tools.get_financials.fetch_hk_financial_history")
@patch("src.tools.get_financials.fetch_hk_latest_quarterly_report", return_value=None)
def test_hk_normal_writes_file(mock_quarterly, mock_fin, mock_snap, hk_snapshot, hk_financials):
    mock_snap.return_value = hk_snapshot
    mock_fin.return_value = hk_financials

    with tempfile.TemporaryDirectory() as tmpdir:
        result = handle_get_financials("0700.HK", years=2, output_dir=tmpdir)

        assert "Data saved successfully" in result
        assert "financial_data.md" in result

        files = os.listdir(tmpdir)
        assert len(files) == 1
        assert "0700.HK_financial_data.md" in files[0] or "0700.HK" in files[0]

        # Check file contains both Markdown sections
        md_file = os.path.join(tmpdir, files[0])
        content = open(md_file, encoding="utf-8").read()
        assert "# Market Snapshot" in content
        assert "# Annual Financial History" in content


@patch("src.tools.get_financials.fetch_hk_market_snapshot")
@patch("src.tools.get_financials.fetch_hk_financial_history")
@patch("src.tools.get_financials.fetch_hk_latest_quarterly_report", return_value=None)
def test_hk_lowercase_ticker_auto_upper(mock_quarterly, mock_fin, mock_snap, hk_snapshot, hk_financials):
    """Lowercase '.hk' should be normalised to '.HK' before calling fetch functions."""
    mock_snap.return_value = hk_snapshot
    mock_fin.return_value = hk_financials

    with tempfile.TemporaryDirectory() as tmpdir:
        result = handle_get_financials("0700.hk", years=2, output_dir=tmpdir)

    assert "Data saved successfully" in result
    mock_snap.assert_called_once()
    mock_fin.assert_called_once()


@patch("src.tools.get_financials.fetch_hk_market_snapshot")
@patch("src.tools.get_financials.fetch_hk_financial_history")
@patch("src.tools.get_financials.fetch_hk_latest_quarterly_report", return_value=None)
def test_hk_snapshot_error_returns_error_string(mock_quarterly, mock_fin, mock_snap):
    mock_snap.side_effect = ValueError("No data returned from yfinance for ticker: BAD.HK")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = handle_get_financials("BAD.HK", years=2, output_dir=tmpdir)

    assert "Error fetching financial data" in result
    # financials should NOT be called if snapshot fails
    mock_fin.assert_not_called()


@patch("src.tools.get_financials.fetch_market_snapshot")
@patch("src.tools.get_financials.fetch_financial_history")
@patch("src.tools.get_financials.fetch_latest_quarterly_report", return_value=None)
@patch("src.tools.get_financials.fetch_hk_market_snapshot")
@patch("src.tools.get_financials.fetch_hk_financial_history")
@patch("src.tools.get_financials.fetch_hk_latest_quarterly_report")
def test_cn_stock_does_not_call_hk_functions(
    mock_hk_quarterly, mock_hk_fin, mock_hk_snap,
    mock_cn_quarterly, mock_cn_fin, mock_cn_snap
):
    """Passing an A-share code must not invoke any HK functions."""
    mock_cn_snap.return_value = {
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "current_price": 1500.0,
        "circulating_shares": 1_256_000_000,
    }
    mock_cn_fin.return_value = pd.DataFrame({
        "报告日": ["20231231"],
        "总资产": [100],
    })

    with tempfile.TemporaryDirectory() as tmpdir:
        result = handle_get_financials("600519", years=1, output_dir=tmpdir)

    assert "Data saved successfully" in result
    mock_hk_snap.assert_not_called()
    mock_hk_fin.assert_not_called()
    mock_hk_quarterly.assert_not_called()
    mock_cn_snap.assert_called_once()
    mock_cn_fin.assert_called_once()
