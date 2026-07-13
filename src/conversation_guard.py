import datetime
import json
import os
import shutil
import sqlite3
import tempfile
from contextlib import closing

from constants import APP_RUNTIME_DIR, CODEX_HOME


GLOBAL_STATE_PATH = os.path.join(CODEX_HOME, ".codex-global-state.json")
SESSION_ROOT = os.path.join(CODEX_HOME, "sessions")
ARCHIVED_SESSION_ROOT = os.path.join(CODEX_HOME, "archived_sessions")
SNAPSHOT_ROOT = os.path.join(APP_RUNTIME_DIR, "conversation-index-backups")
PROVIDER_SNAPSHOT_ROOT = os.path.join(APP_RUNTIME_DIR, "conversation-provider-backups")
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


def _state_database_path():
    candidates = []
    if os.path.isdir(CODEX_HOME):
        for name in os.listdir(CODEX_HOME):
            if name.startswith("state_") and name.endswith(".sqlite"):
                path = os.path.join(CODEX_HOME, name)
                candidates.append((os.path.getmtime(path), path))
    return max(candidates, default=(0, None))[1]


def _replace_first_line(path, line):
    """Replace only the JSONL metadata line and preserve the conversation bytes."""
    with open(path, "rb") as handle:
        data = handle.read()
    separator = data.find(b"\n")
    tail = data[separator + 1:] if separator >= 0 else b""
    encoded = line.encode("utf-8") + b"\n" + tail
    fd, temporary = tempfile.mkstemp(prefix=".modeldock-provider-", suffix=".jsonl", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        shutil.copymode(path, temporary)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def migrate_desktop_conversations(target_provider):
    """Move every desktop conversation to the provider selected by the UI.

    The unified ChatGPT/Codex app filters its project thread list by the
    provider stored both in the JSONL session header and in state_*.sqlite.
    Updating only config.toml or the sidebar IDs therefore creates apparently
    separate histories.  ChatGPT/Codex must be stopped before this function is
    called.
    """
    if target_provider not in ("openai", "cliproxyapi"):
        raise ValueError("不支持的会话目标 provider：" + str(target_provider))

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    root = os.path.join(PROVIDER_SNAPSHOT_ROOT, stamp + "-to-" + target_provider)
    os.makedirs(root, exist_ok=False)
    entries = []
    changed_paths = []
    db_path = _state_database_path()
    db_rows = []

    for session_root in (SESSION_ROOT, ARCHIVED_SESSION_ROOT):
        for path in _session_files(session_root):
            try:
                with open(path, encoding="utf-8-sig") as handle:
                    original_line = handle.readline().rstrip("\r\n")
                first = json.loads(original_line)
                payload = first.get("payload") or {}
                if first.get("type") != "session_meta" or payload.get("source") != "vscode":
                    continue
                session_id = payload.get("id") or payload.get("session_id")
                entries.append({
                    "path": os.path.relpath(path, CODEX_HOME),
                    "id": session_id,
                    "provider": payload.get("model_provider"),
                    "first_line": original_line,
                })
            except Exception:
                continue

    if db_path and os.path.exists(db_path):
        with closing(sqlite3.connect(db_path, timeout=15)) as connection:
            db_rows = [
                {"id": row[0], "provider": row[1]}
                for row in connection.execute(
                    "SELECT id, model_provider FROM threads WHERE source = 'vscode'"
                )
            ]
            backup_path = os.path.join(root, os.path.basename(db_path))
            with closing(sqlite3.connect(backup_path)) as backup:
                connection.backup(backup)

    manifest = {
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "target_provider": target_provider,
        "database": os.path.basename(db_path) if db_path else None,
        "sessions": entries,
        "database_rows": db_rows,
    }
    manifest_path = os.path.join(root, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)

    try:
        for entry in entries:
            if entry["provider"] == target_provider:
                continue
            path = os.path.join(CODEX_HOME, entry["path"])
            first = json.loads(entry["first_line"])
            first["payload"]["model_provider"] = target_provider
            _replace_first_line(path, json.dumps(first, ensure_ascii=False, separators=(",", ":")))
            changed_paths.append(path)

        database_changed = 0
        if db_path and os.path.exists(db_path):
            with closing(sqlite3.connect(db_path, timeout=15)) as connection:
                cursor = connection.execute(
                    "UPDATE threads SET model_provider = ? WHERE source = 'vscode' AND model_provider <> ?",
                    (target_provider, target_provider),
                )
                database_changed = cursor.rowcount
                connection.commit()
        return {
            "snapshot": root,
            "sessions_seen": len(entries),
            "sessions_changed": len(changed_paths),
            "database_changed": database_changed,
            "target_provider": target_provider,
        }
    except Exception:
        restore_provider_snapshot(root)
        raise


def restore_provider_snapshot(root):
    """Undo a provider migration without changing conversation bodies."""
    manifest = _read_json(os.path.join(root, "manifest.json"), {})
    for entry in manifest.get("sessions") or []:
        path = os.path.join(CODEX_HOME, entry.get("path", ""))
        if os.path.isfile(path) and entry.get("first_line"):
            _replace_first_line(path, entry["first_line"])

    db_name = manifest.get("database")
    db_path = os.path.join(CODEX_HOME, db_name) if db_name else None
    rows = manifest.get("database_rows") or []
    if db_path and os.path.exists(db_path) and rows:
        with closing(sqlite3.connect(db_path, timeout=15)) as connection:
            connection.executemany(
                "UPDATE threads SET model_provider = ? WHERE id = ?",
                [(row.get("provider") or "", row.get("id")) for row in rows],
            )
            connection.commit()
    return True


def rebuild_visible_index():
    """Repair both old and new local sidebar indexes; JSONL is untouched."""
    snapshot("before-index-rebuild")
    result = synchronize_sidebar_indexes()
    return {"recovered": result["threads"], "snapshot": SNAPSHOT_ROOT}
