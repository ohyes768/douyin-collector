"""
Cookie 管理器 - 从配置文件加载 Cookie
"""

import yaml
from pathlib import Path
from typing import Optional
from loguru import logger


class CookieManager:
    """Cookie 管理器"""

    _instance: Optional['CookieManager'] = None
    _cookie: str = ""
    _config_path: Path

    def __new__(cls, config_path: str = "config/cookie.yaml"):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config_path = Path(config_path)
            cls._instance._load_cookie()
        return cls._instance

    def _load_cookie(self):
        """从配置文件加载 Cookie"""
        try:
            if self._config_path.exists():
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    self._cookie = config.get("douyin", {}).get("cookie", "")
                    if self._cookie:
                        logger.info("已加载 Cookie")
                    else:
                        logger.warning("Cookie 配置为空")
            else:
                logger.warning(f"Cookie 配置文件不存在: {self._config_path}")
        except Exception as e:
            logger.warning(f"加载 Cookie 失败: {e}")

    def get_cookie(self) -> str:
        """获取当前 Cookie"""
        return self._cookie


# 全局 Cookie 管理器实例
_cookie_manager: Optional[CookieManager] = None


def get_cookie_manager(config_path: str = "config/cookie.yaml") -> CookieManager:
    """获取全局 Cookie 管理器实例"""
    global _cookie_manager
    if _cookie_manager is None:
        _cookie_manager = CookieManager(config_path)
    return _cookie_manager
