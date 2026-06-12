"""
视频上传器
下载视频、转换为音频（WAV）、上传到 file-system-go 服务器
处理流程：下载 MP4 → 转换为 WAV → 上传 WAV → 删除本地文件
"""

import asyncio
import httpx
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from loguru import logger
from ffmpy import FFmpeg

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
        self._processor_url = config["app"]["processor"]["url"]
        self._processor_timeout = config["app"]["processor"].get("timeout", 10)
        self._timeout = config["app"]["server"]["timeout"]
        self._cache_dir = Path(config["app"]["download"]["cache_dir"])
        self._max_retries = config["app"]["processing"]["max_retries"]
        self._retry_delay = config["app"]["processing"]["retry_delay"]
        self._chunk_size = config["app"]["download"]["chunk_size"]

        # 确保缓存目录存在
        ensure_dir(str(self._cache_dir))

        logger.info(f"Uploader ready - Server: {self._server_url}, Processor: {self._processor_url}")

    async def should_upload(self, aweme_id: str) -> bool:
        """调 douyin-processor 的 /api/aweme/{id}/status 端点判断是否需要上传

        Returns:
            True  - douyin-processor 不知道这条，**应该**上传
            False - douyin-processor 已处理过，**不要**上传
        """
        url = f"{self._processor_url}/api/aweme/{aweme_id}/status"
        try:
            async with httpx.AsyncClient(timeout=self._processor_timeout, verify=False) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    # known=True 表示 douyin-processor 已处理过 → 跳过上传
                    # known=False 表示不知道这条 → 需要上传
                    return not data.get("known", True)
                logger.warning(f"Check status non-200: HTTP {response.status_code}")
        except Exception as e:
            logger.warning(f"Check status failed (will upload): {e}")
        return True  # 失败时 fallback 到"传"—— 宁可重复不可漏

    async def notify_pending(
        self,
        aweme_id: str,
        audio_filename: str,
        title: str = "",
        author: str = "",
        description: str = "",
        video_publish_time: str = "",
    ) -> None:
        """上传完 file-system-go 后调，通知 douyin-processor 追加待处理

        调用 /api/aweme/{id}/pending 端点，body 含 audio_filename + metadata
        video_publish_time: 原抖音平台发布时间（ISO8601 字符串，例 "2026-05-20T15:30:00+08:00"）
                            空字符串表示该字段未提供，douyin-processor 端会存为 ""
        """
        url = f"{self._processor_url}/api/aweme/{aweme_id}/pending"
        try:
            async with httpx.AsyncClient(timeout=self._processor_timeout, verify=False) as client:
                response = await client.post(
                    url,
                    json={
                        "audio_filename": audio_filename,
                        "title": title,
                        "author": author,
                        "description": description,
                        "video_publish_time": video_publish_time,
                    },
                )
                if response.status_code == 200:
                    logger.info(f"Added to pending: {aweme_id} ({audio_filename})")
                else:
                    logger.warning(
                        f"Add pending failed: HTTP {response.status_code} "
                        f"for {aweme_id}"
                    )
        except Exception as e:
            logger.error(f"Add pending error for {aweme_id}: {e}")

    async def download_video(self, video_info: VideoInfo) -> Optional[str]:
        """Download video file

        Args:
            video_info: Video info

        Returns:
            Local file path, None if failed
        """
        if not video_info.video_url:
            logger.warning(f"Video {video_info.aweme_id} no URL")
            return None

        filename = f"{video_info.aweme_id}.mp4"
        filepath = self._cache_dir / filename

        # 检查是否已下载
        if filepath.exists():
            logger.info(f"Video cached: {filename}")
            return str(filepath)

        logger.info(f"Downloading: {video_info.title[:30]}...")

        for attempt in range(self._max_retries):
            try:
                # 设置请求头，模拟浏览器访问
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://www.douyin.com/"
                }
                async with httpx.AsyncClient(timeout=self._config["app"]["download"]["timeout"], verify=False) as client:
                    async with client.stream("GET", video_info.video_url, headers=headers) as response:
                        if response.status_code != 200:
                            logger.warning(f"Download failed: HTTP {response.status_code}")
                            if attempt < self._max_retries - 1:
                                await asyncio.sleep(self._retry_delay)
                            continue

                        # 下载文件
                        total_size = 0
                        with open(filepath, "wb") as f:
                            async for chunk in response.aiter_bytes(chunk_size=self._chunk_size):
                                f.write(chunk)
                                total_size += len(chunk)

                        logger.info(f"Downloaded: {filename} ({format_size(total_size)})")
                        return str(filepath)

            except Exception as e:
                logger.warning(f"Download fail ({attempt + 1}/{self._max_retries}): {e}")
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(self._retry_delay)

        logger.error(f"Download failed: {video_info.aweme_id}")
        return None

    async def convert_to_wav(self, video_path: str) -> Optional[str]:
        """Convert video to WAV audio

        Args:
            video_path: Video file path

        Returns:
            WAV file path, None if failed
        """
        video_file = Path(video_path)
        wav_file = video_file.with_suffix(".wav")

        logger.info(f"Converting to WAV: {video_file.name}")

        try:
            # 使用 FFmpeg 提取音频
            ff = FFmpeg(
                inputs={str(video_file): None},
                outputs={
                    str(wav_file): "-vn -acodec pcm_s16le -ar 16000 -ac 1"
                }
            )

            # 执行转换
            await asyncio.to_thread(ff.run)

            if wav_file.exists():
                file_size = wav_file.stat().st_size
                logger.info(f"Converted: {wav_file.name} ({format_size(file_size)})")
                return str(wav_file)
            else:
                logger.error(f"Conversion failed: {video_file.name}")
                return None

        except Exception as e:
            logger.error(f"Conversion error: {e}")
            return None

    async def upload_wav(self, wav_path: str, video_info: VideoInfo) -> bool:
        """Upload WAV audio file

        v2: 不再带 title/author/description form 字段
        （metadata 由 notify_pending 单独发给 douyin-processor）
        """
        filename = Path(wav_path).name
        url = f"{self._server_url}/api/files"

        logger.info(f"Uploading: {filename}")

        for attempt in range(self._max_retries):
            try:
                async with httpx.AsyncClient(timeout=self._timeout, verify=False) as client:
                    with open(wav_path, "rb") as f:
                        files = {"file": (filename, f, "audio/wav")}
                        # v2: 不再带 metadata form 字段
                        response = await client.post(url, files=files)

                    if response.status_code == 200:
                        data = response.json()
                        if data.get("success"):
                            logger.info(f"Uploaded: {filename}")
                            return True
                        else:
                            logger.warning(f"Upload failed: {data.get('error', 'Unknown')}")
                    else:
                        logger.warning(f"Upload failed: HTTP {response.status_code}")

            except Exception as e:
                logger.warning(f"Upload error ({attempt + 1}/{self._max_retries}): {e}")

            if attempt < self._max_retries - 1:
                await asyncio.sleep(self._retry_delay)

        logger.error(f"Upload failed: {filename}")
        return False

    async def upload_video(self, filepath: str, video_info: VideoInfo) -> bool:
        """Upload video file (v2: 不带 metadata)"""
        filename = Path(filepath).name
        url = f"{self._server_url}/api/files"

        logger.info(f"Uploading: {filename}")

        for attempt in range(self._max_retries):
            try:
                async with httpx.AsyncClient(timeout=self._timeout, verify=False) as client:
                    with open(filepath, "rb") as f:
                        files = {"file": (filename, f, "video/mp4")}
                        response = await client.post(url, files=files)

                    if response.status_code == 200:
                        data = response.json()
                        if data.get("success"):
                            logger.info(f"Uploaded: {filename}")
                            return True
                        else:
                            logger.warning(f"Upload failed: {data.get('error', 'Unknown')}")
                    else:
                        logger.warning(f"Upload failed: HTTP {response.status_code}")

            except Exception as e:
                import traceback
                logger.warning(f"Upload error ({attempt + 1}/{self._max_retries}): {type(e).__name__}: {e}")
                logger.debug(f"Trace:\n{traceback.format_exc()}")

            if attempt < self._max_retries - 1:
                await asyncio.sleep(self._retry_delay)

        logger.error(f"Upload failed: {filename}")
        return False

    async def process_video(self, video_info: VideoInfo) -> Dict[str, Any]:
        """v2 流程：查 status → 下载 → 转 WAV → 上传 → 通知 pending

        1. 调 douyin-processor /api/aweme/{id}/status → known=true 跳过
        2. 下载 MP4
        3. 转 WAV
        4. 上传到 file-system-go /api/files
        5. 调 douyin-processor /api/aweme/{id}/pending 通知（含 metadata）
        6. 清理本地
        """
        result = {
            "aweme_id": video_info.aweme_id,
            "title": video_info.title,
            "success": False,
            "skipped": False,
            "error": ""
        }

        audio_filename = f"{video_info.aweme_id}.wav"

        # 1. 查 douyin-processor 状态
        if not await self.should_upload(video_info.aweme_id):
            result["skipped"] = True
            result["success"] = True
            logger.info(f"Skip processed: {video_info.title[:30]}...")
            return result

        # 2. 下载视频 (MP4)
        video_path = await self.download_video(video_info)
        if not video_path:
            result["error"] = "Download failed"
            return result

        # 3. 转换为音频 (WAV)
        wav_path = await self.convert_to_wav(video_path)
        if not wav_path:
            result["error"] = "Convert to WAV failed"
            delete_file(video_path)  # 清理 MP4
            return result

        # 4. 上传 WAV 音频到 file-system-go
        upload_success = await self.upload_wav(wav_path, video_info)
        if not upload_success:
            result["error"] = "Upload WAV failed"
            delete_file(video_path)
            delete_file(wav_path)
            return result

        # 5. 通知 douyin-processor 追加待处理（含 metadata）
        #    video_publish_time：原抖音平台发布时间（秒级时间戳 → ISO8601 字符串）
        #    抖音 API 返回的 create_time 假定为秒级（v1 时期沿用约定）；
        #    若 > 1e12 视为毫秒戳，自动 /1000 兼容
        ts = video_info.create_time
        if ts > 10**12:  # 13 位毫秒戳兼容
            ts = ts / 1000
        video_publish_time = (
            datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else ""
        )
        await self.notify_pending(
            aweme_id=video_info.aweme_id,
            audio_filename=audio_filename,
            title=video_info.title,
            author=video_info.author,
            description=video_info.desc,
            video_publish_time=video_publish_time,
        )

        result["success"] = True

        # 6. 清理本地
        delete_file(video_path)
        delete_file(wav_path)

        return result

    async def process_videos(
        self,
        videos: list[VideoInfo],
        progress_callback=None
    ) -> Dict[str, Any]:
        """Process videos in batch

        Args:
            videos: Video list
            progress_callback: Progress callback

        Returns:
            Process stats
        """
        total = len(videos)
        success = 0
        skipped = 0
        failed = 0

        logger.info(f"Processing {total} videos...")

        for i, video in enumerate(videos, 1):
            logger.info(f"[{i}/{total}] {video.title[:30]}...")

            result = await self.process_video(video)

            if result["skipped"]:
                skipped += 1
            elif result["success"]:
                success += 1
            else:
                failed += 1
                logger.error(f"Failed: {video.title[:30]}... - {result['error']}")

            # 进度回调
            if progress_callback:
                progress_callback(i, total, success, skipped, failed)

        stats = {
            "total": total,
            "success": success,
            "skipped": skipped,
            "failed": failed
        }

        logger.info(f"Done - OK: {success}, Skip: {skipped}, Fail: {failed}")
        return stats
