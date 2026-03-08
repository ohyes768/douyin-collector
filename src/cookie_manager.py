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
        """Load Cookie from config"""
        try:
            if self._config_path.exists():
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    self._cookie = config.get("douyin", {}).get("cookie", "")
                    if self._cookie:
                        logger.info("Cookie loaded")
                    else:
                        logger.warning("Cookie is empty")
            else:
                logger.warning(f"Cookie file not found: {self._config_path}")
        except Exception as e:
            logger.warning(f"Load Cookie failed: {e}")

    def get_cookie(self) -> str:
        """获取当前 Cookie"""
        return self._cookie

    async def validate_cookie_async(self) -> tuple[bool, str]:
        """
        Validate Cookie using Playwright

        Check if login popup appears when visiting favorites page

        Returns:
            (is_valid, message): Valid status and message
        """
        if not self._cookie:
            return False, "Cookie is empty"

        if "sessionid=" not in self._cookie:
            return False, "Cookie missing sessionid"

        # 使用 Playwright 验证
        from playwright.async_api import async_playwright
        from loguru import logger
        import asyncio

        try:
            logger.info("Validating Cookie...")

            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            )

            # 解析并注入 Cookie
            cookies = self._parse_cookie_string(self._cookie)
            await context.add_cookies(cookies)
            logger.debug(f"Injected {len(cookies)} cookies")

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
                return False, "Login popup detected, Cookie expired"

            # 如果没有登录弹窗，说明 Cookie 有效
            await browser.close()
            await playwright.stop()

            return True, "Cookie valid"

        except Exception as e:
            return False, f"Validation error: {e}"

    def validate_cookie(self) -> tuple[bool, str]:
        """
        Validate Cookie (field check only)

        Note: Use validate_cookie_async() for full validation

        Returns:
            (is_valid, message): Valid status and message
        """
        # 1. Check if empty
        if not self._cookie:
            return False, "Cookie is empty"

        # 2. Check sessionid field
        if "sessionid=" not in self._cookie:
            return False, "Cookie missing sessionid"

        # 3. Check login time
        import re
        login_time_match = re.search(r'login_time=(\d+)', self._cookie)
        if login_time_match:
            login_time = int(login_time_match.group(1))
            import time
            current_time = int(time.time())
            # Expire after 30 days
            if current_time - login_time > 30 * 86400:
                return False, f"Login time expired ({login_time})"

        # 4. Check length
        if len(self._cookie) < 100:
            return False, f"Cookie too short ({len(self._cookie)} chars)"

        return True, "Cookie format OK"

    def _parse_cookie_string(self, cookie_str: str) -> list:
        """Parse Cookie string to Playwright format"""
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



# Global Cookie manager instance
_cookie_manager: Optional[CookieManager] = None


def get_cookie_manager(config_path: str = "config/cookie.yaml") -> CookieManager:
    """Get global Cookie manager instance"""
    global _cookie_manager
    if _cookie_manager is None:
        _cookie_manager = CookieManager(config_path)
    return _cookie_manager
