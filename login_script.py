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

# ---------------- 环境检测函数 ----------------
def detect_environment():
    """检测当前运行环境"""
    # 优先检测是否在 Docker 环境中
    if os.environ.get("IN_DOCKER") == "true":
        return "docker"

    # 检测是否在青龙环境中
    ql_path_markers = ['/ql/data/', '/ql/config/', '/ql/', '/.ql/']
    in_ql_env = False

    for path in ql_path_markers:
        if os.path.exists(path):
            in_ql_env = True
            break

    # 检测是否在GitHub Actions环境中
    in_github_env = os.environ.get("GITHUB_ACTIONS") == "true" or (os.environ.get("GH_PAT") and os.environ.get("GITHUB_REPOSITORY"))

    if in_ql_env:
        return "qinglong"
    elif in_github_env:
        return "github"
    else:
        return "unknown"


# ---------------- GitHub 变量写入函数 ----------------
def save_cookie_to_github_var(var_name: str, value: str):
    import requests as py_requests
    token = os.environ.get("GH_PAT")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print("GH_PAT 或 GITHUB_REPOSITORY 未设置，跳过GitHub变量更新")
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    url_check = f"https://api.github.com/repos/{repo}/actions/variables/{var_name}"
    url_create = f"https://api.github.com/repos/{repo}/actions/variables"

    data = {"name": var_name, "value": value}

    try:
        response = py_requests.patch(url_check, headers=headers, json=data)
        if response.status_code == 204:
            print(f"GitHub: {var_name} 更新成功")
            return True
        elif response.status_code == 404:
            print(f"GitHub: {var_name} 不存在，尝试创建...")
            response = py_requests.post(url_create, headers=headers, json=data)
            if response.status_code == 201:
                print(f"GitHub: {var_name} 创建成功")
                return True
            else:
                print(f"GitHub创建失败: {response.status_code}, {response.text}")
                return False
        else:
            print(f"GitHub设置失败: {response.status_code}, {response.text}")
            return False
    except Exception as e:
        print(f"GitHub变量更新异常: {e}")
        return False


# ---------------- 青龙面板 API 交互类 ----------------
class QLAPI:
    @staticmethod
    def get_token():
        # 青龙脚本内部可以直接通过 /ql/config/auth.json 或环境变量获取，
        # 但如果是脚本内部运行，通常可以直接调用 notify.py 或使用已经注入的 API。
        # 这里为了简化，假设使用的是环境变量中已有的权限，或者通过特定的 QL API 库。
        # 实际上在青龙容器内运行脚本时，通常难以直接通过 python 代码修改环境变量并持久化，
        # 除非调用青龙暴露的 HTTP API。
        pass

    @staticmethod
    def _get_ql_config():
        auth_path = '/ql/config/auth.json'
        if os.path.exists(auth_path):
            with open(auth_path, 'r') as f:
                return json.load(f)
        return None

    @staticmethod
    def _get_ql_api_call(method, endpoint, data=None, params=None):
        # 尝试从环境变量获取青龙 API 信息
        # 青龙通常不直接暴露本地 API 给脚本，除非配置了 Client ID/Secret
        client_id = os.environ.get("QL_CLIENT_ID")
        client_secret = os.environ.get("QL_CLIENT_SECRET")
        base_url = os.environ.get("QL_API_URL", "http://localhost:5700")

        if not client_id or not client_secret:
            return {"code": 401, "message": "未配置 QL_CLIENT_ID 或 QL_CLIENT_SECRET"}

        import requests as py_requests
        # 1. 获取 token
        token_url = f"{base_url}/open/auth/token?client_id={client_id}&client_secret={client_secret}"
        try:
            token_resp = py_requests.get(token_url).json()
            if token_resp.get("code") != 200:
                return token_resp
            token = token_resp["data"]["token"]
        except Exception as e:
            return {"code": 500, "message": f"获取 QL Token 失败: {e}"}

        # 2. 调用 API
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = f"{base_url}/open/{endpoint}"
        try:
            if method.upper() == "GET":
                resp = py_requests.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                resp = py_requests.post(url, headers=headers, json=data)
            elif method.upper() == "PUT":
                resp = py_requests.put(url, headers=headers, json=data)
            elif method.upper() == "DELETE":
                resp = py_requests.delete(url, headers=headers, json=data)
            elif method.upper() == "PATCH":
                resp = py_requests.patch(url, headers=headers, json=data)
            else:
                return {"code": 405, "message": "不支持的方法"}
            return resp.json()
        except Exception as e:
            return {"code": 500, "message": f"调用 QL API 失败: {e}"}


