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
        """Get all collection videos by monitoring network requests with page scrolling

        Note: The collection list API returns videos sorted by collection time (newest first),
        but does not include the collection timestamp. We use the cursor value as a proxy
        for collection time to determine when to stop scrolling.
        """
        logger.info("Fetching videos...")

        import time
        current_time = int(time.time())
        time_min = 0
        time_max = 0

        # Calculate time range (in seconds)
        if days_end > 0:
            time_max = current_time - (days_start * 86400)
            time_min = current_time - (days_end * 86400)
            logger.info(f"Time filter: last {days_end} days to {days_start} days ago")
        elif days_start > 0:
            time_max = current_time - (days_start * 86400)
            logger.info(f"Time filter: older than {days_start} days")

        # Cursor is in microsecond-like format, convert time bounds
        # Based on analysis: cursor ≈ timestamp * 1_000_000
        cursor_min = int(time_min * 1_000_000) if time_min > 0 else 0
        cursor_max = int(time_max * 1_000_000) if time_max > 0 else float('inf')

        if not self._context:
            logger.error("Browser context not initialized")
            return []

        all_videos = []
        seen_ids = set()
        stop_fetching = False
        last_cursor = float('inf')

        page = await self._context.new_page()

        # Response handler to capture API data
        async def handle_response(response):
            nonlocal all_videos, seen_ids, stop_fetching, last_cursor

            if '/aweme/v1/web/aweme/listcollection' not in response.url:
                return

            try:
                if response.status != 200:
                    return

                content_type = response.headers.get('content-type', '')
                if 'application/json' not in content_type:
                    return

                body_text = await response.text()
                import json
                data = json.loads(body_text)

                if 'aweme_list' not in data or not isinstance(data.get('aweme_list'), list):
                    return

                videos_data = data['aweme_list']
                cursor = data.get('cursor', 0)

                logger.debug(f"Captured API response: {len(videos_data)} videos, cursor={cursor}")

                # Check if we've passed the time range
                # cursor decreases as we scroll (older collection times)
                if time_min > 0 and cursor < cursor_min:
                    logger.info(f"Reached time limit: cursor {cursor} < min {cursor_min}")
                    stop_fetching = True
                    return

                # Also stop if cursor is not changing (no more data)
                if cursor == last_cursor:
                    logger.info("Cursor not changing, no more data")
                    stop_fetching = True
                    return
                last_cursor = cursor

                for item in videos_data:
                    try:
                        aweme_id = item.get("aweme_id", "")
                        if aweme_id in seen_ids:
                            continue
                        seen_ids.add(aweme_id)

                        video = self._parse_video_info(item)
                        if video:
                            all_videos.append(video)
                    except Exception as e:
                        logger.debug(f"Parse video failed: {e}")

            except Exception as e:
                logger.debug(f"Handle response failed: {e}")

        page.on('response', handle_response)

        try:
            # Navigate to collection page
            await page.goto(_COLLECTION_URL, wait_until='domcontentloaded', timeout=_DEFAULT_TIMEOUT * 1000)
            await asyncio.sleep(5)  # Wait for initial load

            logger.info("Scrolling to load more videos...")

            last_count = 0
            no_new_count = 0
            max_no_new = 5
            max_scroll_rounds = 200

            for scroll_round in range(max_scroll_rounds):
                if stop_fetching:
                    logger.info("Stopping: reached time limit or no more data")
                    break

                if max_count > 0 and len(all_videos) >= max_count:
                    break

                # Scroll down
                await page.evaluate('window.scrollBy(0, document.body.scrollHeight / 3)')
                await asyncio.sleep(2)

                current_count = len(all_videos)
                logger.info(f"Round {scroll_round + 1}/{max_scroll_rounds}: {current_count} videos")

                if current_count == last_count:
                    no_new_count += 1
                    if no_new_count >= max_no_new:
                        logger.info("No new videos after multiple attempts")
                        break
                else:
                    no_new_count = 0

                last_count = current_count

            # Final wait
            await asyncio.sleep(2)

            if max_count > 0 and len(all_videos) > max_count:
                all_videos = all_videos[:max_count]

            logger.info(f"Total: {len(all_videos)} videos")
            return all_videos

        except Exception as e:
            logger.error(f"Fetch failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
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
