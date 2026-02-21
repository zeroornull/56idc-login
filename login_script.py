# -*- coding: utf-8 -*-

import json
import os
import random
import time
from datetime import datetime, timedelta, timezone

from curl_cffi import requests

from yescaptcha import YesCaptchaSolver

try:
    from turnstile_solver import TurnstileSolver, TurnstileSolverError
except ImportError:
    # 兼容旧版本或独立运行环境
    class TurnstileSolverError(Exception):
        pass


    class TurnstileSolver:
        def __init__(self, *args, **kwargs): pass

        def solve(self, *args, **kwargs): return None
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 从环境变量中获取 Telegram Bot Token 和 Chat ID
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# 56idc Turnstile 配置
SITE_KEY = "0x4AAAAAACCEZfX2OxZ4g1Ac"
SITE_URL = "https://56idc.net/login"

# ---------------- 通知模块动态加载 (支持青龙 notify.py) ----------------
hadsend = False
send = None
try:
    from notify import send
    hadsend = True
    print("成功加载通知模块 (notify.py)")
except ImportError:
    print("未加载本地通知模块 (notify.py)，将使用内置的 Telegram 通知")

def _get_env_str(name: str, default: str = "") -> str:
    """读取环境变量并去掉空白；若为空字符串则回退 default。"""
    v = os.getenv(name)
    if v is None:
        return default
    v = str(v).strip()
    return v if v else default


def format_to_iso(date):
    """格式化日期为 ISO 格式"""
    return date.strftime('%Y-%m-%d %H:%M:%S')


def solve_turnstile():
    solver_type = _get_env_str("SOLVER_TYPE", "turnstile")
    api_base_url = _get_env_str("API_BASE_URL", "")
    client_key = _get_env_str("CLIENT_KEY", "")

    if not client_key:
        print("未配置 CLIENT_KEY，无法解决验证码")
        return None

    try:
        if solver_type.lower() == "yescaptcha":
            print("正在使用 YesCaptcha 解决验证码...")
            solver = YesCaptchaSolver(
                api_base_url=api_base_url or "https://api.yescaptcha.com",
                client_key=client_key
            )
        else:
            print("正在使用 TurnstileSolver 解决验证码...")
            solver = TurnstileSolver(
                api_base_url=api_base_url,
                client_key=client_key
            )

        token = solver.solve(
            url=SITE_URL,
            sitekey=SITE_KEY,
            verbose=True
        )
        return token
    except Exception as e:
        print(f"解决验证码出错: {e}")
        return None


def login_with_retry(username, password, max_retries=3):
    """执行登录操作，包含重试逻辑"""
    serviceName = '56idc'
    retry_count = 0

    while retry_count < max_retries:
        try:
            print(f"账号 {username} 第 {retry_count + 1} 次尝试登录...")

            token = solve_turnstile()
            if not token:
                print("验证码解析失败，跳过本次尝试")
                retry_count += 1
                continue

            session = requests.Session(impersonate="chrome110")

            # 访问登录页获取初始 cookies 和 CSRF token
            resp = session.get(SITE_URL)

            # 尝试提取隐藏的 CSRF token
            from re import search
            csrf_match = search(r'input type="hidden" name="token" value="([^"]+)"', resp.text)
            csrf_token = csrf_match.group(1) if csrf_match else ""

            if not csrf_token:
                # 尝试另一种匹配方式
                csrf_match = search(r'name="token" value="([^"]+)"', resp.text)
                csrf_token = csrf_match.group(1) if csrf_match else ""

            # 等待一会，模拟真人行为
            time.sleep(random.uniform(1, 3))

            data = {
                "token": csrf_token,
                "username": username,
                "password": password,
                "cf-turnstile-response": token,
                "rememberme": "on"
            }

            headers = {
                'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                'origin': "https://56idc.net",
                'referer': SITE_URL,
                'accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                'content-type': "application/x-www-form-urlencoded"
            }

            # 56idc 的登录接口通常直接 POST 到登录页
            # 使用 allow_redirects=False 以便捕捉 302 跳转
            response = session.post(SITE_URL, data=data, headers=headers, allow_redirects=False)

            # 打印详细登录响应日志
            print(f"[{serviceName}] 登录响应状态码: {response.status_code}")
            if response.status_code == 302:
                print(f"[{serviceName}] 登录重定向地址: {response.headers.get('Location')}")

            # 检查是否登录成功
            # 56idc (WHMCS) 成功后通常会 302 跳转到 clientarea.php
            is_success = False
            location = response.headers.get("Location", "")
            if response.status_code == 302 and ("clientarea.php" in location or "index.php" in location):
                is_success = True
                print(f"[{serviceName}] 检测到成功重定向至: {location}")
            elif "Logout" in response.text or "注销" in response.text or "clientarea.php" in response.text:
                is_success = True
                print(f"[{serviceName}] 响应内容中检测到登录成功标识 (如 'Logout' 或 'clientarea.php')")

            if is_success:
                # 进一步验证登录状态
                print(f"[{serviceName}] 正在进一步验证登录状态...")
                verify_resp = session.get("https://56idc.net/clientarea.php")
                if "Logout" in verify_resp.text or "注销" in verify_resp.text:
                    print(f"[{serviceName}] [SUCCESS] 账号 {username} 成功进入会员中心！")
                    # 访问注销 URL (保持原脚本逻辑)
                    session.get('https://56idc.net/logout.php')
                    return True
                else:
                    print(f"[{serviceName}] [FAILED] 虽然检测到重定向，但进入会员中心失败，可能会话无效")
            else:
                # 如果没成功，可能重定向回 login.php?failed=true，检查一下
                error_msg = ""
                if "failed=true" in location:
                    error_msg = " (用户名或密码错误)"
                print(
                    f"[{serviceName}] [FAILED] 账号 {username} 登录失败{error_msg}，状态码: {response.status_code}, 响应预览: {response.text[:100].replace('\n', ' ')}")

        except Exception as e:
            print(f'{serviceName}账号 {username} 第 {retry_count + 1} 次登录尝试出错: {e}')

        retry_count += 1
        if retry_count < max_retries:
            delay = random.randint(5, 10)
            print(f"等待 {delay} 秒后重试...")
            time.sleep(delay)

    return False


