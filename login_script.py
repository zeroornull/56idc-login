import json
import asyncio
import os

os.environ["PYPPETEER_CHROMIUM_REVISION"] = "1181217"
from pyppeteer import launch
from pyppeteer.errors import TimeoutError
from datetime import datetime, timedelta, timezone
import aiofiles
import random
import requests

import base64
from io import BytesIO
import ddddocr
from PIL import Image

# 从环境变量中获取 Telegram Bot Token 和 Chat ID
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


# 初始化 OCR 实例
ocr = ddddocr.DdddOcr()


def format_to_iso(date):
    """格式化日期为 ISO 格式"""
    return date.strftime('%Y-%m-%d %H:%M:%S')


async def delay_time(ms):
    """延迟函数"""
    await asyncio.sleep(ms / 1000)


async def login_with_retry(page, username, password, max_retries=3):
    """执行登录操作，包含重试逻辑"""
    serviceName = '56idc'
    retry_count = 0

    while retry_count < max_retries:
        try:
            url = 'https://56idc.net/login'
            await page.goto(url)

            # 等待输入框和按钮加载完成
            await page.waitForSelector('#inputEmail', timeout=10000)
            await page.waitForSelector('#inputPassword', timeout=10000)
            await page.waitForSelector('#inputCaptcha', timeout=10000)
            await page.waitForSelector('#login', timeout=10000)

            # 输入用户名和密码
            await page.type('#inputEmail', username)
            await page.type('#inputPassword', password)

            # 验证码处理逻辑
            captcha_selector = '#inputCaptchaImage'
            captcha_element = await page.querySelector(captcha_selector)

            if captcha_element:
                # 提取验证码图片 Base64 数据
                captcha_base64 = await page.evaluate(
                    """(element) => {
                        const canvas = document.createElement('canvas');
                        const ctx = canvas.getContext('2d');
                        canvas.width = element.naturalWidth;
                        canvas.height = element.naturalHeight;
                        ctx.drawImage(element, 0, 0);
                        return canvas.toDataURL('image/png').split(',')[1];
                    }""",
                    captcha_element
                )

                # 解码 Base64 数据为图片
                captcha_data = BytesIO(base64.b64decode(captcha_base64))
                img = Image.open(captcha_data)

                # 使用全局 OCR 实例识别验证码
                captcha_result = ocr.classification(img, png_fix=True)
                print(f"第 {retry_count + 1} 次尝试，识别出的验证码是: {captcha_result.strip()}")

                # 输入验证码
                await page.type('#inputCaptcha', captcha_result.strip())
            else:
                raise Exception("验证码图片未找到")

            # 点击登录按钮
            login_button = await page.querySelector('#login')
            if login_button:
                await login_button.click()
            else:
                raise Exception('无法找到登录按钮')

            # 等待导航或检查登录成功
            await page.waitForNavigation(timeout=15000)

            # 检查登录状态
            is_logged_in = await page.evaluate('''() => {
                const logoutButton = document.getElementById('Secondary_Navbar-Account-Logout');
                return logoutButton !== null;
            }''')

            # 如果登录成功，访问注销 URL
            if is_logged_in:
                await page.goto('https://56idc.net/logout.php')
                return True

        except TimeoutError as e:
            print(f'{serviceName}账号 {username} 第 {retry_count + 1} 次登录尝试超时: {e}')
        except Exception as e:
            print(f'{serviceName}账号 {username} 第 {retry_count + 1} 次登录尝试出错: {e}')

        retry_count += 1
        if retry_count < max_retries:
            delay = random.randint(2000, 5000)
            print(f"等待 {delay / 1000} 秒后进行第 {retry_count + 1} 次重试...")
            await delay_time(delay)

    return False


async def main():
    global message
    message = '56idc 自动化脚本运行\n'

    # 创建浏览器实例
    browser = await launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])

    try:
        # 读取账号信息
        async with aiofiles.open('accounts.json', mode='r', encoding='utf-8') as f:
            accounts_json = await f.read()
        accounts = json.loads(accounts_json)
    except json.JSONDecodeError as e:
        print(f'读取 accounts.json 文件时出错: {e}')
        await browser.close()
        return

    # 登录所有账号
    for account in accounts:
        page = await browser.newPage()
        username = account['username']
        password = account['password']

        is_logged_in = await login_with_retry(page, username, password)

        # 打码用户名
        masked_username = username[:3] + "***"

        if is_logged_in:
            # 获取带时区的当前时间
            now_utc = format_to_iso(datetime.now(timezone.utc))
            now_beijing = format_to_iso(datetime.now().astimezone(timezone(timedelta(hours=8))))
            success_message = f'56idc账号 {masked_username} 于北京时间 {now_beijing}（UTC时间 {now_utc}）登录成功！'
            message += success_message + '\n'
            print(success_message)
        else:
            message += f'56idc账号 {masked_username} 登录失败，已重试3次，请检查账号和密码是否正确。\n'
            print(f'56idc账号 {masked_username} 登录失败，已重试3次，请检查账号和密码是否正确。')

        delay = random.randint(1000, 8000)
        await delay_time(delay)
        await page.close()

    message += '所有56idc账号登录完成！'
    await send_telegram_message(message)
    print('所有56idc账号登录完成！')

    # 确保正确关闭浏览器
    await browser.close()


async def send_telegram_message(message):
    """发送消息到 Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message
    }
    headers = {
        'Content-Type': 'application/json'
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            print(f"发送消息到Telegram失败: {response.text}")
    except Exception as e:
        print(f"发送消息到Telegram时出错: {e}")


if __name__ == '__main__':
    asyncio.run(main())