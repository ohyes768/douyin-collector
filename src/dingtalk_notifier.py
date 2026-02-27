"""
钉钉通知模块
"""

import httpx
from loguru import logger


class DingTalkNotifier:
    """钉钉通知器"""

    def __init__(self, webhook_url: str):
        """
        初始化钉钉通知器

        Args:
            webhook_url: 钉钉机器人 Webhook URL
        """
        self.webhook_url = webhook_url

    def send_cookie_alert(self, reason: str) -> bool:
        """
        发送 Cookie 失效告警

        Args:
            reason: 失效原因

        Returns:
            是否发送成功
        """
        message = f"""【注意】抖音采集器告警

Cookie 已失效！

**失效原因**: {reason}

**处理建议**:
1. 打开浏览器访问抖音并登录
2. 按 F12 打开开发者工具
3. 切换到 Network 标签
4. 刷新页面，复制 Request Headers 中的 Cookie
5. 更新到服务器的 config/cookie.yaml 文件

请及时处理，避免影响采集任务。"""

        data = {
            "msgtype": "text",
            "text": {
                "content": message
            }
        }

        try:
            response = httpx.post(self.webhook_url, json=data, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    logger.info("钉钉通知发送成功")
                    return True
                else:
                    logger.warning(f"钉钉通知返回错误: {result}")
            else:
                logger.warning(f"钉钉通知发送失败: HTTP {response.status_code}")
        except Exception as e:
            logger.warning(f"钉钉通知发送异常: {e}")

        return False
