import os
import pandas as pd

def save_dataframe_to_markdown(df: pd.DataFrame, filepath: str) -> str:
    """
    Saves a Pandas DataFrame to a Markdown file.
    
    Args:
        df: The pandas DataFrame to save.
        filepath: The absolute or relative path to the output Markdown file.
        
    Returns:
        The absolute path to the saved file.
    """
    os.makedirs(os.path.dirname(os.path.abspath(filepath)) or '.', exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(df.to_markdown(index=False))
    return os.path.abspath(filepath)

def save_dataframe_to_csv(df: pd.DataFrame, filepath: str) -> str:
    """
    Saves a Pandas DataFrame to a CSV file.
    
    Args:
        df: The pandas DataFrame to save.
        filepath: The absolute or relative path to the output CSV file.
        
    Returns:
        The absolute path to the saved file.
    """
    os.makedirs(os.path.dirname(os.path.abspath(filepath)) or '.', exist_ok=True)
    df.to_csv(filepath, index=False, encoding='utf-8-sig')
    return os.path.abspath(filepath)
