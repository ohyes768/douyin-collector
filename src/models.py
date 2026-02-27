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
