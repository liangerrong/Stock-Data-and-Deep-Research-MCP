import pytest
from unittest.mock import patch
import pandas as pd
from src.core.akshare_client import search_stock_code

@pytest.fixture
def spot_em_data():
    return pd.DataFrame({
        "代码": ["600519", "000001", "601398"],
        "名称": ["贵州茅台", "平安银行", "工商银行"],
    })

@patch("src.core.akshare_client.ak.stock_zh_a_spot_em")
def test_search_stock_code_exact(mock_spot_em, spot_em_data):
    mock_spot_em.return_value = spot_em_data
    code = search_stock_code("贵州茅台")
    assert code == "600519"

@patch("src.core.akshare_client.ak.stock_zh_a_spot_em")
def test_search_stock_code_partial(mock_spot_em, spot_em_data):
    mock_spot_em.return_value = spot_em_data
    code = search_stock_code("平安")
    assert code == "000001"

@patch("src.core.akshare_client.ak.stock_zh_a_spot_em")
def test_search_stock_code_not_found(mock_spot_em, spot_em_data):
    mock_spot_em.return_value = spot_em_data
    with pytest.raises(ValueError):
        search_stock_code("不存在的公司")
