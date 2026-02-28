# douyin-collector 技术规范文档

## 1. 概述

### 1.1 背景
从现有 `douying-collect` 项目迁移代码，创建一个简化的 Windows 端视频采集工具，负责采集抖音收藏视频、转换为音频并上传到服务器。

### 1.2 目标
- **核心目标**：采集抖音收藏视频 → 下载 MP4 → 使用 FFmpeg 转换为 WAV 音频 → 上传 WAV 到 file-system-go 服务器
- **附加目标**：支持时间过滤、增量处理、自动重试
- **非目标**：不做 ASR 识别（由 douyin-processor 直接使用服务器 URL 进行）

### 1.3 项目关系
```
douyin-collector (Windows 客户端)
    ↓ 采集视频 → 转换为 WAV 音频
file-system-go (ECS 文件服务器)
    ↓ 存储 WAV 文件，提供公开 URL
douyin-processor (Linux 服务器)
    ↓ 使用 URL 调用 ASR 识别
前端/n8n
    ↓ 获取识别结果
```

## 2. 功能需求

### 2.1 核心功能

| 功能 | 优先级 | 描述 |
|------|--------|------|
| 视频采集 | P0 | 使用 Playwright 获取抖音收藏视频列表 |
| 视频下载 | P0 | 下载 MP4 视频文件到本地缓存 |
| 音频转换 | P0 | 使用 FFmpeg 将 MP4 转换为 WAV（16kHz, mono, PCM） |
| 音频上传 | P0 | 上传 WAV 音频到 file-system-go 服务器 |
| 时间过滤 | P1 | 默认采集最近 7 天的视频 |
| 增量处理 | P1 | 检查服务器是否已存在 WAV 文件，跳过重复文件 |
| 自动重试 | P1 | 失败自动重试 3 次 |

### 2.2 用户故事

```
用户 → 运行脚本
     → 采集最近 7 天的收藏视频
     → 逐个下载 MP4 视频
     → 使用 FFmpeg 转换为 WAV 音频
     → 检查服务器是否已存在 WAV 文件
     → 不存在则上传 WAV，存在则跳过
     → 上传成功后删除本地 MP4 和 WAV 文件
     → 显示简单进度
     → 完成
```

## 3. 技术决策

### 3.1 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 主要开发语言 |
| Playwright | 最新版 | 浏览器自动化采集 |
| httpx | 最新版 | HTTP 客户端（下载、上传） |
| PyYAML | 最新版 | 配置文件解析 |
| Loguru | 最新版 | 日志管理 |
| uv | 最新版 | Python 包管理工具 |

### 3.2 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py                              │
│                      主控制器入口                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      collector.py                           │
│                  采集器（复用现有代码）                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      uploader.py                            │
│                    上传器（新建）                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  下载视频    │  │  转换音频    │  │  上传音频    │      │
│  │   (MP4)      │  │  (MP4→WAV)   │  │   (WAV)      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 方案权衡记录

| 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|
| 配置文件 | 单/双 | 单个 app.yaml | 简化配置管理 |
| 上传内容 | 视频/音频 | WAV 音频 | ASR 需要纯音频，节省存储和带宽 |
| 并发策略 | 并发/串行 | 串行处理 | 更稳定，易于调试 |
| 进度显示 | 详细/简单 | 简单进度 | 满足需求即可 |
| 文件清理 | 保留/删除 | 立即删除 | 节省本地空间 |
| 增量处理 | 需要/不需要 | 服务器检查 | 避免重复上传 |

## 4. 数据设计

### 4.1 数据模型（复用）

```python
@dataclass
class VideoInfo:
    """视频信息"""
    aweme_id: str          # 视频 ID
    title: str             # 视频标题
    author: str            # 作者昵称
    video_url: str         # 视频 URL
    desc: str = ""         # 视频描述
    create_time: int = 0   # 创建时间戳
```

### 4.2 配置文件（config/app.yaml）

```yaml
app:
  # 服务器配置
  server:
    url: "http://your-ecs-ip:8000"
    timeout: 60
    check_endpoint: "/api/check"
    upload_endpoint: "/upload"

  # Cookie 配置
  cookie:
    # 从现有 douying-collect 复制
    path: "config/cookie.yaml"

  # 采集配置
  collector:
    days_limit: 7          # 默认最近 7 天
    max_videos: 0          # 0 表示不限制
    max_file_size: 104857600  # 100MB
    exclude_products: true

  # 下载配置
  download:
    cache_dir: "cache/audios"
    chunk_size: 1048576    # 1MB
    timeout: 300

  # 处理配置
  processing:
    max_retries: 3
    retry_delay: 5
    serial: true           # 串行处理

  # 日志配置
  logging:
    level: "INFO"
    console: true
    file: true
    dir: "logs"
    auto_cleanup: false    # 不自动清理
```

### 4.3 Cookie 文件（config/cookie.yaml）

