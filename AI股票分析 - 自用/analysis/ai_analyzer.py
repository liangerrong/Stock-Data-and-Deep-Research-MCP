"""
AI分析模块
"""
import json
import requests
import time
import sys
from typing import Dict, List, Optional
import pandas as pd
from config.settings import settings
from analysis.data_processor import data_processor
from utils.formatter import format_stock_data_summary, format_metrics_table


class AIAnalyzer:
    """AI分析类"""
    
    def __init__(self):
        self.api_key = settings.DEEPSEEK_API_KEY
        self.api_base = settings.DEEPSEEK_API_BASE
        self.model = settings.DEEPSEEK_MODEL
    
    def _call_deepseek(self, prompt: str, system_prompt: str = None) -> Optional[str]:
        """
        调用DeepSeek API
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
        
        Returns:
            API返回的文本内容
        """
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY 未设置")
        
        url = f"{self.api_base}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=data, headers=headers, timeout=60)
                response.raise_for_status()
                result = response.json()
                
                if "choices" not in result or len(result["choices"]) == 0:
                    raise ValueError("API返回格式异常")
                
                return result["choices"][0]["message"]["content"]
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    print(f"请求超时，{retry_delay}秒后重试...", file=sys.stderr)
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise ValueError("生成报告超时，请稍后重试")
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:
                    raise ValueError("API密钥无效，请检查DEEPSEEK_API_KEY配置")
                elif e.response.status_code == 429:
                    if attempt < max_retries - 1:
                        print(f"请求频率过高，{retry_delay}秒后重试...", file=sys.stderr)
                        time.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        raise ValueError("API请求频率过高，请稍后重试")
                else:
                    raise ValueError(f"生成报告失败: HTTP {e.response.status_code}")
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"请求失败: {e}，{retry_delay}秒后重试...", file=sys.stderr)
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise ValueError(f"调用DeepSeek API失败: {str(e)}")
    
    def generate_report(self, 
                       stock_info: Dict,
                       data: pd.DataFrame,
                       metrics: Dict,
                       requirements: Dict,
                       news_data: Optional[List[Dict]] = None,
                       chart_description: str = "",
                       financial_data: Optional[Dict[str, pd.DataFrame]] = None) -> str:
        """
        生成分析报告
        
        Args:
            stock_info: 股票信息，包含 {'name': str, 'code': str}
            data: 股票数据DataFrame
            metrics: 计算出的指标字典
            requirements: 用户需求字典，包含报告长度等
            news_data: 新闻数据列表（可选）
            chart_description: 图表描述（可选）
            financial_data: 财务数据字典（可选），键为报表类型，值为DataFrame
        
        Returns:
            分析报告文本
        """
        # 构建数据摘要
        data_summary = "无市场数据"
        trend_desc = "无趋势数据"
        
        if data is not None and not data.empty:
            data_summary = format_stock_data_summary(data)
            metrics_table = format_metrics_table(metrics)
            
            # 构建趋势分析
            trend = data_processor.get_trend_analysis(data)
            trend_desc = trend.get('描述', '')
        else:
            metrics_table = "无指标数据"
        
        # 构建提示词
        system_prompt = """你是一位专业的股票分析师。请根据提供的股票数据、指标和用户需求，生成一份专业、客观的股票分析报告。
报告应该：
1. 语言专业但易懂
2. 基于数据进行分析，避免主观臆测
3. 包含对关键指标的解读
4. 如果提供了新闻信息，可以结合新闻进行分析
5. 保持客观中立，不给出投资建议
6. 按照用户要求的字数撰写"""
        
        user_prompt = f"""请分析以下股票数据并生成报告：

股票信息：
- 股票名称：{stock_info.get('name', '')}
- 股票代码：{stock_info.get('code', '')}
"""

        if data is not None and not data.empty:
            user_prompt += f"""
数据摘要：
{data_summary}

技术指标：
{metrics_table}

趋势分析：
{trend_desc}
"""
        
        if chart_description:
            user_prompt += f"\n图表描述：\n{chart_description}\n"
        
        if news_data:
            user_prompt += "\n相关新闻：\n"
            for i, news in enumerate(news_data[:5], 1):  # 最多5条新闻
                user_prompt += f"{i}. {news.get('title', '')}\n"
                user_prompt += f"   链接: {news.get('link', '')}\n"
                user_prompt += f"   摘要: {news.get('snippet', '')}\n"
                # 如果有详细内容，也包含进去
                if news.get('full_content'):
                    user_prompt += f"   详细内容: {news.get('full_content', '')[:1000]}\n"  # 限制长度
                user_prompt += "\n"
        
        if financial_data:
            user_prompt += "\n财务数据概要：\n"
            for report_type, df in financial_data.items():
                type_name = {
                    "balance_sheet": "资产负债表",
                    "profit_sheet": "利润表",
                    "cash_flow_sheet": "现金流量表"
                }.get(report_type, report_type)
                
                user_prompt += f"\n{type_name} (最近{len(df)}期):\n"
                # 只展示部分关键列以节省token，或者全部展示（视列数而定）
                # 这里简单处理，直接转string，依托Pandas的默认显示
                user_prompt += df.to_string() + "\n"
        
        # 添加用户原始需求
        report_length = requirements.get('report_length', settings.DEFAULT_REPORT_LENGTH)
        user_prompt += f"\n\n请生成一份约{report_length}字的分析报告，要求：\n"
        
        if requirements.get('comparison', False):
            user_prompt += "- 包含与前一交易日的对比分析\n"
        
        if requirements.get('metrics'):
            user_prompt += f"- 重点分析以下指标：{', '.join(requirements['metrics'])}\n"
        
        if news_data:
            user_prompt += "- 结合新闻信息进行综合分析\n"
        
        user_prompt += "- 报告应该结构清晰，包含数据解读、趋势分析和综合评价\n"
        
        try:
            report = self._call_deepseek(user_prompt, system_prompt)
            return report.strip()
        except Exception as e:
            return f"生成报告时出错: {str(e)}"
    
    def generate_comparison_report(self,
                                  stock_data_list: List[Dict],
                                  comparison_table: pd.DataFrame,
                                  requirements: Dict) -> str:
        """
        生成多股票对比报告
        
        Args:
            stock_data_list: 股票数据列表
            comparison_table: 对比表格DataFrame
            requirements: 用户需求字典
        
        Returns:
            对比分析报告文本
        """
        system_prompt = """你是一位专业的股票分析师。请根据提供的多股票对比数据，生成一份专业的对比分析报告。
报告应该：
1. 对比各股票的关键指标
2. 分析各股票的优劣势
3. 保持客观中立
4. 按照用户要求的字数撰写"""
        
        user_prompt = f"""请对以下股票进行对比分析：

对比数据：
{comparison_table.to_string()}

股票列表：
"""
        for stock_info in stock_data_list:
            user_prompt += f"- {stock_info.get('name', '')} ({stock_info.get('code', '')})\n"
        
        report_length = requirements.get('report_length', settings.DEFAULT_REPORT_LENGTH)
        user_prompt += f"\n\n请生成一份约{report_length}字的对比分析报告，包含各股票的指标对比、优劣势分析和综合评价。"
        
        try:
            report = self._call_deepseek(user_prompt, system_prompt)
            return report.strip()
        except Exception as e:
            return f"生成对比报告时出错: {str(e)}"


# 创建全局实例
ai_analyzer = AIAnalyzer()

