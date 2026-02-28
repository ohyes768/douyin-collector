# douyin-collector

抖音收藏视频采集工具（Windows 客户端）

## 功能

- 采集抖音收藏视频（使用 Playwright）
- 下载视频文件到本地
- **转换为 WAV 音频格式**
- **上传 WAV 音频到 file-system-go 服务器**
- 支持时间过滤（默认最近 7 天）
- 支持增量处理（跳过已上传视频）
- 自动重试机制

## 处理流程

```
采集视频列表
    ↓
下载 MP4 视频
    ↓
转换为 WAV 音频 (FFmpeg)
    ↓
上传 WAV 到 file-system-go
    ↓
删除本地文件
```

## 安装

```bash
# 安装依赖
scripts\install.bat
```

## 配置

### 1. 修改服务器地址

编辑 `config/app.yaml`：

```yaml
app:
  server:
    url: "http://your-ecs-ip:8000"  # 修改为实际地址
```

### 2. 配置 Cookie

编辑 `config/cookie.yaml`，填入实际的 Cookie：

```yaml
douyin:
  cookie: "your_actual_cookie_here"
```

**获取 Cookie 方法**：
1. 打开浏览器，访问 https://www.douyin.com
2. 登录账号
3. 打开开发者工具（F12）
4. 切换到 Network 标签
5. 刷新页面
6. 找到任意请求，查看 Request Headers
7. 复制 Cookie 字段的值

## 使用

```bash
# 运行
scripts\run.bat
```

## 配置选项

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `days_limit` | 采集最近 N 天的视频 | 7 |
| `max_videos` | 最大采集数量，0 表示不限制 | 0 |
| `exclude_products` | 是否排除商品视频 | true |
| `max_retries` | 失败重试次数 | 3 |

## 项目结构

```
douyin-collector/
├── src/                    # 源代码
│   ├── collector.py        # 采集器
│   ├── uploader.py         # 上传器（含音频转换）
│   ├── playwright_adapter.py
│   ├── cookie_manager.py
│   ├── models.py
│   └── utils.py
├── config/                 # 配置文件
│   ├── app.yaml
│   └── cookie.yaml
├── scripts/                # 脚本
│   ├── run.bat
│   └── install.bat
├── logs/                   # 日志目录
├── cache/audios/           # 音频缓存（临时）
├── main.py                 # 主入口
└── pyproject.toml
```

## 相关项目

- [douying-collect](../douying-collect) - 原始项目
- [file-system-go](../file-system-go) - 文件服务器（存储 WAV 音频）
- [douyin-processor](../douyin-processor) - 音频处理器（ASR 识别）

## 文档

- [API 接口文档](docs/API接口文档.md)
- [数据字典](docs/数据字典.md)
- [技术规范文档](discuss/douyin-collector-技术规范.md)
- [架构重构方案](discuss/架构重构方案-Windows端.md)

## 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| 1.1.0 | 2026-02-28 | 更新架构：转换为 WAV 后上传音频 |
| 1.0.0 | 2026-02-26 | 初始版本 |
