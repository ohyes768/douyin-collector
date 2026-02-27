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

    async def validate_cookie_async(self) -> tuple[bool, str]:
        """
        异步验证 Cookie 是否有效（使用 Playwright）

        通过访问收藏页面，检查是否跳转到登录页来判断

        Returns:
            (is_valid, message): 是否有效及提示信息
        """
        if not self._cookie:
            return False, "Cookie 为空"

        if "sessionid=" not in self._cookie:
            return False, "Cookie 缺少 sessionid 字段"

        # 使用 Playwright 验证
        from playwright.async_api import async_playwright
        from loguru import logger
        import asyncio

        try:
            logger.info("正在验证 Cookie（访问收藏页面）...")

            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )

            # 解析并注入 Cookie
            cookies = self._parse_cookie_string(self._cookie)
            await context.add_cookies(cookies)
            logger.debug(f"已注入 {len(cookies)} 个 Cookie")

            page = await context.new_page()

            # 访问收藏页面
            await page.goto(
                "https://www.douyin.com/user/self?showTab=favorite_collection",
                wait_until='domcontentloaded',
                timeout=30000
            )

            # 等待页面加载
            await asyncio.sleep(3)

            # 检查登录弹窗是否存在
            login_panel = await page.query_selector("#login-panel-new")
            if login_panel:
                await browser.close()
                await playwright.stop()
                return False, "检测到登录弹窗，Cookie 已失效"

            # 如果没有登录弹窗，说明 Cookie 有效
            await browser.close()
            await playwright.stop()

            return True, "Cookie 有效（能访问收藏页面）"

        except Exception as e:
            return False, f"验证过程出错: {e}"

    def validate_cookie(self) -> tuple[bool, str]:
        """
        同步验证 Cookie（只检查字段完整性）

        注意：完整的验证需要使用 validate_cookie_async() 方法

        Returns:
            (is_valid, message): 是否有效及提示信息
        """
        # 1. 检查 Cookie 是否为空
        if not self._cookie:
            return False, "Cookie 为空"

        # 2. 检查关键字段是否存在
        if "sessionid=" not in self._cookie:
            return False, "Cookie 缺少 sessionid 字段"

        # 3. 检查登录时间是否过期（简单判断）
        import re
        login_time_match = re.search(r'login_time=(\d+)', self._cookie)
        if login_time_match:
            login_time = int(login_time_match.group(1))
            import time
            current_time = int(time.time())
            # 如果登录时间超过 30 天，可能已过期
            if current_time - login_time > 30 * 86400:
                return False, f"登录时间已过期 ({login_time})"

        # 4. 检查 Cookie 长度
        if len(self._cookie) < 100:
            return False, f"Cookie 长度过短 ({len(self._cookie)} 字符)"

        return True, "Cookie 格式正确"

    def _parse_cookie_string(self, cookie_str: str) -> list:
        """解析 Cookie 字符串为 Playwright 格式"""
        cookies = []
        for item in cookie_str.split(';'):
            item = item.strip()
            if '=' in item:
                name, value = item.split('=', 1)
                cookies.append({
                    'name': name.strip(),
                    'value': value.strip(),
                    'domain': '.douyin.com',
                    'path': '/'
                })
        return cookies



# 全局 Cookie 管理器实例
_cookie_manager: Optional[CookieManager] = None


def get_cookie_manager(config_path: str = "config/cookie.yaml") -> CookieManager:
    """获取全局 Cookie 管理器实例"""
    global _cookie_manager
    if _cookie_manager is None:
        _cookie_manager = CookieManager(config_path)
    return _cookie_manager
