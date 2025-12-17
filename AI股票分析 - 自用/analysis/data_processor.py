"""
数据处理模块
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional


class DataProcessor:
    """数据处理类"""
    
    @staticmethod
    def calculate_metrics(df: pd.DataFrame) -> Dict:
        """
        计算技术指标
        
        Args:
            df: 股票数据DataFrame
        
        Returns:
            包含各种指标的字典
        """
        if df is None or df.empty:
            return {}
        
        metrics = {}
        
        # 确定列名（akshare可能使用不同列名）
        close_col = None
        open_col = None
        high_col = None
        low_col = None
        volume_col = None
        
        for col in df.columns:
            col_lower = col.lower()
            if '收盘' in col or 'close' in col_lower:
                close_col = col
            elif '开盘' in col or 'open' in col_lower:
                open_col = col
            elif '最高' in col or 'high' in col_lower:
                high_col = col
            elif '最低' in col or 'low' in col_lower:
                low_col = col
            elif '成交量' in col or 'volume' in col_lower:
                volume_col = col
        
        if close_col is None:
            return metrics
        
        close_prices = df[close_col]
        
        # 基本统计
        metrics['最新收盘价'] = float(close_prices.iloc[-1])
        metrics['最高价'] = float(close_prices.max())
        metrics['最低价'] = float(close_prices.min())
        metrics['平均收盘价'] = float(close_prices.mean())
        
        # 涨跌幅
        if len(close_prices) > 1:
            start_price = close_prices.iloc[0]
            end_price = close_prices.iloc[-1]
            change = end_price - start_price
            change_pct = (change / start_price) * 100
            metrics['期间涨跌'] = float(change)
            metrics['期间涨跌幅(%)'] = float(change_pct)
        
        # 最大涨幅和最大回撤
        if len(close_prices) > 1:
            # 计算每日涨跌幅
            daily_returns = close_prices.pct_change().dropna()
            if len(daily_returns) > 0:
                metrics['最大单日涨幅(%)'] = float(daily_returns.max() * 100)
                metrics['最大单日跌幅(%)'] = float(daily_returns.min() * 100)
            
            # 计算最大回撤
            cumulative = (1 + daily_returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            metrics['最大回撤(%)'] = float(drawdown.min() * 100)
            
            # 计算最大涨幅（从最低点到最高点）
            max_price_idx = close_prices.idxmax()
            min_price_idx = close_prices.loc[:max_price_idx].idxmin() if max_price_idx in close_prices.index else None
            if min_price_idx is not None and min_price_idx < max_price_idx:
                max_gain = ((close_prices.loc[max_price_idx] - close_prices.loc[min_price_idx]) / 
                           close_prices.loc[min_price_idx]) * 100
                metrics['最大涨幅(%)'] = float(max_gain)
        
        # 波动率（年化）
        if len(close_prices) > 1:
            daily_returns = close_prices.pct_change().dropna()
            if len(daily_returns) > 0:
                volatility = daily_returns.std() * np.sqrt(252)  # 年化波动率
                metrics['年化波动率(%)'] = float(volatility * 100)
        
        # 成交量统计
        if volume_col:
            volumes = df[volume_col]
            metrics['平均成交量'] = float(volumes.mean())
            metrics['最大成交量'] = float(volumes.max())
            metrics['最新成交量'] = float(volumes.iloc[-1])
        
        return metrics
    
    @staticmethod
    def compare_stocks(stock_data_list: List[Dict]) -> pd.DataFrame:
        """
        多股票对比
        
        Args:
            stock_data_list: 股票数据列表，每个元素包含 {'name': str, 'code': str, 'data': pd.DataFrame}
        
        Returns:
            对比表格DataFrame
        """
        comparison_data = []
        
        for stock_info in stock_data_list:
            name = stock_info.get('name', '')
            code = stock_info.get('code', '')
            df = stock_info.get('data')
            
            if df is None or df.empty:
                continue
            
            metrics = DataProcessor.calculate_metrics(df)
            
            row = {
                '股票名称': name,
                '股票代码': code,
                **metrics
            }
            comparison_data.append(row)
        
        if not comparison_data:
            return pd.DataFrame()
        
        return pd.DataFrame(comparison_data)
    
    @staticmethod
    def get_trend_analysis(df: pd.DataFrame) -> Dict:
        """
        趋势分析
        
        Args:
            df: 股票数据DataFrame
        
        Returns:
            趋势分析结果字典
        """
        if df is None or df.empty:
            return {}
        
        # 确定收盘价列
        close_col = None
        for col in df.columns:
            if '收盘' in col or 'close' in col.lower():
                close_col = col
                break
        
        if close_col is None:
            return {}
        
        close_prices = df[close_col]
        
        trend = {
            '趋势方向': '横盘',
            '趋势强度': '弱',
            '描述': ''
        }
        
        if len(close_prices) < 2:
            return trend
        
        # 简单线性回归判断趋势
        x = np.arange(len(close_prices))
        y = close_prices.values
        
        # 计算斜率
        slope = np.polyfit(x, y, 1)[0]
        
        # 计算R²
        y_pred = np.polyval(np.polyfit(x, y, 1), x)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        # 判断趋势
        price_change_pct = ((close_prices.iloc[-1] - close_prices.iloc[0]) / close_prices.iloc[0]) * 100
        
        if slope > 0:
            trend['趋势方向'] = '上涨'
        elif slope < 0:
            trend['趋势方向'] = '下跌'
        else:
            trend['趋势方向'] = '横盘'
        
        if abs(r_squared) > 0.7:
            trend['趋势强度'] = '强'
        elif abs(r_squared) > 0.4:
            trend['趋势强度'] = '中'
        else:
            trend['趋势强度'] = '弱'
        
        trend['描述'] = f"期间涨跌幅 {price_change_pct:+.2f}%，趋势{trend['趋势方向']}，强度{trend['趋势强度']}"
        
        return trend
    
    @staticmethod
    def summarize_data(df: pd.DataFrame) -> Dict:
        """
        数据摘要
        
        Args:
            df: 股票数据DataFrame
        
        Returns:
            数据摘要字典
        """
        if df is None or df.empty:
            return {}
        
        summary = {
            '数据条数': len(df),
            '列名': list(df.columns)
        }
        
        # 确定日期列
        date_col = None
        for col in df.columns:
            if '日期' in col or 'date' in col.lower():
                date_col = col
                break
        
        if date_col:
            summary['起始日期'] = str(df[date_col].min())
            summary['结束日期'] = str(df[date_col].max())
        
        return summary


# 创建全局实例
data_processor = DataProcessor()