def delete_ql_env(var_name: str):
    """删除青龙面板中的指定环境变量"""
    try:
        print(f"查询要删除的环境变量: {var_name}")
        env_result = QLAPI._get_ql_api_call("GET", "envs", params={"searchValue": var_name})

        env_ids = []
        if env_result.get("code") == 200 and env_result.get("data"):
            for env in env_result.get("data"):
                if env.get("name") == var_name:
                    env_ids.append(env.get("id"))

        if env_ids:
            print(f"找到 {len(env_ids)} 个环境变量需要删除: {env_ids}")
            delete_result = QLAPI._get_ql_api_call("DELETE", "envs", data=env_ids)
            if delete_result.get("code") == 200:
                print(f"成功删除环境变量: {var_name}")
                return True
            else:
                print(f"删除环境变量失败: {delete_result}")
                return False
        else:
            print(f"未找到环境变量: {var_name}")
            return True
    except Exception as e:
        print(f"删除环境变量异常: {str(e)}")
        return False


def save_env_to_ql(var_name: str, value: str):
    """保存环境变量到青龙面板"""
    try:
        delete_result = delete_ql_env(var_name)
        if not delete_result:
            print("删除已有变量失败，但仍将尝试创建新变量")

        create_data = [
            {
                "name": var_name,
                "value": value,
                "remarks": "56idc登录脚本自动创建"
            }
        ]

        create_result = QLAPI._get_ql_api_call("POST", "envs", data=create_data)
        if create_result.get("code") == 200:
            print(f"青龙面板环境变量 {var_name} 创建成功")
            return True
        else:
            print(f"青龙面板环境变量创建失败: {create_result}")
            return False
    except Exception as e:
        print(f"青龙面板环境变量操作异常: {str(e)}")
        return False


# ---------------- 统一变量保存函数 ----------------
def save_variable(var_name: str, value: str):
    """根据当前环境保存变量到相应位置"""
    env_type = detect_environment()

    if env_type == "qinglong":
        print("检测到青龙环境，尝试通过 API 更新环境变量...")
        return save_env_to_ql(var_name, value)
    elif env_type == "github":
        print("检测到GitHub环境，尝试保存变量到GitHub Actions Variables...")
        return save_cookie_to_github_var(var_name, value)
    else:
        print("未检测到支持远程保存的环境或配置不足，跳过变量自动保存")
        return False


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

    # 1. 尝试从 ACCOUNTS_JSON_56IDC 读取多账号 (GitHub Secrets 或 青龙)
    env_accounts_json = os.getenv('ACCOUNTS_JSON_56IDC')
    if env_accounts_json:
        try:
            json_accounts = json.loads(env_accounts_json)
            if isinstance(json_accounts, list):
                for acc in json_accounts:
                    if 'username' in acc and 'password' in acc:
                        accounts.append(acc)
                print(f"从环境变量 ACCOUNTS_JSON_56IDC 加载了 {len(json_accounts)} 个账号")
        except Exception as e:
            print(f'解析环境变量 ACCOUNTS_JSON_56IDC 出错: {e}')

    # 2. 尝试读取 IDC_USERNAME / IDC_PASSWORD (单账号)
    user = os.getenv("IDC_USERNAME")
    password = os.getenv("IDC_PASSWORD")
    if user and password:
        if not any(a['username'] == user for a in accounts):
            accounts.append({"username": user, "password": password})

    # 3. 尝试读取 IDC_USERNAME1, IDC_PASSWORD1, IDC_USERNAME2... (递增账号)
    index = 1
    while True:
        user = os.getenv(f"IDC_USERNAME{index}")
        password = os.getenv(f"IDC_PASSWORD{index}")
        if user and password:
            if not any(a['username'] == user for a in accounts):
                accounts.append({"username": user, "password": password})
            index += 1
        else:
            break

    # 4. 如果有 accounts.json，也合并进来
    if os.path.exists('accounts.json'):
        try:
            with open('accounts.json', 'r', encoding='utf-8') as f:
                json_accounts = json.load(f)
                if isinstance(json_accounts, list):
                    for acc in json_accounts:
                        if 'username' in acc and 'password' in acc:
                            if not any(a['username'] == acc['username'] for a in accounts):
                                accounts.append(acc)
        except Exception as e:
            print(f'读取 accounts.json 文件时出错: {e}')

    if not accounts:
        print("未发现账号信息，请在环境变量 (IDC_USERNAME/PASSWORD, IDC_USERNAME1/PASSWORD1, ACCOUNTS_JSON_56IDC) 或 accounts.json 中配置")
        return

    print(f"当前运行环境: {detect_environment()}")
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
