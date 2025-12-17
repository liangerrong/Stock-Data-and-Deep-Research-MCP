"""
配置管理模块
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class Settings:
    """应用配置类"""
    
    # akshare配置
    AKSHARE_TIMEOUT = int(os.getenv("AKSHARE_TIMEOUT", "30"))
    
    # 缓存配置 (可选，视底层实现而定)
    CACHE_ENABLED = os.getenv("CACHE_ENABLED", "True").lower() == "true"
    CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))  # 缓存时间（秒）
    
    # 股票市场配置
    SUPPORTED_MARKETS = ["A股", "SH", "SZ"]  # 支持的市场
    
    @classmethod
    def validate(cls):
        """验证必要的配置项"""
        # 这里仅用于验证数据源的必要配置，目前 akshare 无需 key
        return []


# 创建全局配置实例
settings = Settings()
