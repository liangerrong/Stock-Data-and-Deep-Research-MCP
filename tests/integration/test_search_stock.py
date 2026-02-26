import pytest
from unittest.mock import patch
from src.tools.search_stock import handle_search_stock

@patch("src.tools.search_stock.search_stock_code")
def test_handle_search_stock_success(mock_search):
    mock_search.return_value = "600519"
    
    result = handle_search_stock("贵州茅台")
    
    assert "600519" in result
    assert "贵州茅台" in result

@patch("src.tools.search_stock.search_stock_code")
def test_handle_search_stock_failure(mock_search):
    mock_search.side_effect = ValueError("Could not find stock name matching: 不存在的公司")
    
    result = handle_search_stock("不存在的公司")
    
    assert "Error" in result
    assert "不存在的公司" in result