def send_notification(message):
    """统一发送通知接口"""
    # 优先使用 notify.py (青龙自带)
    if hadsend:
        try:
            send("56idc 登录通知", message)
            print("已通过 notify.py 发送通知")
            return
        except Exception as e:
            print(f"通过 notify.py 发送通知失败: {e}")

    # 备选：使用内置的 Telegram 发送
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message
        }
        try:
            import requests as py_requests
            response = py_requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                print(f"发送消息到Telegram失败: {response.text}")
            else:
                print("已通过 Telegram 发送通知")
        except Exception as e:
            print(f"发送消息到Telegram时出错: {e}")
    else:
        print("未配置通知方式，仅打印到控制台")


def main():
    message = '56idc 自动化脚本运行 (Requests 版)\n'

    accounts = []
    # 1. 优先从环境变量 ACCOUNTS_JSON 读取多账号 (适合 GitHub Secrets 或青龙)
    env_accounts_json = os.getenv('ACCOUNTS_JSON_56IDC')
    if env_accounts_json:
        try:
            json_accounts = json.loads(env_accounts_json)
            if isinstance(json_accounts, list):
                for acc in json_accounts:
                    if 'username' in acc and 'password' in acc:
                        accounts.append(acc)
                print(f"从环境变量 ACCOUNTS_JSON 加载了 {len(json_accounts)} 个账号")
        except Exception as e:
            print(f'解析环境变量 ACCOUNTS_JSON 出错: {e}')

    # 2. 从环境变量读取单账号
    env_username = os.getenv('IDC_USERNAME')
    env_password = os.getenv('IDC_PASSWORD')

    if env_username and env_password:
        # 避免重复添加
        if not any(a['username'] == env_username for a in accounts):
            accounts.append({'username': env_username, 'password': env_password})

    # 3. 如果有 accounts.json，也合并进来
    if os.path.exists('accounts.json'):
        try:
            with open('accounts.json', 'r', encoding='utf-8') as f:
                json_accounts = json.load(f)
                for acc in json_accounts:
                    if not any(a['username'] == acc['username'] for a in accounts):
                        accounts.append(acc)
        except Exception as e:
            print(f'读取 accounts.json 文件时出错: {e}')

    if not accounts:
        print("未发现账号信息，请在 .env (IDC_USERNAME/PASSWORD 或 ACCOUNTS_JSON) 或 accounts.json 中配置")
        return

    print(f"共发现 {len(accounts)} 个账号，开始执行...")

    # 登录所有账号
    for account in accounts:
        username = account['username']
        password = account['password']

        is_logged_in = login_with_retry(username, password)

        masked_username = username[:3] + "***" if len(username) > 3 else username

        if is_logged_in:
            now_beijing = format_to_iso(datetime.now(timezone(timedelta(hours=8))))
            success_message = f'56idc账号 {masked_username} 于北京时间 {now_beijing} 登录成功！'
            message += success_message + '\n'
            print(success_message)
        else:
            fail_message = f'56idc账号 {masked_username} 登录失败，已重试3次。'
            message += fail_message + '\n'
            print(fail_message)

        time.sleep(random.randint(2, 5))

    message += '所有56idc账号处理完成！'
    send_notification(message)
    print('所有56idc账号处理完成！')


if __name__ == '__main__':
    main()
