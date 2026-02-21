# 56idc.net 保活

## 不建议github action方式，请自行Qinglong或者其他方式

### 快速开始 (本地运行)

#### 1. 安装依赖
确保已安装 [uv](https://github.com/astral-sh/uv)，然后在项目目录下运行：
```bash
uv sync
```
*注：本项目使用了自定义的 `turnstile_solver.py` 来处理 CloudFreed API。*

#### 2. 配置环境变量
复制 `.env.example` 为 `.env` 并填写你的配置：
```bash
cp .env.example .env
```
在 `.env` 文件中：
- `IDC_USERNAME`: 56idc 账号 (邮箱)
- `IDC_PASSWORD`: 56idc 密码
- `SOLVER_TYPE`: 验证码解决服务类型 (`turnstile` 或 `yescaptcha`)
- `API_BASE_URL`: 服务 API 地址 (如 `https://api.capsolver.com` 或 `https://api.yescaptcha.com`)
- `CLIENT_KEY`: 你的 API Key
- `TG_BOT_TOKEN`: (可选) Telegram Bot Token
- `TG_USER_ID`: (可选) Telegram Chat ID
- `PUSH_PLUS_TOKEN`: (可选) push+ 微信推送令牌
- `DD_BOT_TOKEN`, `DD_BOT_SECRET`: (可选) 钉钉机器人推送
- `FSKEY`: (可选) 飞书机器人推送
- `BARK_PUSH`: (可选) Bark 推送
- (其他支持的通知方式请查看 `notify.py`)

### YesCaptcha 商业服务

1. 访问 [YesCaptcha](https://yescaptcha.com/i/Kuc27w) 注册账号
2. 注册后联系客服可免费获得余额（约可使用60次登录）
3. 配置以下环境变量：

| 变量名称 | 说明 |
| :------: | :--- |
| `CLIENT_KEY` | YesCaptcha 的 API 密钥 |
| `IDC_USERNAME` | 56idc 论坛用户名 (或 `USER1`/`USER2`...) |
| `IDC_PASSWORD` | 56idc 论坛密码 (或 `PASS1`/`PASS2`...) |
| `SOLVER_TYPE` | 设置为 `yescaptcha` |

> **提示**：YesCaptcha 提供两个服务节点，可根据网络情况选择：
> - 国际节点：`https://api.yescaptcha.com`（默认）
> - 国内节点：`https://cn.yescaptcha.com`

### CloudFreed (Docker) 配置方式

CloudFreed 提供了一种通过 Docker 部署的 Turnstile 解决服务。你可以按照以下步骤进行配置：

#### 1. Docker 启动
如果你有自己的服务器，可以使用 Docker 运行：
```bash
docker run -it --rm -p 3000:3000 jackzzs/cloudflyer -K YOUR_CLIENT_KEY
```
*注：具体镜像名和参数请参考 https://github.com/cloudflyer-project/cloudflyer-oss 官方文档。*

#### 2. 配置 Key
启动后，在本项目中配置：
- `SOLVER_TYPE`: `turnstile`
- `API_BASE_URL`: `http://你的服务器IP:3000`
- `CLIENT_KEY`: 你在 Docker 启动时设置的 `API_KEY`

#### 3. 运行脚本
```bash
uv run login_script.py
```

### 青龙 (Linux) 环境配置

现在脚本使用 `curl_cffi` 和 Turnstile 解决服务，极大简化了在青龙等 Linux 环境下的部署。

#### 1. 订阅脚本
在青龙面板的“订阅管理”中新建订阅：
- **名称**: 56idc 登录
- **类型**: 公开仓库
- **链接**: `你的仓库地址`
- **定时**: `0 0 * * *` (每天运行一次)
- **白名单**: `login_script.py`
- **依赖文件**: `requirements.txt`

#### 2. 配置依赖
脚本运行需要 `curl_cffi` 等依赖。青龙会自动识别 `requirements.txt` 并尝试安装，如果安装失败，请手动在“依赖管理” -> “Python3”中添加：
- `curl_cffi`
- `yescaptcha`
- `python-dotenv`

#### 3. 配置环境变量
在青龙面板的“环境变量”中添加：
- `IDC_USERNAME`: 56idc 账号 (邮箱)
- `IDC_PASSWORD`: 56idc 密码
- `IDC_USERNAME1`, `IDC_PASSWORD1`: (可选) 递增账号配置，支持 `IDC_USERNAME2`, `IDC_PASSWORD2` 等以此类推
- `ACCOUNTS_JSON_56IDC`: (可选) 多账号 JSON 配置，例如 `[{"username": "acc1", "password": "pwd1"}, {"username": "acc2", "password": "pwd2"}]`。注意：在某些环境中，如果作为字符串输入，请确保其为有效的 JSON 格式。脚本已增加对包裹引号的自动处理。
- `CLIENT_KEY`: 验证码解决服务的 API Key
- `SOLVER_TYPE`: (可选) 默认为 `turnstile`
- `API_BASE_URL`: (可选) 对应服务的 API 地址
- `TG_BOT_TOKEN`: (可选) Telegram 通知
- `TG_USER_ID`: (可选) Telegram 通知
- `PUSH_PLUS_TOKEN`: (可选) push+ 微信推送令牌
- `DD_BOT_TOKEN`, `DD_BOT_SECRET`: (可选) 钉钉机器人推送
- `FSKEY`: (可选) 飞书机器人推送
- `BARK_PUSH`: (可选) Bark 推送
- (其他支持的通知方式请查看 `notify.py`)

**进阶配置 (自动保存变量):**
如果需要在脚本中自动更新/保存环境变量 (目前主要用于支持环境检测和同步):
- 青龙环境: 配置 `QL_CLIENT_ID`, `QL_CLIENT_SECRET`, `QL_API_URL` (默认 http://localhost:5700)
- GitHub 环境: 配置 `GH_PAT` (Personal Access Token) 和 `GITHUB_REPOSITORY`

*注：脚本会自动识别青龙内置的 `notify.py` 模块。如果配置了青龙的全局通知，脚本执行结果会自动推送。*

#### 4. 运行脚本
订阅成功后，在“定时任务”中找到 `56idc 登录` 任务手动运行即可。
### 多账号支持
如果你有多个账号，可以在项目根目录创建 `accounts.json`：
```json
[
  {"username": "user1@example.com", "password": "password1"},
  {"username": "user2@example.com", "password": "password2"}
]
```
脚本会自动合并 `.env` 中的账号和 `accounts.json` 中的账号。

### 将代码fork到你的仓库并运行的操作步骤

#### 1. Fork 仓库

1. **访问原始仓库页面**：
    - 打开你想要 fork 的 GitHub 仓库页面。

2. **Fork 仓库**：
    - 点击页面右上角的 "Fork" 按钮，将仓库 fork 到你的 GitHub 账户下。

#### 2. 设置 GitHub Secrets

1. **创建 Telegram Bot**
    - 在 Telegram 中找到 `@BotFather`，创建一个新 Bot，并获取 API Token。
    - 获取到你的 Chat ID 方法一，发送`/id@KinhRoBot`获取，返回用户信息中的`ID`就是Chat ID
    - 获取到你的 Chat ID 方法二，可以通过向 Bot 发送一条消息，然后访问 `https://api.telegram.org/bot<your_bot_token>/getUpdates` 找到 Chat ID。

2. **配置 GitHub Secrets**
    - 转到你 fork 的仓库页面。
    - 点击 `Settings`，然后在左侧菜单中选择 `Secrets and variables` -> `Actions`。
    - 在 `Secrets` 选项卡下添加以下 Secrets：
        - `ACCOUNTS_JSON_56IDC`: 包含账号信息的 JSON 数据。例如：
        - 
          ```json
          [
            {"username": "acc1", "password": "pwd"},
            {"username": "acc2", "password": "pwd"}
          ]
          ```
        - `IDC_USERNAME`: (可选) 单账号用户名
        - `IDC_PASSWORD`: (可选) 单账号密码
        - `CLIENT_KEY`: 验证码服务的 API Key
        - `TG_BOT_TOKEN`: (可选) 你的 Telegram Bot 的 API Token。
        - `TG_USER_ID`: (可选) 你的 Telegram Chat ID。
        - `PUSH_PLUS_TOKEN`: (可选) Push+ 微信推送令牌
        - `DD_BOT_TOKEN`: (可选) 钉钉机器人 Token
        - `DD_BOT_SECRET`: (可选) 钉钉机器人 Secret
        - `FSKEY`: (可选) 飞书机器人 Key
        - `BARK_PUSH`: (可选) Bark 推送 (iOS)
        - `QYWX_KEY`: (可选) 企业微信机器人 Key
        - `DEER_KEY`: (可选) PushDeer Key
        - (更多通知变量请参考 `notify.py`)

    - **获取方法**：
        - 在 Telegram 中创建 Bot，并获取 API Token 和 Chat ID。
        - 在 GitHub 仓库的 Secrets 页面添加这些值，确保它们安全且不被泄露。

#### 3. 启动 GitHub Actions

1. **配置 GitHub Actions**
    - 在你的 fork 仓库中，进入 `Actions` 页面。
    - 如果 Actions 没有自动启用，点击 `Enable GitHub Actions` 按钮以激活它。

2. **运行工作流**
    - GitHub Actions 将会根据你设置的定时任务（例如每三天一次）自动运行脚本。
    - 如果需要手动触发，可以在 Actions 页面手动运行工作流。

#### 示例 Secrets 和获取方法总结

- **TG_BOT_TOKEN**
    - 示例值: `1234567890:ABCDEFghijklmnopQRSTuvwxyZ`
    - 获取方法: 在 Telegram 中使用 `@BotFather` 创建 Bot 并获取 API Token单位。

- **TG_USER_ID**
    - 示例值: `1234567890`
    - 获取方法: 发送一条消息给你的 Bot，然后访问 `https://api.telegram.org/bot<your_bot_token>/getUpdates` 获取 Chat ID。

- **ACCOUNTS_JSON_56IDC**
    - 示例值:
      ```json
      [
            {"username": "56idc.net的账号", "password": "56idc.net的密码"},
            {"username": "56idc.net的账号2", "password": "56idc.net的密码2"}
          ]
      ```
    - 获取方法: 创建一个包含56idc.net账号信息的 JSON 文件，并将其内容添加到 GitHub 仓库的 Secrets 中。

### 注意事项

- **保密性**: Secrets 是敏感信息，请确保不要将它们泄露到公共代码库或未授权的人员。
- **更新和删除**: 如果需要更新或删除 Secrets，可以通过仓库的 Secrets 页面进行管理。

通过以上步骤，你就可以成功将代码 fork 到你的仓库下并运行它了。如果需要进一步的帮助或有其他问题，请随时告知！

## Stargazers over time
[![Stargazers over time](https://starchart.cc/zeroornull/56idc-login.svg?variant=adaptive)](https://starchart.cc/zeroornull/56idc-login)
