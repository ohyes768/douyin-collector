#!/usr/bin/env python3
"""
取消收藏清理程序
定期清理 file-system-go 中超过指定天数的取消收藏记录
"""

import asyncio
import sys
from pathlib import Path

from loguru import logger

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils import setup_logger, load_config
from src.playwright_adapter import PlaywrightAdapter
from src.uncollected_cleaner import UncollectedCleaner


async def main():
    """主函数"""
    # 加载配置
    try:
        config = load_config("config/app.yaml")
    except FileNotFoundError as e:
        logger.error(str(e))
        logger.error("请先创建配置文件 config/app.yaml")
        sys.exit(1)

    # 设置日志
    log_config = config["app"]["logging"]
    setup_logger(
        level=log_config["level"],
        log_dir=log_config["dir"]
    )

    logger.info("=" * 60)
    logger.info("取消收藏清理程序启动")
    logger.info("=" * 60)

    # 获取清理配置
    cleanup_config = config["app"].get("cleanup", {})
    if not cleanup_config.get("enabled", False):
        logger.info("清理功能未启用，退出")
        sys.exit(0)

    days_threshold = cleanup_config.get("days_threshold", 7)

    # 初始化清理器
    server_url = config["app"]["server"]["url"]
    cleaner = UncollectedCleaner(server_url, days_threshold)

    # 定义取消收藏函数
    async def uncollect_video(aweme_id: str) -> bool:
        """取消收藏视频"""
        logger.info(f"取消收藏视频: {aweme_id}")

        try:
            async with PlaywrightAdapter("config/cookie.yaml") as adapter:
                result = await adapter.uncollect_video_ui(aweme_id)
                return result
        except Exception as e:
            logger.error(f"取消收藏失败: {e}")
            return False

    # 执行清理
    try:
        result = await cleaner.clean_uncollected_records(uncollect_video)

        # 输出结果
        print()
        logger.info("=" * 60)
        logger.info("清理完成")
        logger.info(f"总记录数: {result.total}")
        logger.info(f"处理数量: {result.processed}")
        logger.info(f"成功: {result.success}")
        logger.info(f"失败: {result.failed}")
        logger.info(f"跳过: {result.skipped}")
        logger.info("=" * 60)

        sys.exit(0)

    except Exception as e:
        logger.exception(f"清理失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n已中断")
        sys.exit(0)