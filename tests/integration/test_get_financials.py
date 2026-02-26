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
def financial_indicator_data():
    return pd.DataFrame({
        "日期": ["2023-12-31", "2022-12-31"],
        "净利润(元)": [1000000000.0, 900000000.0]
    })

@patch("src.core.akshare_client.ak.stock_zh_a_spot_em")
@patch("src.core.akshare_client.ak.stock_financial_analysis_indicator")
def test_handle_get_financials(mock_indicator, mock_spot_em, spot_em_data, financial_indicator_data):
    mock_spot_em.return_value = spot_em_data
    mock_indicator.return_value = financial_indicator_data
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch the file utils to save to temporary directory
        with patch("src.tools.get_financials.get_output_dir", return_value=tmpdir):
            result = handle_get_financials("600519", years=3)
            
            assert "Data saved successfully" in result
            assert "600519" in result
            assert "financials" in result
            
            # Check if files were created
            files = os.listdir(tmpdir)
            assert any("600519_market" in f for f in files)
            assert any("600519_financials" in f for f in files)
