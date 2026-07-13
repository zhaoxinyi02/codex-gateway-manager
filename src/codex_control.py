import glob
import os
import subprocess
import time

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _codex_processes():
    try:
        ps = (
            "Get-Process Codex,ChatGPT -ErrorAction SilentlyContinue | "
            "Where-Object { $_.ProcessName -eq 'Codex' -or "
            "($_.ProcessName -eq 'ChatGPT' -and ($_.Path -like '*OpenAI.Codex_*' -or $_.Path -like '*OpenAI\\Codex*')) } | "
            "Select-Object Id,Path,ProcessName | ConvertTo-Json -Compress"
        )
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=8, creationflags=NO_WINDOW,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return []
        import json
        data = json.loads(r.stdout)
        if isinstance(data, dict):
            data = [data]
        return [
            {"pid": int(x.get("Id")), "path": x.get("Path") or "", "name": x.get("ProcessName") or ""}
            for x in data if x.get("Id")
        ]
    except Exception:
        return []


def is_running():
    return bool(_codex_processes())


def get_status():
    procs = _codex_processes()
    return {
        "running": bool(procs),
        "count": len(procs),
        "paths": sorted({p["path"] for p in procs if p.get("path")}),
    }


def _candidate_paths():
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        os.path.join(local, "OpenAI", "Codex", "ChatGPT.exe"),
        os.path.join(local, "OpenAI", "Codex", "Codex.exe"),
        os.path.join(local, "codex", "Codex.exe"),
    ]
    candidates.extend(glob.glob(os.path.join(local, "Packages", "OpenAI.Codex_*", "LocalCache", "*", "Codex.exe")))
    candidates.extend(glob.glob(os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "WindowsApps", "OpenAI.Codex_*", "app", "ChatGPT.exe")))
    candidates.extend(glob.glob(os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "WindowsApps", "OpenAI.Codex_*", "app", "Codex.exe")))
    for path in candidates:
        if path and os.path.exists(path):
            yield path


def _app_ids():
    ids = ["OpenAI.Codex_2p2nqsd0c76g0!App"]
    try:
        ps = "Get-StartApps | Where-Object { $_.Name -eq 'ChatGPT' -or $_.Name -eq 'Codex' -or $_.Name -like '*Codex*' } | Select-Object -ExpandProperty AppID"
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=8, creationflags=NO_WINDOW,
        )
        for line in r.stdout.splitlines():
            line = line.strip()
            if line and line not in ids:
                ids.insert(0, line)
    except Exception:
        pass
    return ids


def start():
    if is_running():
        return True
    for app_id in _app_ids():
        uri = "shell:AppsFolder\\" + app_id
        try:
            os.startfile(uri)
            for _ in range(50):
                time.sleep(0.3)
                if is_running():
                    return True
        except Exception:
            pass
        try:
            subprocess.Popen(["explorer.exe", uri], creationflags=NO_WINDOW)
            for _ in range(50):
                time.sleep(0.3)
                if is_running():
                    return True
        except Exception:
            pass
    for path in _candidate_paths():
        try:
            subprocess.Popen([path], creationflags=subprocess.CREATE_NO_WINDOW)
            for _ in range(50):
                time.sleep(0.3)
                if is_running():
                    return True
        except Exception:
            continue
    return False


def stop():
    # Kill the ChatGPT desktop roots before their Codex children. Killing only
    # codex.exe lets the Electron shell immediately respawn it and later write
    # a stale in-memory sidebar state back to disk.
    processes = sorted(_codex_processes(), key=lambda p: p.get("name") != "ChatGPT")
    for proc in processes:
        try:
            subprocess.run(["taskkill", "/pid", str(proc["pid"]), "/t", "/f"], capture_output=True, timeout=8, creationflags=NO_WINDOW)
        except Exception:
            pass
    for _ in range(30):
        if not is_running():
            return True
        time.sleep(0.2)
    return not is_running()


def restart():
    stop()
    time.sleep(1)
    return start()
