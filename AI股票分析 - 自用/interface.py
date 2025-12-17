"""
此文件为 AI Agent 调用的统一接口层 (Facade)。
封装了底层的数据获取和计算功能。
提供无状态、标准化的原子能力 (Skills/Tools)。
仅负责数据获取与计算，不包含逻辑推理或搜索功能。
"""
import logging
from typing import Dict, List, Optional, Union, Any
import pandas as pd
from datetime import datetime
import json
import sys

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='agent_actions.log', # 同时写入文件
    filemode='a'
)
logger = logging.getLogger("StockTools")

# 引入底层模块
from core.data_fetcher import data_fetcher
from core.stock_lookup import stock_lookup
from analysis.data_processor import data_processor

class StockAnalysisTools:
    """
    股票分析工具集。
    所有方法均返回 JSON 兼容的数据结构 (Dict, List, str, int, float)，
    不直接返回 DataFrame 或复杂对象。
    """

    def __init__(self):
        pass

    def get_stock_info(self, name_or_code: str) -> Dict[str, str]:
        """
        根据名称或代码查找股票标准信息。
        
        Args:
            name_or_code: 股票名称（如"茅台"）或代码（如"600519"）
            
        Returns:
            Dict: {"name": "贵州茅台", "code": "600519.SH"} 或 {"error": "..."}
        """
        try:
            result = stock_lookup.normalize_code(name_or_code)
            if result:
                code, name = result
                logger.info(f"Found stock: {name} ({code})")
                return {"name": name, "code": code}
            else:
                logger.warning(f"Stock not found: {name_or_code}")
                return {"error": f"未找到股票: {name_or_code}"}
        except Exception as e:
            logger.error(f"Error in get_stock_info: {e}")
            return {"error": str(e)}

    def get_stock_daily(self, 
                       stock_code: str, 
                       start_date: str, 
                       end_date: Optional[str] = None) -> Union[List[Dict], Dict]:
        """
        获取股票日线行情数据。
        
        Args:
            stock_code: 标准股票代码 (如 "600519.SH")
            start_date: 开始日期 "YYYY-MM-DD"
            end_date: 结束日期 "YYYY-MM-DD" (可选，默认至今)
            
        Returns:
            List[Dict]: 每日数据列表，每项包含 open, close, high, low, volume 等。
            若出错返回 Dict: {"error": "..."}
        """
        try:
            df = data_fetcher.fetch_daily_data(stock_code, start_date, end_date)
            if df is None or df.empty:
                return {"error": "未获取到数据，请检查日期范围或股票代码"}
            
            # 转换为记录列表，日期转字符串
            # 假设 df index 包含日期或列中有日期
            if '日期' in df.columns:
                df['date'] = df['日期'].apply(lambda x: x.strftime('%Y-%m-%d') if isinstance(x, (pd.Timestamp, datetime)) else str(x))
            elif 'date' in df.columns:
                 df['date'] = df['date'].apply(lambda x: x.strftime('%Y-%m-%d') if isinstance(x, (pd.Timestamp, datetime)) else str(x))
            
            # 转为字典列表
            records = df.to_dict(orient='records')
            
            # 清理可能的 Timestamp 对象
            clean_records = []
            for record in records:
                new_rec = {}
                for k, v in record.items():
                    if isinstance(v, (pd.Timestamp, datetime)):
                        new_rec[k] = v.strftime('%Y-%m-%d')
                    else:
                        new_rec[k] = v
                clean_records.append(new_rec)
                
            logger.info(f"Fetched {len(clean_records)} daily records for {stock_code}")
            return clean_records
        except Exception as e:
            logger.error(f"Error in get_stock_daily: {e}")
            return {"error": str(e)}

    def get_financial_report(self, 
                            stock_code: str, 
                            report_type: str = "all", 
                            limit: int = 4) -> Union[Dict[str, List[Dict]], Dict]:
        """
        获取财务报表数据。
        
        Args:
            stock_code: 股票代码
            report_type: 'balance_sheet'(资产负债), 'profit_sheet'(利润), 'cash_flow_sheet'(现金流), 'all'(全部)
            limit: 最近几期 (默认4)
            
        Returns:
            Dict: {"balance_sheet": [...], "profit_sheet": [...]}
        """
        try:
            types = []
            if report_type == "all":
                types = ["balance_sheet", "profit_sheet", "cash_flow_sheet"]
            else:
                types = [report_type]
            
            result = {}
            for r_type in types:
                df = data_fetcher.fetch_financial_report(stock_code, r_type, limit=limit)
                if df is not None and not df.empty:
                    # Index 是日期，需要变成列
                    df = df.reset_index()
                    df.rename(columns={'index': 'report_date'}, inplace=True)
                    # 转换日期格式
                    if 'report_date' in df.columns:
                         df['report_date'] = df['report_date'].apply(lambda x: x.strftime('%Y-%m-%d') if isinstance(x, (pd.Timestamp, datetime)) else str(x))
                    
                    result[r_type] = df.to_dict(orient='records')
            
            if not result:
                return {"error": "未获取到财务数据"}
                
            return result
        except Exception as e:
            logger.error(f"Error in get_financial_report: {e}")
            return {"error": str(e)}

    def calculate_indicators(self, daily_data: List[Dict]) -> Dict:
        """
        根据日线数据计算技术指标。
        
        Args:
            daily_data: get_stock_daily 返回的数据列表
            
        Returns:
            Dict: {"ma5": ..., "rsi": ..., "change_pct": ...}
        """
        try:
            if not daily_data:
                return {"error": "数据为空"}
            
            df = pd.DataFrame(daily_data)
            # DataProcessor 需要一定的列名格式，通常 fetch_daily_data 已经标准化好了
            # 这里调用 data_processor 计算
            metrics = data_processor.calculate_metrics(df)
            trend = data_processor.get_trend_analysis(df)
            
            return {
                "metrics": metrics,
                "trend": trend
            }
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return {"error": str(e)}

if __name__ == "__main__":
    # 简单测试
    tool = StockAnalysisTools()
    print("Testing stock lookup...", file=sys.stderr)
    print(tool.get_stock_info("茅台"), file=sys.stderr)
