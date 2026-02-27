# douyin-collector 变更日志

## [1.0.1] - 2026-02-27

### Bug 修复

- 🐛 修复视频下载 HTTP 403 错误
  - 添加 User-Agent 和 Referer 请求头
  - 模拟浏览器访问
- 🐛 修复视频上传 ReadError 错误
  - 调整 AsyncClient 和文件打开的顺序
  - 将 AsyncClient 放在外层，open 放在内层
- 🐛 修复 API 接口路径错误
  - 上传接口从 `/api/upload` 改为 `/upload`
  - 保持与 file-system-go 服务器一致

### 功能改进

- ✨ 上传时传递视频元数据
  - 标题 (title)
  - 作者 (author)
  - 描述 (description)
- 🔒 安全改进
  - 将敏感配置文件添加到 .gitignore
  - 创建 app.yaml.example 示例文件

### 配置

- ⚙️ 增加上传超时时间至 300 秒
- ⏱️ 调整下载超时时间至 300 秒

---

## [1.0.0] - 2026-02-26

### 新增

- ✨ Windows 端抖音收藏视频采集器
  - 使用 Playwright 浏览器自动化采集
  - 支持时间过滤（默认最近 7 天）
  - 支持排除商品视频
- 📤 视频上传功能
  - 下载视频到本地缓存
  - 上传到 file-system-go 服务器
  - 上传成功后自动删除本地文件
- 🔄 增量处理
  - 检查服务器是否已存在文件
  - 跳过已上传的视频
- 🔁 自动重试机制
  - 下载失败自动重试
  - 上传失败自动重试
  - 可配置重试次数和延迟

### 配置

- 📝 单配置文件设计 (config/app.yaml)
- 🍪 Cookie 配置文件 (config/cookie.yaml)
- ⚙️ 可配置的采集参数
  - 天数限制
  - 最大视频数
  - 商品视频过滤

### 脚本

- 🔧 安装脚本 (scripts/install.bat)
  - 自动创建虚拟环境
  - 安装 Python 依赖
  - 处理 uv 缓存问题
- 🚀 运行脚本 (scripts/run.bat)
  - 检查虚拟环境
  - 运行主程序

### 文档

- 📚 README.md - 项目说明
- 📚 API 接口文档 - file-system-go API 规范
- 📚 数据字典 - 数据模型定义
- 📚 技术规范文档
- 📚 架构重构方案

### 技术栈

- Python 3.11+
- Playwright - 浏览器自动化
- httpx - HTTP 客户端
- Loguru - 日志管理
- PyYAML - 配置解析

---

## 版本说明

### 版本号规则

- **主版本号**：重大架构变更
- **次版本号**：功能新增
- **修订号**：Bug 修复和小改进

### 变更类型图标

- ✨ 新增功能
- 🐛 Bug 修复
- 🔄 功能优化
- 📝 文档更新
- 🔧 配置变更
- 🚀 性能改进
- 🔒 安全修复
- 🗑️ 删除功能
