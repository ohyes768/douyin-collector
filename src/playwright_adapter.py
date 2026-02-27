"""
Playwright-based Douyin collection video scraper
Fetches collection videos by monitoring network requests
"""

import asyncio
from typing import List, Optional

from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from loguru import logger

from src.models import VideoInfo
from src.cookie_manager import get_cookie_manager

# Constants
_DEFAULT_TIMEOUT = 60
_DEFAULT_COUNT = 18
_MAX_PAGES = 5
_COLLECTION_URL = "https://www.douyin.com/user/self?showTab=favorite_collection"


class PlaywrightAdapter:
    """Playwright adapter"""

    def __init__(self, config_path: str = "") -> None:
        """Init adapter"""
        self._config_path = config_path
        self._cookie_manager = get_cookie_manager(config_path or "config/cookie.yaml")
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    async def __aenter__(self):
        """Async context enter"""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ]
        )
        self._context = await self._browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
        )

        # Inject anti-detection script
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        # Inject Cookie
        cookie = self._cookie_manager.get_cookie()
        if cookie:
            cookies = self._parse_cookie_string(cookie)
            await self._context.add_cookies(cookies)
            logger.debug(f"Injected {len(cookies)} cookies")
        else:
            logger.warning("Cookie not configured, may fail to fetch data")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context exit"""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    def _parse_cookie_string(self, cookie_str: str) -> List[dict]:
        """Parse Cookie string"""
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

    async def get_all_collections_videos(
        self,
        max_count: int = 0,
        days_start: int = 0,
        days_end: int = 0,
    ) -> List[VideoInfo]:
        """Get all collection videos"""
        logger.info("Fetching videos...")

        # Calculate time range
        import time
        current_time = int(time.time())
        time_min = 0
        time_max = 0

        if days_end > 0:
            time_min = current_time - (days_end * 86400)
            logger.info(f"Time filter: last {days_end} days")

        if not self._context:
            logger.error("Browser context not initialized")
            return []

        all_videos = []
        page_count = 0

        def create_response_handler():
            seen_ids = set()

            async def handle_response(response):
                nonlocal seen_ids
                url = response.url

                if '/aweme/v1/web/aweme/listcollection' in url and response.status == 200:
                    try:
                        headers = await response.all_headers()
                        if 'application/json' in headers.get('content-type', ''):
                            body_text = await response.text()
                            import json
                            data = json.loads(body_text)

                            if 'aweme_list' in data and isinstance(data['aweme_list'], list):
                                videos_data = data['aweme_list']

                                for item in videos_data:
                                    try:
                                        create_time = item.get("create_time", 0)
                                        if time_min > 0 and create_time < time_min:
                                            continue

                                        video = self._parse_video_info(item)
                                        if video and video.aweme_id and video.aweme_id not in seen_ids:
                                            seen_ids.add(video.aweme_id)
                                            all_videos.append(video)
                                    except Exception as e:
                                        logger.warning(f"Parse video failed: {e}")
                    except Exception as e:
                        logger.debug(f"Handle response failed: {e}")

            return handle_response

        page = await self._context.new_page()
        page.on('response', create_response_handler())

        try:
            await page.goto(_COLLECTION_URL, wait_until='domcontentloaded', timeout=_DEFAULT_TIMEOUT * 1000)
            await asyncio.sleep(5)

            last_count = 0
            no_new_video_count = 0

            for i in range(_MAX_PAGES):
                if max_count > 0 and len(all_videos) >= max_count:
                    break

                await page.evaluate('window.scrollBy(0, 1000)')
                await asyncio.sleep(2)

                page_count += 1
                current_count = len(all_videos)
                logger.info(f"Got {current_count} videos")

                if current_count == last_count:
                    no_new_video_count += 1
                    if no_new_video_count >= 2:
                        break
                else:
                    no_new_video_count = 0

                last_count = current_count

            await asyncio.sleep(3)

            if max_count > 0 and len(all_videos) > max_count:
                all_videos = all_videos[:max_count]

            logger.info(f"Total: {len(all_videos)} videos")
            return all_videos

        except Exception as e:
            logger.error(f"Fetch failed: {e}")
            return []
        finally:
            await page.close()

    def _parse_video_info(self, item: dict) -> Optional[VideoInfo]:
        """Parse video info"""
        try:
            aweme_id = item.get("aweme_id", "")
            desc = item.get("desc", "")
            title = desc

            is_product = self._is_product_video(item, title, desc)

            video_url = ""
            if "video" in item and "play_addr" in item["video"]:
                urls = item["video"]["play_addr"].get("url_list", [])
                if urls:
                    video_url = urls[0]

            author = ""
            if "author" in item:
                author = item["author"].get("nickname", "")

            create_time = item.get("create_time", 0)

            return VideoInfo(
                aweme_id=aweme_id,
                title=title,
                author=author,
                video_url=video_url,
                desc=desc,
                create_time=create_time,
                is_product=is_product,
            )
        except Exception as e:
            logger.warning(f"Parse video info failed: {e}")
            return None

    def _is_product_video(self, item: dict, title: str, desc: str) -> bool:
        """Check if product video"""
        product_keywords = ["购买", "商品", "橱窗", "小店", "商城", "优惠", "折扣", "秒杀", "抢购"]
        text_to_check = f"{title} {desc}".lower()
        for keyword in product_keywords:
            if keyword in text_to_check:
                return True
        return False
