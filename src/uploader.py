"""
视频上传器
下载视频、转换为音频（WAV）、上传到 file-system-go 服务器
处理流程：下载 MP4 → 转换为 WAV → 上传 WAV → 删除本地文件
"""

import asyncio
import httpx
from pathlib import Path
from typing import Optional, Dict, Any
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
        self._timeout = config["app"]["server"]["timeout"]
        self._cache_dir = Path(config["app"]["download"]["cache_dir"])
        self._max_retries = config["app"]["processing"]["max_retries"]
        self._retry_delay = config["app"]["processing"]["retry_delay"]
        self._chunk_size = config["app"]["download"]["chunk_size"]

        # 确保缓存目录存在
        ensure_dir(str(self._cache_dir))

        logger.info(f"Uploader ready - Server: {self._server_url}")

    async def check_file_exists(self, filename: str) -> Optional[Dict[str, Any]]:
        """Check if file exists on server

        Args:
            filename: File name

        Returns:
            File info, None if not exists
        """
        url = f"{self._server_url}/api/check/{filename}"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("exists"):
                        logger.info(f"File exists: {filename}")
                        return data
                    return None
                else:
                    logger.warning(f"Check failed: HTTP {response.status_code}")
                    return None

        except Exception as e:
            logger.warning(f"Check error: {e}")
            return None

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
                async with httpx.AsyncClient(timeout=self._config["app"]["download"]["timeout"]) as client:
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

        Args:
            wav_path: WAV file path
            video_info: Video info

        Returns:
            Success or not
        """
        filename = Path(wav_path).name
        url = f"{self._server_url}/upload"

        logger.info(f"Uploading: {filename}")

        for attempt in range(self._max_retries):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    with open(wav_path, "rb") as f:
                        files = {"file": (filename, f, "audio/wav")}
                        # 传递音频元数据
                        data = {
                            "title": video_info.title,
                            "author": video_info.author,
                            "description": video_info.desc,
                        }
                        response = await client.post(url, files=files, data=data)

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
        """Upload video file

        Args:
            filepath: Local file path
            video_info: Video info

        Returns:
            Success or not
        """
        filename = Path(filepath).name
        url = f"{self._server_url}/upload"

        logger.info(f"Uploading: {filename}")

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
        """Process single video: download -> convert to wav -> check -> upload wav -> delete

        Args:
            video_info: Video info

        Returns:
            Process result
        """
        result = {
            "aweme_id": video_info.aweme_id,
            "title": video_info.title,
            "success": False,
            "skipped": False,
            "error": ""
        }

        wav_filename = f"{video_info.aweme_id}.wav"

        # 检查服务器是否已存在 WAV 文件
        exists_info = await self.check_file_exists(wav_filename)
        if exists_info:
            result["skipped"] = True
            result["success"] = True
            logger.info(f"Skip exists: {video_info.title[:30]}...")
            return result

        # 下载视频 (MP4)
        video_path = await self.download_video(video_info)
        if not video_path:
            result["error"] = "Download failed"
            return result

        # 转换为音频 (WAV)
        wav_path = await self.convert_to_wav(video_path)
        if not wav_path:
            result["error"] = "Convert to WAV failed"
            delete_file(video_path)  # 清理 MP4
            return result

        # 上传 WAV 音频
        upload_success = await self.upload_wav(wav_path, video_info)
        if upload_success:
            result["success"] = True
        else:
            result["error"] = "Upload WAV failed"

        # 删除本地文件
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
