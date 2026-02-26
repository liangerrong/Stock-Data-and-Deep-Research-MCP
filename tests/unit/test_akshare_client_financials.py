import pytest
from unittest.mock import patch
import pandas as pd
from src.core.akshare_client import fetch_market_snapshot, fetch_financial_history

@pytest.fixture
def spot_em_data():
    return pd.DataFrame({
        "代码": ["600519", "000001"],
        "名称": ["贵州茅台", "平安银行"],
        "最新价": [1500.0, 10.0],
        "流通股本": [1256000000.0, 19400000000.0]
    })

@pytest.fixture
def financial_indicator_data():
    return pd.DataFrame({
        "日期": ["2023-12-31", "2022-12-31"],
        "净利润(元)": [1000000000.0, 900000000.0],
        "营业总收入(元)": [2000000000.0, 1800000000.0]
    })

@patch("src.core.akshare_client.ak.stock_zh_a_spot_em")
def test_fetch_market_snapshot(mock_spot_em, spot_em_data):
    mock_spot_em.return_value = spot_em_data
    snapshot = fetch_market_snapshot("600519")
    
    assert snapshot["stock_code"] == "600519"
    assert snapshot["stock_name"] == "贵州茅台"
    assert snapshot["current_price"] == 1500.0
    assert snapshot["circulating_shares"] == 1256000000.0

@patch("src.core.akshare_client.ak.stock_financial_analysis_indicator")
def test_fetch_financial_history(mock_indicator, financial_indicator_data):
    mock_indicator.return_value = financial_indicator_data
    df = fetch_financial_history("600519", years=2)
    
    assert len(df) == 2
    assert "净利润(元)" in df.columns
    mock_indicator.assert_called_once()
