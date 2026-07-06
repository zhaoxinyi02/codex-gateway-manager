import glob
import os
import subprocess
import time

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _codex_processes():
    try:
        ps = (
            "Get-Process Codex -ErrorAction SilentlyContinue | "
            "Select-Object Id,Path | ConvertTo-Json -Compress"
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
            {"pid": int(x.get("Id")), "path": x.get("Path") or ""}
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
        os.path.join(local, "OpenAI", "Codex", "Codex.exe"),
        os.path.join(local, "codex", "Codex.exe"),
    ]
    candidates.extend(glob.glob(os.path.join(local, "Packages", "OpenAI.Codex_*", "LocalCache", "*", "Codex.exe")))
    candidates.extend(glob.glob(os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "WindowsApps", "OpenAI.Codex_*", "app", "Codex.exe")))
    for path in candidates:
        if path and os.path.exists(path):
            yield path


def start():
    if is_running():
        return True
    for path in _candidate_paths():
        try:
            subprocess.Popen([path], creationflags=subprocess.CREATE_NO_WINDOW)
            for _ in range(20):
                time.sleep(0.5)
                if is_running():
                    return True
        except Exception:
            continue
    try:
        subprocess.Popen(["explorer.exe", "shell:AppsFolder\\OpenAI.Codex_2p2nqsd0c76g0!App"], creationflags=NO_WINDOW)
        for _ in range(20):
            time.sleep(0.5)
            if is_running():
                return True
    except Exception:
        pass
    return False


def stop():
    for proc in _codex_processes():
        try:
            subprocess.run(["taskkill", "/pid", str(proc["pid"]), "/f"], capture_output=True, timeout=8, creationflags=NO_WINDOW)
        except Exception:
            pass
    time.sleep(1)
    return not is_running()


def restart():
    stop()
    time.sleep(1)
    return start()
