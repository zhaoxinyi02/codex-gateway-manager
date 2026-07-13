import os, subprocess, time, json, urllib.request, urllib.error, datetime
from constants import *
import runtime

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

def is_running():
    try:
        r = subprocess.run(
            ["tasklist", "/fi", "imagename eq cli-proxy-api.exe", "/fo", "csv", "/nh"],
            capture_output=True, text=True, timeout=5, creationflags=NO_WINDOW)
        return "cli-proxy-api.exe" in r.stdout.lower()
    except Exception:
        return False

def get_pid():
    try:
        r = subprocess.run(
            ["tasklist", "/fi", "imagename eq cli-proxy-api.exe", "/fo", "csv", "/nh"],
            capture_output=True, text=True, timeout=5, creationflags=NO_WINDOW)
        for line in r.stdout.strip().splitlines():
            parts = [p.strip('"') for p in line.split('","')]
            if parts and parts[0].lower() == "cli-proxy-api.exe":
                return int(parts[1])
        return None
    except Exception:
        return None


def get_process_info():
    pid = get_pid()
    if not pid:
        return None
    try:
        ps = (
            "Get-CimInstance Win32_Process -Filter \"ProcessId=" + str(pid) + "\" | "
            "Select-Object ProcessId,ExecutablePath,CommandLine | ConvertTo-Json -Compress"
        )
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=8, creationflags=NO_WINDOW)
        if r.returncode != 0 or not r.stdout.strip():
            return {"pid": pid, "path": "", "command_line": ""}
        data = json.loads(r.stdout)
        return {
            "pid": pid,
            "path": data.get("ExecutablePath") or "",
            "command_line": data.get("CommandLine") or "",
        }
    except Exception:
        return {"pid": pid, "path": "", "command_line": ""}


