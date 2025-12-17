"""
提示词解析模块
"""
import json
import sys
import requests
from typing import Dict, Optional, List
from config.settings import settings
from utils.date_utils import calculate_relative_date
import time


class PromptParser:
    """提示词解析类"""
    
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
            "temperature": 0.3
        }
        
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=data, headers=headers, timeout=30)
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
                    raise ValueError("API请求超时，请稍后重试")
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
                    raise ValueError(f"API请求失败: HTTP {e.response.status_code}")
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"请求失败: {e}，{retry_delay}秒后重试...", file=sys.stderr)
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise ValueError(f"调用DeepSeek API失败: {str(e)}")
    
    def parse(self, user_prompt: str) -> Dict:
        """
        解析用户提示词，提取结构化信息
        
        Args:
            user_prompt: 用户输入的提示词
        
        Returns:
            结构化字典，包含股票、日期、需求等信息
        """
        system_prompt = """你是一个股票分析助手，需要从用户提示词中提取以下信息：
1. 股票标识（名称或代码，可能有多个）
2. 日期信息（单日或日期区间，可能是绝对日期如"2024-06-01"或相对日期如"最近一年"）
3. 数据类型（日级/秒级，默认日级）
4. 分析需求（是否需要新闻、报告长度、需要计算的指标等）
5. 财务数据需求（是否需要财务报表，如资产负债表、利润表、现金流量表，以及时间段和频率）

请以JSON格式返回，格式如下：
{
    "stocks": ["股票名称或代码"],
    "date_start": "YYYY-MM-DD 或 null",
    "date_end": "YYYY-MM-DD 或 null",
    "relative_date": "相对日期描述，如'最近一年'，如果没有则为null",
    "data_type": "daily 或 second",
    "requirements": {
        "include_news": true/false,
        "search_query": "搜索关键词或句子（如果需要新闻时，AI应生成合适的搜索查询）",
        "report_length": 数字（字数要求）,
        "metrics": ["需要计算的指标列表"],
        "comparison": true/false（是否需要对比前一交易日）,
        "financial_data": {
            "needed": true/false,
            "types": ["balance_sheet", "profit_sheet", "cash_flow_sheet"] 或 ["all"],
            "period": 数字（需要获取的报告期数，默认4）,
            "frequency": "quarterly" (默认) 或 "yearly"
        }
    }
}

如果信息不明确，请合理推断。
- 关于财务数据：
  - 如果用户问"财务状况"、"基本面"等，通常意味着需要所有三张表。
  - 如果用户指定"过去3年"，frequency应为"yearly"，period为3。
  - 如果用户指定"过去4个季度"，frequency应为"quarterly"，period为4。
  - period字段请转换为具体的数字（报告期数）。
"""
        
        try:
            response = self._call_deepseek(user_prompt, system_prompt)
            
            # 尝试从响应中提取JSON
            # 可能响应包含markdown代码块
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()
            
            # 解析JSON
            parsed = json.loads(json_str)
            
            # 处理相对日期
            if parsed.get("relative_date") and not parsed.get("date_start"):
                start_date, end_date = calculate_relative_date(parsed["relative_date"])
                parsed["date_start"] = start_date
                parsed["date_end"] = end_date
            
            # 设置默认值
            if "data_type" not in parsed:
                parsed["data_type"] = "daily"
            
            if "requirements" not in parsed:
                parsed["requirements"] = {}
            
            if "report_length" not in parsed["requirements"]:
                parsed["requirements"]["report_length"] = settings.DEFAULT_REPORT_LENGTH
            
            return parsed
            
        except json.JSONDecodeError as e:
            print(f"解析JSON失败: {e}", file=sys.stderr)
            if 'response' in locals():
                print(f"响应内容: {response}", file=sys.stderr)
            # 返回一个基础结构
            return {
                "stocks": [],
                "date_start": None,
                "date_end": None,
                "data_type": "daily",
                "requirements": {
                    "include_news": False,
                    "report_length": settings.DEFAULT_REPORT_LENGTH,
                    "metrics": []
                }
            }
        except requests.exceptions.RequestException as e:
            error_msg = f"API请求失败: {str(e)}"
            print(error_msg, file=sys.stderr)
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"解析提示词失败: {str(e)}"
            print(error_msg, file=sys.stderr)
            raise ValueError(error_msg)


# 创建全局实例
prompt_parser = PromptParser()

