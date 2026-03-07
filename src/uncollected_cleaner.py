"""
取消收藏清理器模块
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from loguru import logger
import httpx

from src.models import UncollectedRecord, CleanupResult


class UncollectedCleaner:
    """取消收藏清理器"""

    def __init__(self, server_url: str, days_threshold: int = 7):
        """初始化清理器

        Args:
            server_url: file-system-go 服务器地址
            days_threshold: 天数阈值，默认 7 天
        """
        self._server_url = server_url
        self._days_threshold = days_threshold
        logger.info(f"Cleaner ready - Days threshold: {days_threshold}")

    async def get_uncollected_records(self) -> List[UncollectedRecord]:
        """获取所有取消收藏记录"""
        url = f"{self._server_url}/api/uncollected/files"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        records = []
                        for item in data.get("records", []):
                            records.append(UncollectedRecord(
                                filename=item.get("filename", ""),
                                uncollected_at=item.get("uncollected_at", "")
                            ))
                        logger.debug(f"获取到 {len(records)} 条取消收藏记录")
                        return records
                else:
                    logger.warning(f"获取记录失败: HTTP {response.status_code}")
                    return []
        except Exception as e:
            logger.error(f"获取记录异常: {e}")
            return []

    async def remove_uncollected_record(self, filename: str) -> bool:
        """删除取消收藏记录"""
        url = f"{self._server_url}/api/uncollected/remove"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.delete(url, json={"filename": filename})

                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        logger.debug(f"已删除记录: {filename}")
                        return True
                return False
        except Exception as e:
            logger.error(f"删除记录异常: {e}")
            return False

    @staticmethod
    def extract_aweme_id(filename: str) -> str:
        """从文件名提取 aweme_id"""
        return Path(filename).stem

    def is_over_threshold(self, uncollected_at: str) -> bool:
        """判断是否超过阈值天数"""
        try:
            uncollected_time = datetime.fromisoformat(
                uncollected_at.replace('Z', '+00:00')
            )
            threshold_time = datetime.now(uncollected_time.tzinfo) - timedelta(days=self._days_threshold)
            return uncollected_time < threshold_time
        except Exception as e:
            logger.warning(f"解析时间失败: {uncollected_at}, {e}")
            return False

    async def process_single_record(
        self,
        record: UncollectedRecord,
        uncollect_func
    ) -> bool:
        """处理单条记录

        Args:
            record: 取消收藏记录
            uncollect_func: 取消收藏的异步函数

        Returns:
            是否处理成功
        """
        aweme_id = self.extract_aweme_id(record.filename)

        # 调用取消收藏函数
        success = await uncollect_func(aweme_id)

        if success:
            # 删除记录
            await self.remove_uncollected_record(record.filename)
            logger.info(f"成功处理: {record.filename}")
        else:
            logger.warning(f"处理失败: {record.filename}")

        return success

    async def clean_uncollected_records(self, uncollect_func) -> CleanupResult:
        """清理超过阈值的取消收藏记录

        Args:
            uncollect_func: 取消收藏的异步函数，接收 aweme_id 参数

        Returns:
            清理结果
        """
        result = CleanupResult(total=0, processed=0, success=0, failed=0, skipped=0)

        # 获取所有记录
        records = await self.get_uncollected_records()
        result.total = len(records)

        if not records:
            logger.info("没有需要处理的记录")
            return result

        # 筛选超过阈值的记录
        overdue_records = [
            r for r in records
            if self.is_over_threshold(r.uncollected_at)
        ]

        if not overdue_records:
            logger.info(f"没有超过 {self._days_threshold} 天的记录")
            return result

        logger.info(f"发现 {len(overdue_records)} 条超过 {self._days_threshold} 天的记录")
        result.processed = len(overdue_records)

        # 处理每条记录
        for record in overdue_records:
            success = await self.process_single_record(record, uncollect_func)

            if success:
                result.success += 1
            else:
                result.failed += 1

        return result