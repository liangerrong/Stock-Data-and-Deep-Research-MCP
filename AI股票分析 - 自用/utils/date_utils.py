"""
日期工具模块
"""
from datetime import datetime, timedelta
import pandas as pd
import akshare as ak


def parse_date(date_str):
    """
    解析日期字符串
    
    Args:
        date_str: 日期字符串，格式如 "2024-06-01" 或 "2024/06/01"
    
    Returns:
        datetime对象
    """
    if isinstance(date_str, datetime):
        return date_str
    
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"]:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"无法解析日期格式: {date_str}")


def format_date(date_obj, fmt="%Y-%m-%d"):
    """
    格式化日期对象
    
    Args:
        date_obj: datetime对象
        fmt: 格式字符串
    
    Returns:
        格式化后的日期字符串
    """
    if isinstance(date_obj, str):
        return date_obj
    return date_obj.strftime(fmt)


def get_prev_trade_date(date_str):
    """
    获取前一交易日
    
    Args:
        date_str: 日期字符串
    
    Returns:
        前一交易日的日期字符串 (YYYY-MM-DD)
    """
    target_date = parse_date(date_str)
    
    # 获取交易日历
    try:
        trade_cal = ak.tool_trade_date_hist_sina()
        trade_cal['trade_date'] = pd.to_datetime(trade_cal['trade_date'])
        
        # 找到目标日期之前的交易日
        prev_dates = trade_cal[trade_cal['trade_date'] < target_date]
        if len(prev_dates) > 0:
            prev_date = prev_dates.iloc[-1]['trade_date']
            return format_date(prev_date)
    except Exception:
        # 如果获取交易日历失败，简单往前推1-3天
        for i in range(1, 4):
            prev_date = target_date - timedelta(days=i)
            if prev_date.weekday() < 5:  # 周一到周五
                return format_date(prev_date)
    
    # 默认返回前一天
    return format_date(target_date - timedelta(days=1))


def calculate_relative_date(relative_str, base_date=None):
    """
    计算相对日期
    
    Args:
        relative_str: 相对日期字符串，如 "最近一年"、"最近一个月"
        base_date: 基准日期，默认为今天
    
    Returns:
        (start_date, end_date) 元组
    """
    if base_date is None:
        base_date = datetime.now()
    elif isinstance(base_date, str):
        base_date = parse_date(base_date)
    
    end_date = base_date
    
    if "一年" in relative_str or "1年" in relative_str:
        start_date = base_date - timedelta(days=365)
    elif "半年" in relative_str or "6个月" in relative_str:
        start_date = base_date - timedelta(days=180)
    elif "三个月" in relative_str or "3个月" in relative_str:
        start_date = base_date - timedelta(days=90)
    elif "一个月" in relative_str or "1个月" in relative_str:
        start_date = base_date - timedelta(days=30)
    elif "一周" in relative_str or "7天" in relative_str:
        start_date = base_date - timedelta(days=7)
    else:
        # 默认最近一年
        start_date = base_date - timedelta(days=365)
    
    return format_date(start_date), format_date(end_date)


def is_trade_date(date_str):
    """
    判断是否为交易日
    
    Args:
        date_str: 日期字符串
    
    Returns:
        bool
    """
    try:
        trade_cal = ak.tool_trade_date_hist_sina()
        date_obj = parse_date(date_str)
        trade_cal['trade_date'] = pd.to_datetime(trade_cal['trade_date'])
        return date_obj in trade_cal['trade_date'].values
    except Exception:
        # 如果无法获取交易日历，简单判断是否为工作日
        date_obj = parse_date(date_str)
        return date_obj.weekday() < 5


def get_current_date(fmt="%Y-%m-%d"):
    """
    获取当前日期
    
    Args:
        fmt: 日期格式，默认为 "YYYY-MM-DD"
    
    Returns:
        当前日期的字符串
    """
    return format_date(datetime.now(), fmt)


def normalize_end_date(end_date, fmt="%Y-%m-%d"):
    """
    规范化结束日期：如果结束日期大于当前日期，则替换为当前日期
    
    Args:
        end_date: 结束日期，可以是字符串或datetime对象
        fmt: 返回格式，默认为 "YYYY-MM-DD"
    
    Returns:
        规范化后的日期字符串
    """
    if end_date is None:
        return get_current_date(fmt)
    
    # 解析日期
    if isinstance(end_date, str):
        end_date_obj = parse_date(end_date)
    elif isinstance(end_date, datetime):
        end_date_obj = end_date
    else:
        return get_current_date(fmt)
    
    # 如果结束日期是未来，替换为今天
    current_date = datetime.now()
    if end_date_obj > current_date:
        return get_current_date(fmt)
    
    # 返回格式化后的日期
    return format_date(end_date_obj, fmt)

