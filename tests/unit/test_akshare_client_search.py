import os
import json
import tempfile
import pytest
from unittest.mock import patch
import pandas as pd
from src.core.akshare_client import search_stock_code

@pytest.fixture
def stock_info_data():
    return pd.DataFrame({
        "code": ["600519", "000001", "601398"],
        "name": ["贵州茅台", "平安银行", "工商银行"],
    })

@patch("src.core.akshare_client.ak.stock_info_a_code_name")
def test_search_stock_code_no_cache(mock_stock_info, stock_info_data):
    mock_stock_info.return_value = stock_info_data
    
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_cache_file = os.path.join(tmpdir, ".stock_codes_cache.json")
        with patch("src.core.akshare_client.CACHE_FILE", temp_cache_file):
            # First call, should fetch and write cache
            code = search_stock_code("贵州茅台")
            assert code == "600519"
            mock_stock_info.assert_called_once()
            
            # Verify cache file created
            assert os.path.exists(temp_cache_file)
            with open(temp_cache_file, "r", encoding="utf-8") as f:
                mapping = json.load(f)
                assert mapping["贵州茅台"] == "600519"

@patch("src.core.akshare_client.ak.stock_info_a_code_name")
def test_search_stock_code_with_cache(mock_stock_info, stock_info_data):
    mock_stock_info.return_value = stock_info_data
    
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_cache_file = os.path.join(tmpdir, ".stock_codes_cache.json")
        # Pre-seed cache
        with open(temp_cache_file, "w", encoding="utf-8") as f:
            json.dump({"平安银行": "000001", "工商银行": "601398"}, f)
            
        with patch("src.core.akshare_client.CACHE_FILE", temp_cache_file):
            # Exact match, should not call API
            code = search_stock_code("平安银行")
            assert code == "000001"
            mock_stock_info.assert_not_called()
            
            # Partial match, should not call API
            code = search_stock_code("商银")
            assert code == "601398"
            mock_stock_info.assert_not_called()

@patch("src.core.akshare_client.ak.stock_info_a_code_name")
def test_search_stock_code_not_found(mock_stock_info, stock_info_data):
    mock_stock_info.return_value = stock_info_data
    
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_cache_file = os.path.join(tmpdir, ".stock_codes_cache.json")
        with patch("src.core.akshare_client.CACHE_FILE", temp_cache_file):
            with pytest.raises(ValueError):
                search_stock_code("不存在的公司")
