import os
import shutil
import sys
import time

from constants import *


def _bundled_cli_proxy_path():
    candidates = []
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        candidates.append(os.path.join(base, "cli-proxy-api.exe"))
        candidates.append(os.path.join(base, "assets", "cli-proxy-api.exe"))
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates.append(os.path.join(here, "assets", "cli-proxy-api.exe"))
    candidates.append(os.path.join(INSTALL_DIR, "cli-proxy-api.exe"))
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def ensure_cli_proxy_runtime():
    os.makedirs(INSTALL_DIR, exist_ok=True)
    os.makedirs(AUTH_DIR, exist_ok=True)
    bundled = _bundled_cli_proxy_path()
    if not bundled:
        return False, "未找到内置 cli-proxy-api.exe。"
    if os.path.abspath(bundled).lower() != os.path.abspath(EXE_PATH).lower():
        should_copy = not os.path.exists(EXE_PATH)
        if not should_copy:
            try:
                should_copy = os.path.getsize(EXE_PATH) != os.path.getsize(bundled)
            except OSError:
                should_copy = True
        if should_copy:
            try:
                shutil.copy2(bundled, EXE_PATH)
            except PermissionError:
                if os.path.exists(EXE_PATH):
                    return True, "现有 CLIProxyAPI 正在运行，已沿用当前运行时。"
                return False, "CLIProxyAPI 正在被占用，且本地运行时不存在。"
    return os.path.exists(EXE_PATH), EXE_PATH


def update_cli_proxy_runtime_if_possible():
    bundled = _bundled_cli_proxy_path()
    if not bundled:
        return False, "未找到内置 cli-proxy-api.exe。"
    os.makedirs(INSTALL_DIR, exist_ok=True)
    if os.path.abspath(bundled).lower() == os.path.abspath(EXE_PATH).lower():
        return True, "已使用本地运行时。"
    tmp = EXE_PATH + ".new"
    try:
        shutil.copy2(bundled, tmp)
        for _ in range(10):
            try:
                os.replace(tmp, EXE_PATH)
                return True, "CLIProxyAPI 运行时已更新。"
            except PermissionError:
                time.sleep(0.3)
        return False, "CLIProxyAPI 仍被占用，暂未更新运行时。"
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


def ensure_all():
    ok, msg = ensure_cli_proxy_runtime()
    if not ok:
        return False, msg
    from config_manager import ensure_base_files, ensure_builtin_model
    ensure_base_files()
    ensure_builtin_model()
    return True, "运行时已就绪。"
