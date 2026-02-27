#!/usr/bin/env python3
"""
douyin-collector 主入口
抖音收藏视频采集和上传工具
"""

import asyncio
import sys
from pathlib import Path
from loguru import logger

from src.utils import setup_logger, load_config
from src.collector import DouyinCollector
from src.uploader import VideoUploader
from src.cookie_manager import get_cookie_manager
from src.dingtalk_notifier import DingTalkNotifier


def print_progress(current: int, total: int, success: int, skipped: int, failed: int):
    """Print progress"""
    print(f"\rProgress: {current}/{total} | OK: {success} | Skip: {skipped} | Fail: {failed}", end="", flush=True)


async def main():
    """主函数"""
    # 加载配置
    try:
        config = load_config("config/app.yaml")
    except FileNotFoundError as e:
        logger.error(str(e))
        logger.error("请先创建配置文件 config/app.yaml 和 config/cookie.yaml")
        sys.exit(1)

    # 设置日志
    log_config = config["app"]["logging"]
    setup_logger(
        level=log_config["level"],
        log_dir=log_config["dir"]
    )

    logger.info("=" * 60)
    logger.info("douyin-collector starting")
    logger.info("=" * 60)

    # 验证 Cookie（使用 Playwright）
    logger.info("Validating Cookie...")
    cookie_mgr = get_cookie_manager("config/cookie.yaml")
    is_valid, message = await cookie_mgr.validate_cookie_async()

    if not is_valid:
        logger.error(f"Cookie invalid: {message}")

        # 发送钉钉通知
        notify_config = config["app"].get("notification", {})
        if notify_config.get("enabled", False):
            webhook = notify_config.get("dingtalk_webhook")
            if webhook:
                notifier = DingTalkNotifier(webhook)
                notifier.send_cookie_alert(message)

        # 打印错误信息并退出
        logger.error("=" * 60)
        logger.error("Cookie expired, exit")
        logger.error("=" * 60)
        logger.error("Update Cookie:")
        logger.error("1. Open douyin.com and login")
        logger.error("2. Press F12 to open DevTools")
        logger.error("3. Go to Network tab")
        logger.error("4. Refresh page, find any request")
        logger.error("5. Copy Cookie from Request Headers")
        logger.error("6. Update config/cookie.yaml")
        logger.error("=" * 60)
        sys.exit(1)

    logger.info("Cookie valid")

    # 获取配置
    collector_config = config["app"]["collector"]
    days_limit = collector_config.get("days_limit", 7)
    max_videos = collector_config.get("max_videos", 0)
    exclude_products = collector_config.get("exclude_products", True)

    # 初始化上传器
    uploader = VideoUploader(config)

    # 采集视频
    try:
        async with DouyinCollector("config/cookie.yaml") as collector:
            logger.info(f"Fetching last {days_limit} days videos...")

            videos = await collector.fetch_collection_videos(
                max_count=max_videos,
                days_end=days_limit,
                exclude_products=exclude_products
            )

            if not videos:
                logger.warning("No videos found")
                return

            logger.info(f"Got {len(videos)} videos")

            # 处理视频
            stats = await uploader.process_videos(videos, progress_callback=print_progress)

            # 输出结果
            print()  # 换行
            logger.info("=" * 60)
            logger.info("Done")
            logger.info(f"Total: {stats['total']} | OK: {stats['success']} | Skip: {stats['skipped']} | Fail: {stats['failed']}")
            logger.info("=" * 60)

    except Exception as e:
        logger.exception(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nInterrupted")
        sys.exit(0)
