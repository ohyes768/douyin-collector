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
    """打印进度"""
    print(f"\r进度: {current}/{total} | 成功: {success} | 跳过: {skipped} | 失败: {failed}", end="", flush=True)


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
    logger.info("douyin-collector 启动")
    logger.info("=" * 60)

    # 验证 Cookie（使用 Playwright）
    logger.info("正在验证 Cookie...")
    cookie_mgr = get_cookie_manager("config/cookie.yaml")
    is_valid, message = await cookie_mgr.validate_cookie_async()

    if not is_valid:
        logger.error(f"Cookie 验证失败: {message}")

        # 发送钉钉通知
        notify_config = config["app"].get("notification", {})
        if notify_config.get("enabled", False):
            webhook = notify_config.get("dingtalk_webhook")
            if webhook:
                notifier = DingTalkNotifier(webhook)
                notifier.send_cookie_alert(message)

        # 打印错误信息并退出
        logger.error("=" * 60)
        logger.error("Cookie 已失效，程序退出")
        logger.error("=" * 60)
        logger.error("请按以下步骤更新 Cookie：")
        logger.error("1. 打开浏览器访问抖音并登录")
        logger.error("2. 按 F12 打开开发者工具")
        logger.error("3. 切换到 Network 标签")
        logger.error("4. 刷新页面，找到任意请求")
        logger.error("5. 复制 Request Headers 中的 Cookie")
        logger.error("6. 更新到 config/cookie.yaml 文件")
        logger.error("=" * 60)
        sys.exit(1)

    logger.info("Cookie 验证通过")

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
            logger.info(f"开始采集最近 {days_limit} 天的收藏视频...")

            videos = await collector.fetch_collection_videos(
                max_count=max_videos,
                days_end=days_limit,
                exclude_products=exclude_products
            )

            if not videos:
                logger.warning("未获取到任何视频，请检查 Cookie 是否有效")
                return

            logger.info(f"成功获取 {len(videos)} 个视频")

            # 处理视频
            stats = await uploader.process_videos(videos, progress_callback=print_progress)

            # 输出结果
            print()  # 换行
            logger.info("=" * 60)
            logger.info("处理完成")
            logger.info(f"总计: {stats['total']} | 成功: {stats['success']} | 跳过: {stats['skipped']} | 失败: {stats['failed']}")
            logger.info("=" * 60)

    except Exception as e:
        logger.exception(f"运行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n用户中断")
        sys.exit(0)
