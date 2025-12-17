"""
股票代码查询模块
"""
import akshare as ak
import pandas as pd
from typing import Optional, List, Tuple
import sys


class StockLookup:
    """股票代码查询类"""
    
    def __init__(self):
        self._stock_list_cache = None
    
    def _get_stock_list(self):
        """获取股票列表（带缓存）"""
        if self._stock_list_cache is None:
            try:
                # 获取A股股票列表
                sh_stocks = ak.stock_info_a_code_name()
                self._stock_list_cache = sh_stocks
            except Exception as e:
                print(f"获取股票列表失败: {e}", file=sys.stderr)
                self._stock_list_cache = pd.DataFrame()
        return self._stock_list_cache
    
    def lookup_by_name(self, stock_name: str) -> Optional[Tuple[str, str]]:
        """
        通过股票名称查找股票代码
        
        Args:
            stock_name: 股票名称，如 "贵州茅台"
        
        Returns:
            (股票代码, 股票名称) 元组，如 ("600519", "贵州茅台")，未找到返回None
        """
        stock_list = self._get_stock_list()
        if stock_list.empty:
            return None
        
        # 精确匹配
        exact_match = stock_list[stock_list['name'] == stock_name]
        if not exact_match.empty:
            code = exact_match.iloc[0]['code']
            name = exact_match.iloc[0]['name']
            return (code, name)
        
        # 模糊匹配
        fuzzy_match = stock_list[stock_list['name'].str.contains(stock_name, na=False)]
        if not fuzzy_match.empty:
            code = fuzzy_match.iloc[0]['code']
            name = fuzzy_match.iloc[0]['name']
            return (code, name)
        
        return None
    
    def lookup_by_code(self, stock_code: str) -> Optional[Tuple[str, str]]:
        """
        通过股票代码查找股票名称
        
        Args:
            stock_code: 股票代码，如 "600519" 或 "600519.SH"
        
        Returns:
            (股票代码, 股票名称) 元组，未找到返回None
        """
        # 清理代码格式
        code = stock_code.replace(".SH", "").replace(".SZ", "").strip()
        
        stock_list = self._get_stock_list()
        if stock_list.empty:
            return None
        
        # 精确匹配
        exact_match = stock_list[stock_list['code'] == code]
        if not exact_match.empty:
            name = exact_match.iloc[0]['name']
            return (code, name)
        
        return None
    
    def normalize_code(self, stock_identifier: str) -> Optional[Tuple[str, str]]:
        """
        标准化股票标识符（名称或代码）为标准格式
        
        Args:
            stock_identifier: 股票标识符，可能是名称或代码
        
        Returns:
            (标准代码, 股票名称) 元组，格式如 ("600519.SH", "贵州茅台")
        """
        # 如果包含点号，可能是代码格式
        if "." in stock_identifier:
            code_part = stock_identifier.split(".")[0]
            suffix = stock_identifier.split(".")[1] if "." in stock_identifier else ""
            result = self.lookup_by_code(code_part)
            if result:
                code, name = result
                # 确定市场后缀
                if not suffix:
                    # 根据代码判断市场
                    if code.startswith("6"):
                        suffix = "SH"
                    elif code.startswith("0") or code.startswith("3"):
                        suffix = "SZ"
                    else:
                        suffix = "SH"  # 默认
                return (f"{code}.{suffix}", name)
        else:
            # 尝试作为名称查找
            result = self.lookup_by_name(stock_identifier)
            if result:
                code, name = result
                # 根据代码判断市场
                if code.startswith("6"):
                    suffix = "SH"
                elif code.startswith("0") or code.startswith("3"):
                    suffix = "SZ"
                else:
                    suffix = "SH"
                return (f"{code}.{suffix}", name)
            
            # 尝试作为代码查找（无后缀）
            result = self.lookup_by_code(stock_identifier)
            if result:
                code, name = result
                if code.startswith("6"):
                    suffix = "SH"
                elif code.startswith("0") or code.startswith("3"):
                    suffix = "SZ"
                else:
                    suffix = "SH"
                return (f"{code}.{suffix}", name)
        
        return None
    
    def validate_code(self, stock_code: str) -> bool:
        """
        验证股票代码是否有效
        
        Args:
            stock_code: 股票代码
        
        Returns:
            bool
        """
        result = self.normalize_code(stock_code)
        return result is not None


# 创建全局实例
stock_lookup = StockLookup()

