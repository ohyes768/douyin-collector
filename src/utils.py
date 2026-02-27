"""
工具函数模块
"""

import json
from pathlib import Path
from loguru import logger


def setup_logger(
    name: str = "douyin-collector",
    log_dir: str = "logs",
    level: str = "INFO"
) -> None:
    """配置日志器"""
    logger.remove()
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # 控制台输出
    logger.add(
        sink=lambda msg: print(msg, end=""),
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level=level,
        colorize=True,
    )

    # 文件输出
    logger.add(
        sink=log_path / "{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level=level,
        rotation="100 MB",
        encoding="utf-8",
    )


def load_config(config_path: str) -> dict:
    """加载配置文件"""
    import yaml
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    with open(config_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config if config else {}


def ensure_dir(dir_path: str) -> None:
    """确保目录存在"""
    Path(dir_path).mkdir(parents=True, exist_ok=True)


def delete_file(filepath: str) -> bool:
    """删除文件"""
    file_path = Path(filepath)
    if not file_path.exists():
        return False
    try:
        file_path.unlink()
        return True
    except Exception:
        return False


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
