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
UNIFIED_MARKER = "modeldock-sidebar-index-unified-v1"


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


def synchronize_sidebar_indexes():
    """Migrate the legacy Codex sidebar index to the new ChatGPT layout.

    The unified ChatGPT/Codex desktop stores its canonical projectless index at
    the JSON root. Older Codex builds stored the same values inside
    ``electron-persisted-atom-state``. On the first run we merge both active
    sets. Afterward the new root is authoritative, so archived/deleted threads
    cannot be resurrected by stale legacy data.
    """
    if not os.path.exists(GLOBAL_STATE_PATH):
        return {"changed": False, "threads": 0}
    state = _read_json(GLOBAL_STATE_PATH, {})
    atom = state.setdefault("electron-persisted-atom-state", {})
    top_ids = state.get("projectless-thread-ids") or []
    legacy_ids = atom.get("projectless-thread-ids") or []
    active_ids = set()
    for path in _session_files(SESSION_ROOT):
        meta = _read_session_meta(path)
        if meta:
            active_ids.add(meta["id"])

    if state.get(UNIFIED_MARKER):
        merged = [sid for sid in top_ids if sid in active_ids]
    else:
        merged = []
        seen = set()
        for sid in list(top_ids) + list(legacy_ids):
            if sid in active_ids and sid not in seen:
                seen.add(sid)
                merged.append(sid)

    top_roots = state.get("thread-workspace-root-hints") or {}
    legacy_roots = atom.get("thread-workspace-root-hints") or {}
    roots = {}
    for sid in merged:
        value = top_roots.get(sid) or legacy_roots.get(sid)
        if value:
            roots[sid] = value

    changed = (
        top_ids != merged
        or legacy_ids != merged
        or state.get("thread-workspace-root-hints") != roots
        or atom.get("thread-workspace-root-hints") != roots
        or not state.get(UNIFIED_MARKER)
    )
    if changed:
        state["projectless-thread-ids"] = merged
        state["thread-workspace-root-hints"] = roots
        atom["projectless-thread-ids"] = list(merged)
        atom["thread-workspace-root-hints"] = dict(roots)
        state[UNIFIED_MARKER] = True
        temp = GLOBAL_STATE_PATH + ".new"
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, separators=(",", ":"))
        os.replace(temp, GLOBAL_STATE_PATH)
    return {"changed": changed, "threads": len(merged)}


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
    """Repair both old and new local sidebar indexes; JSONL is untouched."""
    snapshot("before-index-rebuild")
    result = synchronize_sidebar_indexes()
    return {"recovered": result["threads"], "snapshot": SNAPSHOT_ROOT}
