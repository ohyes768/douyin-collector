# douyin-collector API 接口文档

## 概述

douyin-collector 依赖 file-system-go 提供的文件服务接口。本文档描述所需的 API 规范。

## 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| 1.0.0 | 2026-02-26 | 初始版本 |

---

## 1. 文件检查接口

### 1.1 检查文件是否存在

**接口描述**：检查服务器上是否已存在指定文件

**请求**

```http
GET /api/check/{filename}
```

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| filename | string | 是 | 文件名（如：7123456789012345678.mp4） |

**响应示例**

文件存在：
```json
{
  "exists": true,
  "filename": "7123456789012345678.mp4",
  "size": 102400000,
  "upload_time": "2026-02-26T12:00:00Z"
}
```

文件不存在：
```json
{
  "exists": false,
  "filename": "7123456789012345678.mp4"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| exists | boolean | 文件是否存在 |
| filename | string | 文件名 |
| size | number | 文件大小（字节），仅 exists=true 时返回 |
| upload_time | string | 上传时间（ISO 8601），仅 exists=true 时返回 |

**错误响应**

```json
{
  "error": "文件检查失败"
}
```

---

## 2. 文件上传接口

### 2.1 上传视频文件

**接口描述**：上传视频文件到服务器

**请求**

```http
POST /api/upload
Content-Type: multipart/form-data
```

**表单参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | 是 | 视频文件（MP4 格式） |

**成功响应**

```json
{
  "success": true,
  "filename": "7123456789012345678.mp4",
  "url": "/audio/7123456789012345678.mp4",
  "size": 102400000
}
```

**失败响应**

```json
{
  "success": false,
  "error": "错误描述"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 上传是否成功 |
| filename | string | 保存的文件名 |
| url | string | 文件访问 URL |
| size | number | 文件大小（字节） |
| error | string | 错误描述，仅 success=false 时返回 |

---

## 3. 实现要求

### 3.1 file-system-go 改造

当前 file-system-go 需要添加以下接口：

1. **GET /api/check/{filename}** - 文件检查接口
   - 返回文件存在信息
   - 支持增量处理

### 3.2 接口兼容性

| 接口 | file-system-go 状态 | douyin-collector 需求 |
|------|---------------------|---------------------|
| GET /api/check/{filename} | ❌ 需添加 | ✅ 必需 |
| POST /api/upload | ✅ 已有 | ✅ 使用现有 |

---

## 4. 调用流程

```
douyin-collector                    file-system-go
       |                                    |
       |  1. GET /api/check/{filename}       |
       |----------------------------------->|
       |                                    |
       |  2. 检查结果 (exists/size)         |
       |<-----------------------------------|
       |                                    |
       |  3. 如果不存在，上传文件            |
       |  4. POST /api/upload               |
       |----------------------------------->|
       |                                    |
       |  5. 上传结果 (success/url)          |
       |<-----------------------------------|
```

---

## 5. 注意事项

### 5.1 超时设置

- 检查接口超时：30 秒
- 上传接口超时：60 秒（可配置）

### 5.2 重试机制

- 失败自动重试 3 次
- 重试延迟：5 秒

### 5.3 文件命名

- 文件名格式：`{aweme_id}.mp4`
- 示例：`7123456789012345678.mp4`

### 5.4 文件大小限制

- 最大文件大小：100 MB
- 超过限制的文件会被跳过

---

## 6. 示例代码

### 6.1 检查文件存在

```python
import httpx

async def check_file(filename: str):
    url = f"{server_url}/api/check/{filename}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()
```

### 6.2 上传文件

```python
import httpx

async def upload_file(filepath: str):
    url = f"{server_url}/api/upload"
    with open(filepath, "rb") as f:
        files = {"file": (filename, f, "video/mp4")}
        async with httpx.AsyncClient() as client:
            response = await client.post(url, files=files)
            return response.json()
```

---

## 附录

### A. 相关文档

- [file-system-go 技术规范文档](../../../file-system-go/docs/技术规范文档.md)
- [douyin-collector 技术规范文档](../discuss/douyin-collector-技术规范.md)

### B. 变更记录

- 2026-02-26: 创建 API 接口文档
