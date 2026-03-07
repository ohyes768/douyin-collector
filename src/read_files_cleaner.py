"""
已读文件清理器模块
"""

from datetime import datetime, timedelta
from typing import List

from loguru import logger
import httpx

from src.models import ReadFileRecord, CleanupResult


class ReadFilesCleaner:
    """已读文件清理器"""

    def __init__(self, server_url: str, days_threshold: int = 7):
        """初始化清理器

        Args:
            server_url: file-system-go 服务器地址
            days_threshold: 天数阈值，默认 7 天
        """
        self._server_url = server_url
        self._days_threshold = days_threshold
        logger.info(f"ReadFilesCleaner ready - Days threshold: {days_threshold}")

    async def get_read_records(self) -> List[ReadFileRecord]:
        """获取所有已读文件记录"""
        url = f"{self._server_url}/api/read/files"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        records = []
                        for item in data.get("records", []):
                            records.append(ReadFileRecord(
                                filename=item.get("filename", ""),
                                read_at=item.get("read_at", "")
                            ))
                        logger.debug(f"获取到 {len(records)} 条已读记录")
                        return records
                else:
                    logger.warning(f"获取记录失败: HTTP {response.status_code}")
                    return []
        except Exception as e:
            logger.error(f"获取记录异常: {e}")
            return []

    async def delete_file(self, filename: str) -> bool:
        """删除文件（会同时删除 wav 和 meta.json）"""
        url = f"{self._server_url}/api/file/{filename}"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.delete(url)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        logger.debug(f"已删除文件: {filename}")
                        return True
                return False
        except Exception as e:
            logger.error(f"删除文件异常: {e}")
            return False

    async def remove_read_record(self, filename: str) -> bool:
        """删除已读记录"""
        url = f"{self._server_url}/api/read/remove"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.delete(url, json={"filename": filename})

                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        logger.debug(f"已删除已读记录: {filename}")
                        return True
                return False
        except Exception as e:
            logger.error(f"删除已读记录异常: {e}")
            return False

    def is_over_threshold(self, read_at: str) -> bool:
        """判断是否超过阈值天数"""
        try:
            read_time = datetime.fromisoformat(
                read_at.replace('Z', '+00:00')
            )
            threshold_time = datetime.now(read_time.tzinfo) - timedelta(days=self._days_threshold)
            return read_time < threshold_time
        except Exception as e:
            logger.warning(f"解析时间失败: {read_at}, {e}")
            return False

    async def process_single_record(self, record: ReadFileRecord) -> bool:
        """处理单条记录

        Args:
            record: 已读文件记录

        Returns:
            是否处理成功
        """
        logger.info(f"处理已读文件: {record.filename}")

        # 删除文件（会同时删除 wav 和 meta.json）
        delete_success = await self.delete_file(record.filename)

        if delete_success:
            # 删除已读记录
            await self.remove_read_record(record.filename)
            logger.info(f"成功处理: {record.filename}")
            return True
        else:
            logger.warning(f"处理失败: {record.filename}")
            return False

    async def clean_read_files(self) -> CleanupResult:
        """清理超过阈值的已读文件

        Returns:
            清理结果
        """
        result = CleanupResult(total=0, processed=0, success=0, failed=0, skipped=0)

        # 获取所有记录
        records = await self.get_read_records()
        result.total = len(records)

        if not records:
            logger.info("没有需要处理的记录")
            return result

        # 筛选超过阈值的记录
        overdue_records = [
            r for r in records
            if self.is_over_threshold(r.read_at)
        ]

        if not overdue_records:
            logger.info(f"没有超过 {self._days_threshold} 天的记录")
            return result

        logger.info(f"发现 {len(overdue_records)} 条超过 {self._days_threshold} 天的记录")
        result.processed = len(overdue_records)

        # 处理每条记录
        for record in overdue_records:
            success = await self.process_single_record(record)

            if success:
                result.success += 1
            else:
                result.failed += 1

        return result