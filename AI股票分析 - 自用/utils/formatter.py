"""
报告格式化工具
"""
import pandas as pd


def format_stock_data_summary(df):
    """
    格式化股票数据摘要
    
    Args:
        df: pandas DataFrame，包含股票数据
    
    Returns:
        格式化的字符串
    """
    if df is None or df.empty:
        return "无数据"
    
    summary = []
    summary.append(f"数据条数: {len(df)}")
    
    if '日期' in df.columns or 'date' in df.columns:
        date_col = '日期' if '日期' in df.columns else 'date'
        summary.append(f"起始日期: {df[date_col].min()}")
        summary.append(f"结束日期: {df[date_col].max()}")
    
    if '收盘' in df.columns or 'close' in df.columns:
        close_col = '收盘' if '收盘' in df.columns else 'close'
        summary.append(f"最新收盘价: {df[close_col].iloc[-1]:.2f}")
        if len(df) > 1:
            change = df[close_col].iloc[-1] - df[close_col].iloc[0]
            change_pct = (change / df[close_col].iloc[0]) * 100
            summary.append(f"期间涨跌: {change:+.2f} ({change_pct:+.2f}%)")
    
    return "\n".join(summary)


def format_metrics_table(metrics_dict):
    """
    格式化指标表格
    
    Args:
        metrics_dict: 指标字典
    
    Returns:
        Markdown格式的表格字符串
    """
    if not metrics_dict:
        return "无指标数据"
    
    lines = ["| 指标 | 数值 |", "|------|------|"]
    for key, value in metrics_dict.items():
        if isinstance(value, float):
            value_str = f"{value:.2f}"
        else:
            value_str = str(value)
        lines.append(f"| {key} | {value_str} |")
    
    return "\n".join(lines)


def format_stock_info(stock_name, stock_code):
    """
    格式化股票信息
    
    Args:
        stock_name: 股票名称
        stock_code: 股票代码
    
    Returns:
        格式化的字符串
    """
    return f"**{stock_name}** ({stock_code})"


def format_date_range(start_date, end_date=None):
    """
    格式化日期范围
    
    Args:
        start_date: 开始日期
        end_date: 结束日期（可选）
    
    Returns:
        格式化的字符串
    """
    if end_date:
        return f"{start_date} 至 {end_date}"
    else:
        return f"{start_date}"

