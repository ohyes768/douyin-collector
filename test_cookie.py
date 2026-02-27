#!/usr/bin/env python3
"""
Cookie 验证测试脚本
独立测试 Cookie 验证逻辑
"""

import httpx
import yaml
from pathlib import Path


def validate_cookie(cookie: str):
    """
    验证 Cookie 是否有效

    Args:
        cookie: Cookie 字符串

    Returns:
        (is_valid, message, response_data): 是否有效、提示信息、响应数据
    """
    # 1. 检查 Cookie 是否为空
    if not cookie:
        return False, "Cookie 为空", None

    # 2. 检查关键字段是否存在
    if "sessionid=" not in cookie:
        return False, "Cookie 缺少 sessionid 字段", None

    # 3. 发送 API 请求测试
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.douyin.com/",
            "Origin": "https://www.douyin.com",
            "Cookie": cookie
        }

        print(f"正在请求: https://www.douyin.com/aweme/v1/web/query/user/")

        response = httpx.get(
            "https://www.douyin.com/aweme/v1/web/query/user/",
            headers=headers,
            timeout=10
        )

        print(f"\n{'='*60}")
        print(f"HTTP 状态码: {response.status_code}")
        print(f"{'='*60}")

        if response.status_code == 200:
            try:
                data = response.json()
                print(f"\n响应 JSON 结构:")
                print(f"  Keys: {list(data.keys())}")

                # 打印关键字段的值
                if "status_code" in data:
                    print(f"  status_code: {data['status_code']}")
                if "status_msg" in data:
                    print(f"  status_msg: {data['status_msg']}")
                if "user_info" in data:
                    print(f"  user_info: 存在")
                if "data" in data:
                    print(f"  data: {type(data['data'])}")

                # 打印完整响应（格式化）
                print(f"\n完整响应 JSON:")
                import json
                print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
                print(f"...\n(截取前 2000 字符)")

                # 判断 Cookie 是否有效
                if data.get("status_code") == 0:
                    return True, "Cookie 有效 (status_code=0)", data
                if "user_info" in data:
                    return True, "Cookie 有效 (包含 user_info)", data
                if data.get("data") and isinstance(data.get("data"), dict):
                    return True, "Cookie 有效 (包含 data)", data

                return False, "响应不符合预期格式", data

            except Exception as e:
                print(f"\nJSON 解析失败: {e}")
                print(f"原始响应文本: {response.text[:500]}")
                return False, f"响应不是有效的 JSON: {e}", response.text

        return False, f"HTTP 错误: {response.status_code}", None

    except httpx.TimeoutException:
        return False, "请求超时", None
    except Exception as e:
        return False, f"请求失败: {e}", None


def main():
    """主函数"""
    print("="*60)
    print("抖音 Cookie 验证测试")
    print("="*60)

    # 加载 Cookie
    config_path = Path("config/cookie.yaml")
    if not config_path.exists():
        print(f"\n错误: 配置文件不存在: {config_path}")
        return

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        cookie = config.get("douyin", {}).get("cookie", "")

    if not cookie:
        print("\n错误: Cookie 配置为空")
        return

    print(f"\n已加载 Cookie (长度: {len(cookie)} 字符)")
    print(f"Cookie 前 100 字符: {cookie[:100]}...")

    # 检查关键字段
    print(f"\n关键字段检查:")
    print(f"  sessionid: {'✓ 存在' if 'sessionid=' in cookie else '✗ 不存在'}")
    print(f"  ttwid: {'✓ 存在' if 'ttwid=' in cookie else '✗ 不存在'}")
    print(f"  passport_csrf_token: {'✓ 存在' if 'passport_csrf_token=' in cookie else '✗ 不存在'}")

    # 验证 Cookie
    is_valid, message, data = validate_cookie(cookie)

    print(f"\n{'='*60}")
    print(f"验证结果: {'✓ 通过' if is_valid else '✗ 失败'}")
    print(f"提示信息: {message}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
