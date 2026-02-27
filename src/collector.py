"""
收藏视频采集器
使用 Playwright 获取抖音收藏视频列表
"""

from typing import List
from loguru import logger

from src.models import VideoInfo
from src.playwright_adapter import PlaywrightAdapter


class DouyinCollector:
    """抖音收藏视频采集器"""

    def __init__(self, config_path: str = "config/cookie.yaml") -> None:
        """初始化采集器"""
        self._adapter = PlaywrightAdapter(config_path)
        logger.info("抖音收藏视频采集器初始化完成")
        self._initialized = False

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._adapter.__aenter__()
        self._initialized = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self._adapter.__aexit__(exc_type, exc_val, exc_tb)
        self._initialized = False

    async def fetch_collection_videos(
        self,
        max_count: int = 0,
        days_start: int = 0,
        days_end: int = 0,
        exclude_products: bool = True
    ) -> List[VideoInfo]:
        """获取收藏视频列表"""
        if not self._initialized:
            logger.warning("采集器未初始化")
            return []

        logger.info("开始获取收藏视频列表...")
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
                logger.info(f"已过滤 {excluded_count} 个商品视频")

        logger.info(f"成功获取 {len(videos)} 个收藏视频")
        return videos
