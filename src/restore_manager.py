import datetime
import json
import os
import shutil

from constants import *


TRACKED_FILES = [
    ("cliproxy-config", CONFIG_PATH),
    ("codex-config", CODEX_CONFIG),
    ("codex-catalog", CATALOG_PATH),
    ("codex-auth", os.path.join(CODEX_HOME, "auth.json")),
]

# Chat history and the ChatGPT desktop global state are intentionally excluded.
# Mode changes must never move, remove, or restore conversation files.
EXCLUDED_CODEX_DATA = [
    os.path.join(CODEX_HOME, "sessions"),
    os.path.join(CODEX_HOME, "archived_sessions"),
    os.path.join(CODEX_HOME, ".codex-global-state.json"),
]


def _safe_name(text):
    text = (text or "").strip() or "restore"
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in text)[:80]


def _copy_if_exists(src, dst):
    if os.path.exists(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        return True
    return False


def create_restore_point(kind="auto", name=None, notes=""):
    kind = "manual" if kind == "manual" else "auto"
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe = _safe_name(name or kind)
    root = os.path.join(RESTORE_ROOT, kind, stamp + "-" + safe)
    os.makedirs(root, exist_ok=True)
    copied = []
    for label, path in TRACKED_FILES:
        if _copy_if_exists(path, os.path.join(root, "files", label, os.path.basename(path))):
            copied.append({"label": label, "source": path})
    auth_snapshot = os.path.join(root, "files", "cliproxy-auth")
    if os.path.isdir(AUTH_DIR):
        os.makedirs(auth_snapshot, exist_ok=True)
        for fn in os.listdir(AUTH_DIR):
            src = os.path.join(AUTH_DIR, fn)
            if os.path.isfile(src) and fn.lower().endswith(".json"):
                shutil.copy2(src, os.path.join(auth_snapshot, fn))
        if os.listdir(auth_snapshot):
            copied.append({"label": "cliproxy-auth", "source": AUTH_DIR})
    manifest = {
        "kind": kind,
        "name": name or ("自动回退点 " + stamp),
        "notes": notes or "",
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "app_version": APP_VERSION,
        "items": copied,
        "excluded": EXCLUDED_CODEX_DATA,
    }
    with open(os.path.join(root, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    try:
        import conversation_guard
        conversation_guard.snapshot("restore-point-" + safe)
    except Exception:
        pass
    return root


def list_restore_points():
    result = []
    for kind in ("manual", "auto"):
        base = os.path.join(RESTORE_ROOT, kind)
        if not os.path.isdir(base):
            continue
        for name in os.listdir(base):
            root = os.path.join(base, name)
            manifest_path = os.path.join(root, "manifest.json")
            if not os.path.isfile(manifest_path):
                continue
            try:
                with open(manifest_path, encoding="utf-8") as f:
                    manifest = json.load(f)
            except Exception:
                manifest = {}
            result.append({
                "id": root,
                "kind": kind,
                "name": manifest.get("name") or name,
                "notes": manifest.get("notes") or "",
                "created_at": manifest.get("created_at") or name[:15],
                "items": len(manifest.get("items") or []),
            })
    return sorted(result, key=lambda x: x["created_at"], reverse=True)


def restore(point_dir):
    if not point_dir or not os.path.isdir(point_dir):
        raise ValueError("回退点不存在。")
    create_restore_point("auto", "restore-before-apply", "回退前自动保护")
    mapping = {
        "cliproxy-config": CONFIG_PATH,
        "codex-config": CODEX_CONFIG,
        "codex-catalog": CATALOG_PATH,
        "codex-auth": os.path.join(CODEX_HOME, "auth.json"),
    }
    for label, dst in mapping.items():
        src_dir = os.path.join(point_dir, "files", label)
        if os.path.isdir(src_dir):
            files = [os.path.join(src_dir, x) for x in os.listdir(src_dir)]
            if files:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(files[0], dst)
    auth_dir = os.path.join(point_dir, "files", "cliproxy-auth")
    if os.path.isdir(auth_dir):
        os.makedirs(AUTH_DIR, exist_ok=True)
        for fn in os.listdir(auth_dir):
            src = os.path.join(auth_dir, fn)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(AUTH_DIR, fn))
    return True
