APP_NAME = "ModelDock"
APP_VERSION = "V2026.07.13d"
GITHUB_OWNER = "zhaoxinyi02"
GITHUB_REPO = "modeldock"

import os, tempfile
LOCAL_APPDATA = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
INSTALL_DIR = os.path.join(LOCAL_APPDATA, "CLIProxyAPI")
EXE_PATH = os.path.join(INSTALL_DIR, "cli-proxy-api.exe")
CONFIG_PATH = os.path.join(INSTALL_DIR, "config.yaml")
VBS_PATH = os.path.join(INSTALL_DIR, "start-hidden.vbs")
AUTH_DIR = os.path.join(INSTALL_DIR, "auth")
APP_RUNTIME_DIR = os.path.join(LOCAL_APPDATA, "CodexGatewayManager")
MANAGED_STATE_PATH = os.path.join(APP_RUNTIME_DIR, "managed-state.json")
RESTORE_ROOT = os.path.join(APP_RUNTIME_DIR, "restore-points")

CODEX_HOME = os.path.join(os.path.expanduser("~"), ".codex")
CODEX_CONFIG = os.path.join(CODEX_HOME, "config.toml")
CATALOG_PATH = os.path.join(CODEX_HOME, "custom-model-catalog.json")

GATEWAY_KEY = "codex-local-cliproxy"
GATEWAY_DEFAULT_PORT = 8317
GATEWAY_DEFAULT_HOST = "127.0.0.1"

BUILTIN_PROVIDER_ID = "zhipu_glm_free_builtin"
BUILTIN_PROVIDER_NAME = "智谱 GLM 免费内置"
BUILTIN_MODEL_ID = "glm-4.7-flash"
BUILTIN_ALIAS = "glm-4.7-flash-free"
BUILTIN_DISPLAY_NAME = "GLM-4.7-Flash 免费内置"
BUILTIN_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
BUILTIN_CONTEXT_WINDOW = 200000
BUILTIN_MAX_OUTPUT_TOKENS = 128000
BUILTIN_KEY_ENV = "BUILTIN_GLM_API_KEY"

AUTOSTART_TASK_NAME = "ModelDock"
# These are removed automatically when users enable/disable autostart after
# upgrading, so the product rename never leaves duplicate background tasks.
LEGACY_AUTOSTART_TASK_NAMES = ("Codex Gateway Manager", "CLIProxyAPI for Codex")
