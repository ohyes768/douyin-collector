# Cookie 反爬机制问题记录

## 问题描述

使用 Playwright 自动化工具访问抖音网站时，即使注入了有效的 Cookie，仍然会出现登录弹框，导致无法正常采集数据。

## 根本原因

抖音的反爬机制会检查多个特征来识别自动化工具：

### 1. User-Agent 不完整
错误示例：
```python
user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
```

正确示例：
```python
user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
```

### 2. 缺少反检测脚本
必须注入反检测脚本来隐藏 `navigator.webdriver` 属性：
```python
await context.add_init_script("""
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });
""")
```

### 3. 浏览器启动参数不完整
错误示例：
```python
browser = await playwright.chromium.launch(
    headless=True,
    args=['--disable-blink-features=AutomationControlled']
)
```

正确示例：
```python
browser = await playwright.chromium.launch(
    headless=True,
    args=[
        '--disable-blink-features=AutomationControlled',
        '--no-sandbox',
        '--disable-setuid-sandbox',
    ]
)
```

## 解决方案

完整的 Playwright 配置必须包含以下三个要素：

```python
async def __aenter__(self):
    """Async context enter"""
    self._playwright = await async_playwright().start()

    # 1. 浏览器启动参数（完整）
    self._browser = await self._playwright.chromium.launch(
        headless=True,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-setuid-sandbox',
        ]
    )

    # 2. Context 配置（完整 User-Agent）
    self._context = await self._browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        locale='zh-CN',
        timezone_id='Asia/Shanghai',
    )

    # 3. 反检测脚本（必需！）
    await self._context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)

    # 注入 Cookie
    # ...
```

## 验证方法

创建测试脚本验证 Cookie 注入是否有效：

```python
#!/usr/bin/env python3
import asyncio
from playwright.async_api import async_playwright

async def test_cookie():
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=True,
        args=['--disable-blink-features=AutomationControlled']
    )
    context = await browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    )
    # 注入 Cookie
    await context.add_cookies(cookies)
    page = await context.new_page()
    await page.goto("https://www.douyin.com/user/self?showTab=favorite_collection")
    await asyncio.sleep(3)

    # 检查是否有登录弹框
    login_popup = await page.query_selector('#login-panel-new')
    if login_popup:
        print("[FAIL] Cookie 失效")
    else:
        print("[SUCCESS] Cookie 有效")

    await browser.close()
    await playwright.stop()

asyncio.run(test_cookie())
```

## 相关文件

- `src/playwright_adapter.py` - Playwright 适配器，包含 User-Agent 配置
- `src/cookie_manager.py` - Cookie 管理器，负责加载和解析 Cookie
- `config/cookie.yaml` - Cookie 配置文件

## 历史记录

| 日期 | 问题 | 解决方案 |
|------|------|----------|
| 2026-03-06 | User-Agent 不完整导致登录弹框 | 补充完整的浏览器标识信息 |
| 2026-03-06 | 多个测试文件仍使用不完整 User-Agent | 批量修复所有相关文件的 User-Agent |
| 2026-03-06 | 缺少反检测脚本导致测试文件仍有登录弹框 | 添加 `navigator.webdriver` 隐藏脚本 |

## 修复的文件

以下文件已修复 User-Agent 配置并添加反检测脚本：

- `src/playwright_adapter.py` - 主适配器（包含完整配置）
- `src/cookie_manager.py` - Cookie 验证方法
- `test_click_collect_button.py` - 点击收藏按钮测试
- `test_find_collect_button.py` - 查找收藏按钮测试
- `test_headless_off.py` - 可见浏览器测试
- `test_verify_collection.py` - 收藏切换验证测试
- `test_real_collection.py` - 真实收藏测试

## Playwright 抖音反爬完整配置模板

今后新增的 Playwright 脚本必须使用以下完整配置：

```python
import asyncio
from playwright.async_api import async_playwright

async def douyin_request():
    """抖音请求完整配置模板"""
    playwright = await async_playwright().start()

    # 1. 浏览器启动（完整参数）
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-setuid-sandbox',
        ]
    )

    # 2. Context 配置（完整 User-Agent）
    context = await browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        locale='zh-CN',
        timezone_id='Asia/Shanghai',
    )

    # 3. 反检测脚本（必需！）
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)

    # 4. 注入 Cookie
    await context.add_cookies(cookies)

    # 5. 创建页面并请求
    page = await context.new_page()
    await page.goto("https://www.douyin.com/...")

    await browser.close()
    await playwright.stop()
```