```yaml
# 从现有 douying-collect 复制
douyin:
  cookie: "your_cookie_here"
  timeout: 30
  max_retries: 3
```

## 5. API 接口设计

### 5.1 检查文件接口（需添加到 file-system-go）

**端点**：`GET /api/check/{filename}`

**响应（文件存在）**：
```json
{
  "exists": true,
  "filename": "7123456789012345678.wav",
  "size": 5120000,
  "upload_time": "2024-01-01T12:00:00Z"
}
```

**响应（文件不存在）**：
```json
{
  "exists": false,
  "filename": "7123456789012345678.wav"
}
```

### 5.2 上传文件接口（现有）

**端点**：`POST /upload`

**请求**：
```http
Content-Type: multipart/form-data

file: <binary>              # WAV 音频文件
title: 视频标题
author: 作者昵称
description: 视频描述
```

**响应**：
```json
{
  "success": true,
  "filename": "7123456789012345678.wav",
  "url": "/audio/7123456789012345678.wav",
  "size": 5120000
}
```

## 6. 非功能需求

### 6.1 性能要求
- 单视频处理时间：视网络情况而定
- 串行处理，不追求高并发

### 6.2 可靠性要求
- Cookie 失效：日志 + 醒目提示
- 网络中断：自动重试
- 服务器不可达：继续下载，暂存缓存

### 6.3 可维护性
- 代码复用现有项目
- 单文件不超过 300 行
- 完善的日志记录

## 7. 边缘情况与错误处理

### 7.1 异常场景

| 场景 | 处理策略 |
|------|----------|
| Cookie 失效 | 记录日志 + 醒目提示 |
| 网络中断 | 自动重试，超过次数后跳过 |
| 服务器不可达 | 继续下载，暂存缓存 |
| 下载失败 | 重试后跳过，记录日志 |
| 上传失败 | 重试后跳过，保留本地文件 |

### 7.2 降级策略

| 级别 | 策略 |
|------|------|
| 服务器完全不可达 | 继续下载所有视频，暂存 cache 目录 |
| Cookie 失效 | 立即停止，提示用户更新 |

## 8. 实施计划

### 8.1 开发阶段

1. ✅ 需求分析和技术规范
2. 创建项目目录结构
3. 从现有项目复用代码
4. 创建配置文件
5. 实现 uploader.py
6. 实现 collector.py
7. 实现 main.py
8. 创建启动脚本
9. 测试完整流程

### 8.2 file-system-go 改造

1. 添加 `GET /api/check/{filename}` 接口
2. 返回文件存在信息和元数据

## 9. 用户访谈记录

### 9.1 关键决策点

| 决策 | 用户选择 | 理由 |
|------|----------|------|
| 架构关系 | 从现有项目迁移 | 复用已有代码 |
| 开发顺序 | 先开发 collector | 客户端优先 |
| 本地测试 | 连真实 ECS 服务器 | 文件服务用真实环境 |
| 代码复用 | 能复用的都复用 | 提高效率 |
| Cookie 管理 | 保持 YAML 格式 | 兼容现有 |
| 上传方式 | 上传+元数据 | 需要改造 file-system-go |
| 失败处理 | 重试后跳过 | 提高成功率 |
| 运行方式 | 手动运行 | 按需执行 |
| 配置管理 | 单个 app.yaml | 简化配置 |
| 时间过滤 | 默认 7 天 | 灵活可控 |
| 视频清理 | 立即删除 | 节省空间 |
| 增量处理 | 服务器检查 | 避免重复 |
| 检查接口 | 返回文件信息 | 便于调试 |
| 并发策略 | 串行处理 | 稳定可靠 |
| 进度显示 | 简单进度 | 满足需求 |

## 10. 附录

### 10.1 目录结构

```
douyin-collector/
├── src/
│   ├── __init__.py
│   ├── collector.py          # 采集器（复用）
│   ├── playwright_adapter.py # Playwright 适配器（复用）
│   ├── uploader.py           # 上传器（含 FFmpeg 转换）
│   ├── models.py             # 数据模型（复用）
│   └── utils.py              # 工具函数（复用）
├── config/
│   ├── app.yaml              # 应用配置（新建）
│   └── cookie.yaml           # Cookie 配置（从现有复制）
├── scripts/
│   └── run.bat               # Windows 启动脚本（新建）
├── cache/
│   └── audios/               # 音频缓存目录（临时）
├── logs/                     # 日志目录（不自动清理）
├── main.py                   # 主入口（新建）
├── pyproject.toml            # 项目配置（新建）
└── README.md                 # 项目文档（新建）
```

### 10.2 相关项目

- 现有项目：`F:/github/person_project/douying-collect`
- 文件服务器：`F:/github/person_project/file-system-go`
- 处理服务器：`F:/github/person_project/douyin-processor`

---

**文档版本**: v1.1
**创建时间**: 2026-02-26
**更新时间**: 2026-02-28
**状态**: ✅ 架构已更新，WAV 音频处理流程
