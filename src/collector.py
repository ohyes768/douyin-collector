"""
收藏视频采集器
使用 Playwright 获取抖音收藏视频列表
"""

from typing import List
from loguru import logger

from src.models import VideoInfo
from src.playwright_adapter import PlaywrightAdapter


class DouyinCollector:
    """Douyin Collector"""

    def __init__(self, config_path: str = "config/cookie.yaml") -> None:
        """Init collector"""
        self._adapter = PlaywrightAdapter(config_path)
        logger.info("Collector ready")
        self._initialized = False

    async def __aenter__(self):
        """Async context enter"""
        await self._adapter.__aenter__()
        self._initialized = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context exit"""
        await self._adapter.__aexit__(exc_type, exc_val, exc_tb)
        self._initialized = False

    async def fetch_collection_videos(
        self,
        max_count: int = 0,
        days_start: int = 0,
        days_end: int = 0,
        exclude_products: bool = True
    ) -> List[VideoInfo]:
        """Fetch collection videos"""
        if not self._initialized:
            logger.warning("Collector not initialized")
            return []

        logger.info("Fetching videos...")
        videos = await self._adapter.get_all_collections_videos(
            max_count=max_count,
            days_start=days_start,
            days_end=days_end
        )

        if exclude_products:
            original_count = len(videos)
            videos = [v for v in videos if not v.is_product]
            excluded_count = original_count - len(videos)
            if excluded_count > 0:
                logger.info(f"Filtered {excluded_count} product videos")

        logger.info(f"Got {len(videos)} videos")
        return videos