def _write_managed_state(pid=None):
    os.makedirs(APP_RUNTIME_DIR, exist_ok=True)
    data = {
        "pid": pid or get_pid(),
        "exe_path": EXE_PATH,
        "config_path": CONFIG_PATH,
        "started_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "managed_by": APP_NAME,
        "version": APP_VERSION,
    }
    with open(MANAGED_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_managed_running():
    info = get_process_info()
    if not info:
        return False
    try:
        with open(MANAGED_STATE_PATH, encoding="utf-8") as f:
            state = json.load(f)
        if int(state.get("pid") or 0) != int(info.get("pid") or 0):
            return False
        return os.path.abspath(state.get("exe_path") or "").lower() == os.path.abspath(info.get("path") or EXE_PATH).lower()
    except Exception:
        return False


def running_config_path():
    info = get_process_info()
    if not info:
        return None
    cmd = info.get("command_line") or ""
    import shlex
    try:
        parts = shlex.split(cmd, posix=False)
    except Exception:
        parts = cmd.split()
    for i, part in enumerate(parts):
        if part.strip('"').lower() == "-config" and i + 1 < len(parts):
            return parts[i + 1].strip('"')
    return CONFIG_PATH

def get_gateway_url():
    import yaml
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        host = cfg.get("host") or "127.0.0.1"
        port = cfg.get("port") or GATEWAY_DEFAULT_PORT
        return f"http://{host}:{port}"
    except Exception:
        return f"http://{GATEWAY_DEFAULT_HOST}:{GATEWAY_DEFAULT_PORT}"

def get_gateway_key():
    try:
        import yaml
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        keys = cfg.get("api-keys") or []
        return keys[0] if keys else GATEWAY_KEY
    except Exception:
        return GATEWAY_KEY

def is_responding():
    url = get_gateway_url()
    key = get_gateway_key()
    try:
        req = urllib.request.Request(
            f"{url}/v1/models",
            headers={"Authorization": f"Bearer {key}"})
        urllib.request.urlopen(req, timeout=3)
        return True
    except Exception:
        return False


def _configured_codex_model():
    try:
        if not os.path.exists(CODEX_CONFIG):
            return ""
        text = open(CODEX_CONFIG, encoding="utf-8").read()
        import re
        match = re.search(r'(?m)^\s*model\s*=\s*"([^"]+)"', text)
        return match.group(1) if match else ""
    except Exception:
        return ""


def probe_official_subscription():
    """Verify the local gateway can make one minimal official Codex request."""
    if not is_responding():
        return False, "网关未响应。"
    candidates = [_configured_codex_model(), "gpt-5.5", "gpt-5.4", "gpt-5.3-codex-spark"]
    seen = set()
    last_error = ""
    for model in candidates:
        model = (model or "").strip()
        if not model or model in seen:
            continue
        seen.add(model)
        body = json.dumps({
            "model": model,
            "input": "Reply with exactly: ok",
            "max_output_tokens": 16,
            "store": False,
        }).encode("utf-8")
        req = urllib.request.Request(
            get_gateway_url() + "/v1/responses",
            data=body,
            method="POST",
            headers={
                "Authorization": "Bearer " + get_gateway_key(),
                "Content-Type": "application/json",
            },
        )
        try:
            response = json.loads(urllib.request.urlopen(req, timeout=45).read().decode("utf-8"))
            if response.get("id") or response.get("output"):
                return True, "官方订阅凭据预检成功（" + model + "）。"
            last_error = "官方模型未返回有效响应。"
        except urllib.error.HTTPError as ex:
            try:
                detail = ex.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                detail = ""
            last_error = "HTTP {} {}".format(ex.code, detail)
        except Exception as ex:
            last_error = str(ex)
    return False, "官方订阅凭据预检失败：" + (last_error or "未找到可用官方模型。")

def get_status():
    runtime.ensure_all()
    running = is_running()
    responding = is_responding() if running else False
    pid = get_pid() if running else None
    url = get_gateway_url()
    models = []
    if responding:
        key = get_gateway_key()
        try:
            req = urllib.request.Request(
                f"{url}/v1/models",
                headers={"Authorization": f"Bearer {key}"})
            resp = urllib.request.urlopen(req, timeout=5)
            data = json.loads(resp.read())
            models = [m.get("id", "") for m in data.get("data", [])]
            models.sort()
        except Exception:
            pass
    return {
        "running": running,
        "responding": responding,
        "pid": pid,
        "url": url,
        "models": models,
    }

def _write_vbs():
    os.makedirs(INSTALL_DIR, exist_ok=True)
    content = (
        "' CLIProxyAPI hidden launcher\n"
        'Set sh = CreateObject("WScript.Shell")\n'
        'sh.Run """" & "' + EXE_PATH.replace("\\", "\\\\") + '" & """ -config ""' +
        CONFIG_PATH.replace("\\", "\\\\") + '""", 0, False\n'
    )
    with open(VBS_PATH, 'w', encoding='ascii') as f:
        f.write(content)

def start():
    ok, _ = runtime.ensure_all()
    if not ok:
        return False
    if is_running():
        return True
    if not os.path.exists(EXE_PATH):
        return False
    runtime.update_cli_proxy_runtime_if_possible()
    _write_vbs()
    subprocess.Popen(
        ["wscript.exe", VBS_PATH],
        creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(40):
        time.sleep(0.5)
        if is_responding():
            _write_managed_state()
            return True
    ok = is_running()
    if ok:
        _write_managed_state()
    return ok

def stop():
    pid = get_pid()
    if pid:
        try:
            subprocess.run(["taskkill", "/pid", str(pid), "/f"],
                           capture_output=True, timeout=10, creationflags=NO_WINDOW)
        except Exception:
            pass
    time.sleep(1)
    stopped = not is_running()
    if stopped:
        try:
            if os.path.exists(MANAGED_STATE_PATH):
                os.remove(MANAGED_STATE_PATH)
        except OSError:
            pass
    return stopped

def restart():
    stop()
    time.sleep(1)
    return start()

def get_scheduled_task_state():
    for task_name in (AUTOSTART_TASK_NAME, *LEGACY_AUTOSTART_TASK_NAMES):
        try:
            r = subprocess.run(
                ["schtasks", "/query", "/tn", task_name, "/fo", "list"],
                capture_output=True, text=True, timeout=5, creationflags=NO_WINDOW)
            if r.returncode != 0:
                continue
            if "Ready" in r.stdout:
                return "ready"
            elif "Running" in r.stdout:
                return "running"
            elif "Disabled" in r.stdout:
                return "disabled"
            return "unknown"
        except Exception:
            pass
    return "not_found"

def enable_autostart():
    runtime.ensure_all()
    _write_vbs()
    # Delete old task first
    for task_name in (AUTOSTART_TASK_NAME, *LEGACY_AUTOSTART_TASK_NAMES):
        subprocess.run(["schtasks", "/delete", "/tn", task_name, "/f"], capture_output=True, creationflags=NO_WINDOW)
    # Create new task with wscript + VBS (hidden window)
    cmd = (
        f'schtasks /create /tn "{AUTOSTART_TASK_NAME}" '
        f'/tr "wscript.exe \"{VBS_PATH}\"" '
        f'/sc onlogon /rl limited /f'
    )
    r = subprocess.run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW)
    return r.returncode == 0

def disable_autostart():
    ok = False
    for task_name in (AUTOSTART_TASK_NAME, *LEGACY_AUTOSTART_TASK_NAMES):
        r = subprocess.run(
            ["schtasks", "/delete", "/tn", task_name, "/f"],
            capture_output=True, text=True, creationflags=NO_WINDOW)
        ok = ok or r.returncode == 0
    return ok


def run_codex_login(device=False):
    ok, _ = runtime.ensure_all()
    if not ok:
        return False
    flag = "-codex-device-login" if device else "-codex-login"
    subprocess.Popen(
        [EXE_PATH, "-config", CONFIG_PATH, flag],
        cwd=INSTALL_DIR,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return True
