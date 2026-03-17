import os
import tempfile
import pytest
from unittest.mock import patch
import pandas as pd
from src.tools.get_financials import handle_get_financials

@pytest.fixture
def spot_em_data():
    return pd.DataFrame({
        "代码": ["600519"],
        "名称": ["贵州茅台"],
        "最新价": [1500.0],
        "流通股本": [1256000000.0]
    })

@pytest.fixture
def mock_financial_data():
    return pd.DataFrame({
        "报告日": ["20231231", "20221231"],
        "总资产": [1000, 900],
        "净利润": [100, 90]
    })

@patch("src.tools.get_financials.fetch_market_snapshot")
@patch("src.tools.get_financials.fetch_financial_history")
def test_handle_get_financials(mock_financial_history, mock_snapshot, spot_em_data, mock_financial_data):
    # Setup mocks
    mock_snapshot.return_value = {
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "current_price": 1500.0,
        "circulating_shares": 1256000000.0
    }
    mock_financial_history.return_value = mock_financial_data
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch the file utils to save to temporary directory
        with patch("src.tools.get_financials.get_output_dir", return_value=tmpdir):
            result = handle_get_financials("600519", years=3)
            
            assert "Data saved successfully" in result
            assert "financial_data.md" in result
            
            # Check if files were created
            files = os.listdir(tmpdir)
            assert any("600519_financial_data" in f for f in files)
            assert len(files) == 1

@patch("src.tools.get_financials.fetch_market_snapshot")
@patch("src.tools.get_financials.fetch_financial_history")
def test_handle_get_financials_with_output_dir(mock_financial_history, mock_snapshot, spot_em_data, mock_financial_data):
    mock_snapshot.return_value = {
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "current_price": 1500.0,
        "circulating_shares": 1256000000.0
    }
    mock_financial_history.return_value = mock_financial_data
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Pass tmpdir directly as output_dir without patching get_output_dir
        result = handle_get_financials("600519", years=3, output_dir=tmpdir)
        
        assert "Data saved successfully" in result
        
        # Check if files were created in the exact requested directory
        files = os.listdir(tmpdir)
        assert any("600519_financial_data" in f for f in files), f"Expected combined financial_data file in {files}"
        assert len(files) == 1
