# douyin-collector 架构重构方案（Windows端）

## 1. 项目概述

**项目名称**：douyin-collector
**职责**：Windows端视频采集和上传
**运行环境**：Windows本地
**运行方式**：每天定时运行的自动化脚本

## 2. 核心功能

1. 使用Playwright获取抖音收藏视频列表
2. 下载视频文件（100MB以内）
3. 通过HTTP API上传到服务器
4. Cookie本地YAML存储
5. 下载失败时跳过并记录日志
6. Cookie失效时仅记录日志

## 3. 目录结构

```
douyin-collector/
├── src/
│   ├── __init__.py
│   ├── collector.py          # 视频采集逻辑（从现有项目复用）
│   ├── cookie_manager.py     # Cookie管理（简化版）
│   ├── playwright_adapter.py # Playwright适配器（从现有项目复用）
│   ├── models.py             # 数据模型（简化版）
│   ├── uploader.py           # 上传器（新建）
│   ├── config_loader.py      # 配置加载（新建）
│   └── utils.py              # 工具函数
├── scripts/
│   ├── run.bat              # Windows启动脚本
│   ├── install_deps.bat     # 依赖安装
│   └── setup_task.bat       # 定时任务设置
├── config/
│   └── app.yaml             # 应用配置
├── cache/videos/            # 视频缓存
├── logs/                    # 日志目录（不自动清理）
├── main.py                  # 主入口
├── pyproject.toml           # 项目配置
└── README.md
```

## 4. 配置文件（config/app.yaml）

```yaml
app:
  # Cookie配置
  cookie:
    path: "config/cookie.yaml"

  # 采集配置
  collector:
    max_videos: 50
    min_duration: 5
    max_duration: 300
    max_file_size: 104857600  # 100MB
    exclude_products: true
    retry_count: 3
    retry_delay: 5

  # 上传配置
  uploader:
    server_url: "http://your-ecs-ip:8000"
    upload_endpoint: "/api/video/upload"
    timeout: 60
    retry_count: 3
    chunk_size: 1048576

  # 日志配置
  logging:
    level: "INFO"
    console: true
    file: true
    # 不自动清理
```

## 5. 服务器API接口

### 视频上传接口

**端点**：`POST /api/video/upload`

**请求**：
```http
Content-Type: multipart/form-data

file: <binary>              # 视频文件
metadata: <json string>     # 元数据（可选）
```

**元数据格式**：
```json
{
  "aweme_id": "7123456789012345678",
  "title": "视频标题",
  "author": "作者昵称",
  "duration": 60,
  "size": 102400000
}
```

**成功响应**：
```json
{
  "success": true,
  "message": "文件上传成功",
  "data": {
    "filename": "7123456789012345678.mp4",
    "size": 102400000,
    "upload_time": "2024-01-01T12:00:00Z"
  }
}
```

## 6. 核心模块设计

### 6.1 uploader.py（新建）

```python
"""
视频上传器
负责将下载的视频上传到服务器
"""

import httpx
from pathlib import Path
from typing import Optional, Dict
from loguru import logger

class VideoUploader:
    """视频上传器"""

    def __init__(self, config: dict):
        self.server_url = config["uploader"]["server_url"]
        self.endpoint = config["uploader"]["upload_endpoint"]
        self.timeout = config["uploader"]["timeout"]
        self.retry_count = config["uploader"]["retry_count"]

    async def upload_video(
        self,
        video_path: Path,
        metadata: dict
    ) -> bool:
        """上传视频到服务器

        Args:
            video_path: 视频文件路径
            metadata: 视频元数据

        Returns:
            是否上传成功
        """
        # 实现上传逻辑
        pass
```

### 6.2 config_loader.py（新建）

```python
"""
配置加载器
加载YAML配置文件
"""

import yaml
from pathlib import Path
from typing import dict

def load_config(config_path: str) -> dict:
    """加载配置文件"""
    pass

def save_config(config_path: str, config: dict) -> None:
    """保存配置文件"""
    pass
```

## 7. 复用现有代码

从现有项目 `douying-collect` 复用以下模块：

| 原文件 | 目标文件 | 修改说明 |
|--------|----------|----------|
| `src/collector.py` | `src/collector.py` | 移除处理相关逻辑，保留采集功能 |
| `src/playwright_adapter.py` | `src/playwright_adapter.py` | 直接复用 |
| `src/cookie_manager.py` | `src/cookie_manager.py` | 简化为YAML存储 |
| `src/models.py` | `src/models.py` | 只保留VideoInfo相关模型 |
| `src/utils.py` | `src/utils.py` | 提取公共工具函数 |

## 8. 启动脚本（scripts/run.bat）

```batch
@echo off
cd /d %~dp0..
python main.py
pause
```

## 9. 定时任务设置（scripts/setup_task.bat）

```batch
@echo off
echo 设置每天定时任务...
schtasks /create /tn "douyin-collector" /tr "F:\path\to\douyin-collector\scripts\run.bat" /sc daily /st 02:00
echo 任务已创建
pause
```

## 10. 依赖项（pyproject.toml）

```toml
[project]
name = "douyin-collector"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = [
    "playwright",
    "httpx",
    "pyyaml",
    "loguru",
]
```

## 11. 实施步骤

1. 创建项目目录结构
2. 从现有项目复制并简化代码
3. 新建 uploader.py 和 config_loader.py
4. 创建配置文件
5. 创建启动脚本
6. 本地测试

## 12. 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| Windows反检测失效 | 保留现有反检测机制 |
| 下载失败 | 跳过并记录日志 |
| Cookie失效 | 仅记录日志，人工更新 |
| 上传失败 | 简单重试机制（3次） |
