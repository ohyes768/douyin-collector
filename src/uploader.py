"""
视频上传器
下载视频并上传到 file-system-go 服务器
"""

import asyncio
import httpx
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger

from src.models import VideoInfo
from src.utils import ensure_dir, delete_file, format_size


class VideoUploader:
    """视频上传器"""

    def __init__(self, config: dict):
        """初始化上传器

        Args:
            config: 应用配置
        """
        self._config = config
        self._server_url = config["app"]["server"]["url"]
        self._timeout = config["app"]["server"]["timeout"]
        self._cache_dir = Path(config["app"]["download"]["cache_dir"])
        self._max_retries = config["app"]["processing"]["max_retries"]
        self._retry_delay = config["app"]["processing"]["retry_delay"]
        self._chunk_size = config["app"]["download"]["chunk_size"]

        # 确保缓存目录存在
        ensure_dir(str(self._cache_dir))

        logger.info(f"上传器初始化完成 - 服务器: {self._server_url}")

    async def check_file_exists(self, filename: str) -> Optional[Dict[str, Any]]:
        """检查服务器上是否已存在文件

        Args:
            filename: 文件名

        Returns:
            文件信息，不存在返回 None
        """
        url = f"{self._server_url}/api/check/{filename}"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("exists"):
                        logger.info(f"文件已存在: {filename}")
                        return data
                    return None
                else:
                    logger.warning(f"检查文件失败: {response.status_code}")
                    return None

        except Exception as e:
            logger.warning(f"检查文件存在失败: {e}")
            return None

    async def download_video(self, video_info: VideoInfo) -> Optional[str]:
        """下载视频文件

        Args:
            video_info: 视频信息

        Returns:
            本地文件路径，失败返回 None
        """
        if not video_info.video_url:
            logger.warning(f"视频 {video_info.aweme_id} 没有下载链接")
            return None

        filename = f"{video_info.aweme_id}.mp4"
        filepath = self._cache_dir / filename

        # 检查是否已下载
        if filepath.exists():
            logger.info(f"视频已下载: {filename}")
            return str(filepath)

        logger.info(f"开始下载视频: {video_info.title[:30]}...")

        for attempt in range(self._max_retries):
            try:
                # 设置请求头，模拟浏览器访问
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://www.douyin.com/"
                }
                async with httpx.AsyncClient(timeout=self._config["app"]["download"]["timeout"]) as client:
                    async with client.stream("GET", video_info.video_url, headers=headers) as response:
                        if response.status_code != 200:
                            logger.warning(f"下载失败: HTTP {response.status_code}")
                            if attempt < self._max_retries - 1:
                                await asyncio.sleep(self._retry_delay)
                            continue

                        # 下载文件
                        total_size = 0
                        with open(filepath, "wb") as f:
                            async for chunk in response.aiter_bytes(chunk_size=self._chunk_size):
                                f.write(chunk)
                                total_size += len(chunk)

                        logger.info(f"下载完成: {filename} ({format_size(total_size)})")
                        return str(filepath)

            except Exception as e:
                logger.warning(f"下载失败 (尝试 {attempt + 1}/{self._max_retries}): {e}")
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(self._retry_delay)

        logger.error(f"下载失败: {video_info.aweme_id}")
        return None

    async def upload_video(self, filepath: str, video_info: VideoInfo) -> bool:
        """上传视频文件

        Args:
            filepath: 本地文件路径
            video_info: 视频信息

        Returns:
            是否成功
        """
        filename = Path(filepath).name
        url = f"{self._server_url}/upload"

        logger.info(f"开始上传: {filename}")

        for attempt in range(self._max_retries):
            try:
                # AsyncClient 在外层，open 在内层（与旧项目一致）
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    with open(filepath, "rb") as f:
                        files = {"file": (filename, f, "video/mp4")}
                        # 传递视频元数据
                        data = {
                            "title": video_info.title,
                            "author": video_info.author,
                            "description": video_info.desc,
                        }
                        response = await client.post(url, files=files, data=data)

                    if response.status_code == 200:
                        data = response.json()
                        if data.get("success"):
                            logger.info(f"上传成功: {filename}")
                            return True
                        else:
                            logger.warning(f"上传失败: {data.get('error', 'Unknown')}")
                    else:
                        logger.warning(f"上传失败: HTTP {response.status_code}")

            except Exception as e:
                import traceback
                logger.warning(f"上传失败 (尝试 {attempt + 1}/{self._max_retries}): {type(e).__name__}: {e}")
                logger.debug(f"详细错误:\n{traceback.format_exc()}")

            if attempt < self._max_retries - 1:
                await asyncio.sleep(self._retry_delay)

        logger.error(f"上传失败: {filename}")
        return False

    async def process_video(self, video_info: VideoInfo) -> Dict[str, Any]:
        """处理单个视频：下载 -> 检查 -> 上传 -> 删除

        Args:
            video_info: 视频信息

        Returns:
            处理结果
        """
        result = {
            "aweme_id": video_info.aweme_id,
            "title": video_info.title,
            "success": False,
            "skipped": False,
            "error": ""
        }

        filename = f"{video_info.aweme_id}.mp4"

        # 检查服务器是否已存在
        exists_info = await self.check_file_exists(filename)
        if exists_info:
            result["skipped"] = True
            result["success"] = True
            logger.info(f"跳过已存在: {video_info.title[:30]}...")
            return result

        # 下载视频
        filepath = await self.download_video(video_info)
        if not filepath:
            result["error"] = "下载失败"
            return result

        # 上传视频
        upload_success = await self.upload_video(filepath, video_info)
        if upload_success:
            result["success"] = True
        else:
            result["error"] = "上传失败"

        # 删除本地文件
        if delete_file(filepath):
            logger.debug(f"已删除本地文件: {filename}")

        return result

    async def process_videos(
        self,
        videos: list[VideoInfo],
        progress_callback=None
    ) -> Dict[str, Any]:
        """批量处理视频

        Args:
            videos: 视频列表
            progress_callback: 进度回调函数

        Returns:
            处理统计
        """
        total = len(videos)
        success = 0
        skipped = 0
        failed = 0

        logger.info(f"开始处理 {total} 个视频...")

        for i, video in enumerate(videos, 1):
            logger.info(f"[{i}/{total}] 处理: {video.title[:30]}...")

            result = await self.process_video(video)

            if result["skipped"]:
                skipped += 1
            elif result["success"]:
                success += 1
            else:
                failed += 1
                logger.error(f"处理失败: {video.title[:30]}... - {result['error']}")

            # 进度回调
            if progress_callback:
                progress_callback(i, total, success, skipped, failed)

        stats = {
            "total": total,
            "success": success,
            "skipped": skipped,
            "failed": failed
        }

        logger.info(f"处理完成: 成功 {success}, 跳过 {skipped}, 失败 {failed}")
        return stats
