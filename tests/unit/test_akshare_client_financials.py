import pytest
from unittest.mock import patch
import pandas as pd
from src.core.akshare_client import fetch_market_snapshot, fetch_financial_history

@pytest.fixture
def individual_info_data():
    return pd.DataFrame({
        "公司简称": ["贵州茅台"],
        "流通股本": [1256000000.0]
    })

@pytest.fixture
def hist_data():
    return pd.DataFrame({
        "日期": ["2024-01-01"],
        "收盘": [1500.0]
    })

@pytest.fixture
def financial_indicator_data():
    return pd.DataFrame({
        "日期": ["2023-12-31", "2022-12-31"],
        "净利润(元)": [1000000000.0, 900000000.0],
        "营业总收入(元)": [2000000000.0, 1800000000.0]
    })

@patch("src.core.akshare_client.ak.stock_zh_a_hist")
@patch("src.core.akshare_client.ak.stock_profile_cninfo")
def test_fetch_market_snapshot(mock_info_em, mock_hist, individual_info_data, hist_data):
    mock_info_em.return_value = individual_info_data
    mock_hist.return_value = hist_data
    
    snapshot = fetch_market_snapshot("600519")
    
    assert snapshot["stock_code"] == "600519"
    assert snapshot["stock_name"] == "贵州茅台"
    assert snapshot["current_price"] == 1500.0
    assert snapshot["circulating_shares"] == 1256000000.0

@patch("src.core.akshare_client.ak.stock_financial_report_sina")
def test_fetch_financial_history(mock_report_sina):
    # Create two dummy dataframes to represent the assets and income reports
    df_assets = pd.DataFrame({
        "报告日": ["20231231", "20221231", "20230630"],
        "总资产": [1000, 900, 950]
    })
    
    df_income = pd.DataFrame({
        "报告日": ["20231231", "20221231"],
        "净利润": [100, 90]
    })
    
    # Simulate API returning different dataframe based on the report type requested
    def side_effect(*args, **kwargs):
        symbol = kwargs.get('symbol')
        if symbol == '资产负债表':
            return df_assets
        elif symbol == '利润表':
            return df_income
        else:
            return pd.DataFrame()  # Empty dataframe for cashflow to test missing data handling
            
    mock_report_sina.side_effect = side_effect
    
    df = fetch_financial_history("600519", years=2)
    
    # We should only get the 1231 items, and there are 2 years
    assert len(df) == 2
    assert "总资产" in df.columns
    assert "净利润" in df.columns
    # Verify that the non-1231 report was filtered out
    assert "20230630" not in df['报告日'].values
    assert mock_report_sina.call_count == 3  # Called for the 3 distinct report types
