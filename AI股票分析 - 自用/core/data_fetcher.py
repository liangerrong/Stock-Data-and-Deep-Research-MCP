"""
数据获取模块
"""
import akshare as ak
import pandas as pd
from typing import Optional
import sys
from datetime import datetime
from utils.date_utils import parse_date, format_date, get_prev_trade_date, normalize_end_date
from config.settings import settings


class DataFetcher:
    """数据获取类"""
    
    def __init__(self):
        self.timeout = settings.AKSHARE_TIMEOUT
    
    def fetch_daily_data(self, stock_code: str, start_date: str, end_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        获取日级股票数据
        
        Args:
            stock_code: 股票代码，如 "600519.SH" 或 "600519"
            start_date: 开始日期，格式 "YYYY-MM-DD"
            end_date: 结束日期，格式 "YYYY-MM-DD"，默认为今天
        
        Returns:
            pandas DataFrame，包含日期、开盘、收盘、最高、最低、成交量等
        """
        try:
            # 清理股票代码
            code = stock_code.replace(".SH", "").replace(".SZ", "").strip()
            
            # 解析日期
            start = parse_date(start_date)
            if end_date:
                end = parse_date(end_date)
            else:
                end = datetime.now()
            
            # 规范化结束日期（如果大于今天，替换为今天）
            end_str = normalize_end_date(end, "%Y%m%d")
            end = parse_date(end_str)  # 重新解析以确保一致性
            
            # 格式化开始日期为akshare需要的格式
            start_str = format_date(start, "%Y%m%d")
            
            # 调用akshare获取数据
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",  # 日k线数据，使用"daily"而不是"日k"
                start_date=start_str,
                end_date=end_str,
                adjust=""
            )
            
            if df is None or df.empty:
                return None
            
            # 标准化列名
            if '日期' in df.columns:
                df['日期'] = pd.to_datetime(df['日期'])
            elif 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
            
            return df
            
        except KeyError as e:
            error_msg = f"akshare返回数据格式异常: {str(e)}"
            print(error_msg, file=sys.stderr)
            # 打印调试信息
            print(f"调试信息: code={code}, start={start_str}, end={end_str}", file=sys.stderr)
            return None
        except Exception as e:
            error_msg = f"获取股票数据失败: {str(e)}"
            print(error_msg, file=sys.stderr)
            # 打印调试信息
            print(f"调试信息: code={code}, start={start_str}, end={end_str}", file=sys.stderr)
            # 检查是否是股票代码错误
            if "不存在" in str(e) or "无效" in str(e) or "symbol" in str(e).lower():
                raise ValueError(f"股票代码 {stock_code} ({code}) 无效或不存在")
            # 检查是否是日期错误
            if "date" in str(e).lower() or "日期" in str(e):
                raise ValueError(f"日期范围无效: {start_date} 到 {end_date or '今天'}")
            return None
    
    def fetch_single_date(self, stock_code: str, date: str) -> Optional[pd.DataFrame]:
        """
        获取单日股票数据
        
        Args:
            stock_code: 股票代码
            date: 日期，格式 "YYYY-MM-DD"
        
        Returns:
            pandas DataFrame
        """
        return self.fetch_daily_data(stock_code, date, date)
    
    def fetch_with_prev_day(self, stock_code: str, target_date: str) -> Optional[pd.DataFrame]:
        """
        获取目标日期及前一交易日的数据（用于对比分析）
        
        Args:
            stock_code: 股票代码
            target_date: 目标日期
        
        Returns:
            pandas DataFrame，包含两日数据
        """
        prev_date = get_prev_trade_date(target_date)
        return self.fetch_daily_data(stock_code, prev_date, target_date)
    
    def get_stock_basic_info(self, stock_code: str) -> Optional[dict]:
        """
        获取股票基本信息
        
        Args:
            stock_code: 股票代码
        
        Returns:
            包含股票基本信息的字典
        """
        try:
            code = stock_code.replace(".SH", "").replace(".SZ", "").strip()
            # 这里可以调用akshare的其他接口获取基本信息
            # 暂时返回空字典
            return {}
        except Exception as e:
            print(f"获取股票基本信息失败: {e}", file=sys.stderr)
            return None

    def fetch_financial_report(self, stock_code: str, report_type: str, limit: int = 4, frequency: str = "quarterly") -> Optional[pd.DataFrame]:
        """
        获取财务报表数据
        
        Args:
            stock_code: 股票代码
            report_type: 报表类型 'balance_sheet', 'profit_sheet', 'cash_flow_sheet', 'all'
            limit: 获取最近多少期的数据
            frequency: 频率 'quarterly' (每季) 或 'yearly' (每年)
            
        Returns:
            pandas DataFrame (Index=Date, Columns=Metrics)
        """
        try:
            code = stock_code.replace(".SH", "").replace(".SZ", "").strip()
            
            # 由于akshare部分接口失效，改用 stock_financial_abstract 获取财务摘要
            df_abstract = ak.stock_financial_abstract(symbol=code)
            
            if df_abstract is None or df_abstract.empty:
                return None
            
            # 数据清洗与转置
            # 假设列名: Index, 选项, 指标, 20240930, 20240630...
            # 设置 "指标" 为索引
            if "指标" in df_abstract.columns:
                df_abstract = df_abstract.set_index("指标")
            
            # 删除非日期列
            cols_to_drop = [c for c in df_abstract.columns if c in ["选项", "Index"] or not str(c).isdigit()]
            df_abstract = df_abstract.drop(columns=cols_to_drop, errors="ignore")
            
            # 转置：行变日期，列变指标
            df_T = df_abstract.T
            
            # 处理索引为日期
            df_T.index = pd.to_datetime(df_T.index, format="%Y%m%d", errors="coerce")
            df_T = df_T.sort_index(ascending=False)
            
            # 过滤频率
            if frequency == "yearly":
                # 只保留年报（12月31日）
                df_T = df_T[df_T.index.month == 12]
            
            # 截取最近 N 期
            df_final = df_T.head(limit)
            
            # 如果指定了报表类型，尝试过指标（简单的关键词过滤）
            # 注意：abstract数据是混合的，分类可能不完全准确，但比没有好
            if report_type != "all":
                if report_type == "balance_sheet":
                    keywords = ["资产", "负债", "权益"]
                elif report_type == "profit_sheet":
                    keywords = ["利润", "收入", "成本", "费用", "收益"]
                elif report_type == "cash_flow_sheet":
                    keywords = ["现金流量"]
                else:
                    keywords = []
                
                if keywords:
                    # 筛选列（即原来的行指标）
                    selected_cols = [c for c in df_final.columns if any(k in str(c) for k in keywords)]
                    if selected_cols:
                        df_final = df_final[selected_cols]
            
            # 按时间正序排列返回（便于画图和阅读习惯）
            return df_final.sort_index(ascending=True)
            
        except Exception as e:
            print(f"获取财务报表失败 ({report_type}): {e}", file=sys.stderr)
            return None


# 创建全局实例
data_fetcher = DataFetcher()

