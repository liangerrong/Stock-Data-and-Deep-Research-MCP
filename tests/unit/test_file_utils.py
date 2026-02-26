import os
import tempfile
import pandas as pd
import pytest
from src.utils.file_utils import save_dataframe_to_markdown, save_dataframe_to_csv

@pytest.fixture
def sample_df():
    data = {"col1": [1, 2], "col2": [3, 4]}
    return pd.DataFrame(data)

def test_save_dataframe_to_markdown(sample_df):
    with tempfile.TemporaryDirectory() as tmpdirname:
        filepath = os.path.join(tmpdirname, "test.md")
        result_path = save_dataframe_to_markdown(sample_df, filepath)
        
        assert result_path == filepath
        assert os.path.exists(filepath)
        
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            assert "col1" in content
            assert "col2" in content
            assert "1" in content
            assert "2" in content

def test_save_dataframe_to_csv(sample_df):
    with tempfile.TemporaryDirectory() as tmpdirname:
        filepath = os.path.join(tmpdirname, "test.csv")
        result_path = save_dataframe_to_csv(sample_df, filepath)
        
        assert result_path == filepath
        assert os.path.exists(filepath)
        
        df_loaded = pd.read_csv(filepath)
        assert len(df_loaded) == 2
        assert "col1" in df_loaded.columns
