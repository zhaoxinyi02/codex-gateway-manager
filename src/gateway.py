import os, subprocess, time, json, urllib.request, urllib.error
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
            return True
    return is_running()

def stop():
    pid = get_pid()
    if pid:
        try:
            subprocess.run(["taskkill", "/pid", str(pid), "/f"],
                           capture_output=True, timeout=10, creationflags=NO_WINDOW)
        except Exception:
            pass
    time.sleep(1)
    return not is_running()

def restart():
    stop()
    time.sleep(1)
    return start()

def get_scheduled_task_state():
    for task_name in (AUTOSTART_TASK_NAME, OLD_AUTOSTART_TASK_NAME):
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
    for task_name in (AUTOSTART_TASK_NAME, OLD_AUTOSTART_TASK_NAME):
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
    for task_name in (AUTOSTART_TASK_NAME, OLD_AUTOSTART_TASK_NAME):
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
