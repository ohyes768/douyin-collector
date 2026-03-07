"""
数据模型定义
"""

from dataclasses import dataclass


@dataclass
class VideoInfo:
    """视频信息"""
    aweme_id: str              # 视频ID
    title: str                 # 视频标题
    author: str                # 作者昵称
    video_url: str             # 视频URL
    desc: str = ""             # 视频描述
    create_time: int = 0       # 创建时间戳
    is_product: bool = False   # 是否为商品视频


@dataclass
class UncollectedRecord:
    """取消收藏记录"""
    filename: str              # 文件名，如 "123456789.wav"
    uncollected_at: str        # 取消收藏时间，RFC3339 格式


@dataclass
class ReadFileRecord:
    """已读文件记录"""
    filename: str              # 文件名，如 "123456789.wav"
    read_at: str               # 已读时间，RFC3339 格式


@dataclass
class CleanupResult:
    """清理结果"""
    total: int                 # 总记录数
    processed: int             # 处理数量
    success: int               # 成功数量
    failed: int                # 失败数量
    skipped: int               # 跳过数量
