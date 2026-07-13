import datetime
import json
import os
import shutil
import tempfile

from constants import APP_RUNTIME_DIR, CODEX_HOME


GLOBAL_STATE_PATH = os.path.join(CODEX_HOME, ".codex-global-state.json")
SESSION_ROOT = os.path.join(CODEX_HOME, "sessions")
ARCHIVED_SESSION_ROOT = os.path.join(CODEX_HOME, "archived_sessions")
SNAPSHOT_ROOT = os.path.join(APP_RUNTIME_DIR, "conversation-index-backups")


def _session_files(root):
    result = []
    if not os.path.isdir(root):
        return result
    for base, _, files in os.walk(root):
        for name in files:
            if name.endswith(".jsonl"):
                result.append(os.path.join(base, name))
    return result


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def get_status():
    state = _read_json(GLOBAL_STATE_PATH, {})
    atom = state.get("electron-persisted-atom-state") or {}
    descriptions = atom.get("thread-descriptions-v1") or {}
    snapshots = []
    if os.path.isdir(SNAPSHOT_ROOT):
        snapshots = [x for x in os.listdir(SNAPSHOT_ROOT) if os.path.isdir(os.path.join(SNAPSHOT_ROOT, x))]
    return {
        "active_sessions": len(_session_files(SESSION_ROOT)),
        "archived_sessions": len(_session_files(ARCHIVED_SESSION_ROOT)),
        "indexed_threads": len(descriptions) if isinstance(descriptions, dict) else 0,
        "snapshots": len(snapshots),
    }


def snapshot(reason="mode-switch"):
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    root = os.path.join(SNAPSHOT_ROOT, stamp + "-" + reason)
    os.makedirs(root, exist_ok=True)
    if os.path.exists(GLOBAL_STATE_PATH):
        shutil.copy2(GLOBAL_STATE_PATH, os.path.join(root, ".codex-global-state.json"))
    with open(os.path.join(root, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump({"created_at": datetime.datetime.now().isoformat(timespec="seconds"), "reason": reason, **get_status()}, handle, ensure_ascii=False, indent=2)
    return root


def capture_state(reason="mode-switch"):
    """Capture the desktop sidebar state byte-for-byte before a mode switch."""
    root = snapshot(reason)
    return {
        "root": root,
        "state_path": os.path.join(root, ".codex-global-state.json"),
        "existed": os.path.exists(GLOBAL_STATE_PATH),
    }


def restore_state(capture):
    """Atomically restore the exact sidebar/archive state captured above."""
    if not capture:
        return False
    source = capture.get("state_path")
    existed = bool(capture.get("existed"))
    os.makedirs(CODEX_HOME, exist_ok=True)
    if existed and source and os.path.exists(source):
        fd, temp = tempfile.mkstemp(prefix=".codex-global-state-", suffix=".json", dir=CODEX_HOME)
        os.close(fd)
        try:
            shutil.copy2(source, temp)
            os.replace(temp, GLOBAL_STATE_PATH)
        finally:
            if os.path.exists(temp):
                os.remove(temp)
        return True
    if not existed and os.path.exists(GLOBAL_STATE_PATH):
        os.remove(GLOBAL_STATE_PATH)
    return True


def _read_session_meta(path):
    try:
        with open(path, encoding="utf-8") as handle:
            first = json.loads(handle.readline())
        payload = first.get("payload") or {}
        session_id = payload.get("session_id") or payload.get("id")
        if not session_id:
            return None
        return {
            "id": session_id,
            "source": payload.get("source"),
            "thread_source": payload.get("thread_source"),
            "cwd": payload.get("cwd") or "",
            "mtime": os.path.getmtime(path),
        }
    except Exception:
        return None


def rebuild_visible_index():
    """Rebuild only local sidebar hints; session JSONL files are never modified."""
    snapshot("before-index-rebuild")
    state = _read_json(GLOBAL_STATE_PATH, {})
    atom = state.setdefault("electron-persisted-atom-state", {})
    descriptions = atom.setdefault("thread-descriptions-v1", {})
    roots = atom.setdefault("thread-workspace-root-hints", {})

    entries = []
    for path in _session_files(SESSION_ROOT):
        meta = _read_session_meta(path)
        if meta and meta["source"] == "vscode" and meta["thread_source"] == "user":
            entries.append(meta)
    entries.sort(key=lambda item: item["mtime"], reverse=True)

    visible_ids = []
    for item in entries:
        session_id = item["id"]
        visible_ids.append(session_id)
        descriptions.setdefault(session_id, "已恢复的本地会话")
        if item["cwd"]:
            roots.setdefault(session_id, item["cwd"])

    # This was the pre-migration desktop index. Newer builds still preserve it
    # as a harmless local hint, while sessions remain the source of truth.
    atom["projectless-thread-ids"] = visible_ids
    temp = GLOBAL_STATE_PATH + ".new"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, separators=(",", ":"))
    os.replace(temp, GLOBAL_STATE_PATH)
    return {"recovered": len(visible_ids), "snapshot": SNAPSHOT_ROOT}
