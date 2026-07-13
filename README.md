# ModelDock

ModelDock（模型停靠站）是一个 Windows 单文件桌面工具，用来把 Codex Desktop、ChatGPT 订阅模型和第三方 API 模型放到同一个模型下拉列表里统一使用。

它内置并托管 [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI)，用户不需要单独下载网关程序。第一次启动时，软件会自动初始化本地网关、配置目录、模型目录和内置免费模型。

## 功能

- 一体化运行时：EXE 内包含 CLIProxyAPI，首次启动自动释放到 `%LOCALAPPDATA%\CLIProxyAPI`。
- 现代桌面 UI：基于 PySide6/Qt 重写，带窗口图标、应用 logo、托盘常驻。
- 接管保护：发现已有非本软件托管的 CLIProxyAPI 正在运行时，必须选择接管并继承配置，或退出软件。
- Codex 控制：首页检测 Codex Desktop 是否运行，并提供打开、停止、重启按钮。
- 网关控制：首页查看本地网关状态、PID、地址和当前可用模型。
- 配置管理：可视化添加、修改、删除第三方模型，支持 OpenAI / Responses / Claude 三类接口。
- 自动拉取模型：OpenAI 兼容接口可通过 `/models` 获取模型列表后选择。
- 内置免费模型：默认包含 `GLM-4.7-Flash 免费内置`，固定显示为 0 号，该配置受保护，用户不可编辑或删除。
- 回退点：支持自动回退点和手动命名回退点，可恢复网关、Codex provider、模型目录和登录相关配置。
- 登录状态：显示 Codex 安装/登录/官方账号套餐/第三方网关模式，本地读不到用量时会明确提示。
- 登录与跳过登录：可以启动 Codex 官方登录，也可以一键修复为仅 API 模式。
- 开机自启：通过 Windows 计划任务隐藏后台启动，不弹 PowerShell 窗口。
- 一键修复：自动修复 `~/.codex/config.toml`，让 Codex 使用本地网关 provider。
- 检查更新：通过 GitHub Releases 检测最新版。

## 下载

前往 [Releases](https://github.com/zhaoxinyi02/modeldock/releases) 下载最新版：

`ModelDock_VYYYY.MM.DD.exe`

如果同一天发布多个版本，会使用 `VYYYY.MM.DDa`、`VYYYY.MM.DDb` 这样的后缀。

## 使用

1. 安装或下载 Codex Desktop。
2. 打开 `ModelDock.exe`。
3. 在首页启动本地网关，必要时点击“打开 Codex”。
4. 在设置页选择一种模式：
   - “官方登录”：使用 CLIProxyAPI 启动 Codex 官方 OAuth 登录。
   - “修复为订阅+第三方”：保留 Codex 登录状态，同时让模型列表走本地网关。
   - “仅 API/跳过登录”：不依赖 ChatGPT 登录，只使用 API 模型。
5. 在配置页添加自己的第三方模型。

## 数据位置

- 网关程序和配置：`%LOCALAPPDATA%\CLIProxyAPI`
- 网关配置：`%LOCALAPPDATA%\CLIProxyAPI\config.yaml`
- Codex 配置：`%USERPROFILE%\.codex\config.toml`
- Codex 模型目录：`%USERPROFILE%\.codex\custom-model-catalog.json`

软件会尽量保留已有配置，不覆盖、删除或重排原有模型。修复 Codex 配置前会生成带时间戳的备份文件。

## 构建

本项目使用 Python、PySide6/Qt 和 PyInstaller。

```powershell
pip install -r requirements.txt
pyinstaller build.spec --noconfirm
```

正式发布由 GitHub Actions 完成。Actions 会下载 CLIProxyAPI Windows amd64 发布包，并通过仓库 Secret `BUILTIN_GLM_API_KEY` 注入内置免费模型 key。

## 安全说明

内置免费模型 key 会被打进发布版 EXE。它不会出现在公开源码中，但任何内置在客户端的软件密钥都可能被逆向提取。适合低成本体验入口，不适合承载无限制高价值额度。

## 开源依赖

- [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI)
- [PyYAML](https://pyyaml.org/)
- [PyInstaller](https://pyinstaller.org/)
