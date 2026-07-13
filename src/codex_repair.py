import os, re, datetime
from constants import *


def _desktop_catalog_line():
    return 'model_catalog_json = "' + CATALOG_PATH.replace("\\", "\\\\") + '"\n'


def _ensure_model_catalog(content):
    content = _remove_model_catalog(content)
    catalog_line = _desktop_catalog_line()
    desktop = re.search(r'(?m)^\[desktop\]\s*\n', content)
    if desktop:
        return content[:desktop.end()] + catalog_line + content[desktop.end():]
    return content.rstrip() + "\n\n[desktop]\n" + catalog_line


def _remove_model_catalog(content):
    return re.sub(r'(?m)^\s*model_catalog_json\s*=.*\n?', "", content)


def _set_top_level_string(content, key, value):
    line = key + ' = "' + value + '"\n'
    pattern = r'(?m)^\s*' + re.escape(key) + r'\s*=\s*"[^"]*"\s*\n?'
    if re.search(pattern, content):
        return re.sub(pattern, line, content, count=1)
    return line + content


def _set_top_level_bool(content, key, value):
    line = key + " = " + ("true" if value else "false") + "\n"
    pattern = r'(?m)^\s*' + re.escape(key) + r'\s*=\s*(?:true|false)\s*\n?'
    if re.search(pattern, content):
        return re.sub(pattern, line, content, count=1)
    return line + content


def _replace_provider_block(content, provider_block):
    pattern = r'(?ms)^\[model_providers\.cliproxyapi\]\s*\n.*?(?=^\[[^\]]+\]|\Z)'
    if re.search(pattern, content):
        return re.sub(pattern, provider_block.rstrip() + "\n\n", content, count=1)
    return content.rstrip() + "\n\n" + provider_block.rstrip() + "\n"


def check_codex_config():
    issues = []
    if not os.path.exists(CODEX_CONFIG):
        issues.append("config.toml 不存在")
        return issues, True

    with open(CODEX_CONFIG, encoding='utf-8') as f:
        content = f.read()

    needs_fix = False
    has_provider = "cliproxyapi" in content
    if not has_provider:
        issues.append("config.toml 未配置 cliproxyapi provider")
        needs_fix = True

    m = re.search(r'model_provider\s*=\s*"([^"]*)"', content)
    if m:
        if m.group(1) != "cliproxyapi":
            issues.append("当前 model_provider = " + m.group(1) + "，应为 cliproxyapi")
            needs_fix = True
    else:
        issues.append("未设置 model_provider")
        needs_fix = True

    if "[model_providers.cliproxyapi]" not in content:
        issues.append("缺少 [model_providers.cliproxyapi] 配置段")
        needs_fix = True
    if "experimental_bearer_token" not in content and "env_key" in content:
        issues.append("cliproxyapi provider 使用 env_key，建议改为本地固定 token")
        needs_fix = True

    return issues, needs_fix

def repair_codex_config(requires_openai_auth=True):
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = CODEX_CONFIG + ".bak-repair-" + stamp
    os.makedirs(CODEX_HOME, exist_ok=True)
    if os.path.exists(CODEX_CONFIG):
        with open(CODEX_CONFIG, encoding='utf-8') as f:
            old = f.read()
    else:
        old = ""
    with open(backup, 'w', encoding='utf-8') as f:
        f.write(old)

    from config_manager import load_config
    cfg = load_config()
    host = cfg.get("host") or "127.0.0.1"
    port = cfg.get("port") or 8317
    gateway_url = "http://" + str(host) + ":" + str(port) + "/v1"

    provider_block = (
        '\n[model_providers.cliproxyapi]\n'
        'name = "CLIProxyAPI Local Gateway"\n'
        'base_url = "' + gateway_url + '"\n'
        'wire_api = "responses"\n'
        'experimental_bearer_token = "' + GATEWAY_KEY + '"\n'
        'requires_openai_auth = ' + ("true" if requires_openai_auth else "false") + '\n'
    )

    old = _replace_provider_block(old, provider_block)
    old = _set_top_level_string(old, "model_provider", "cliproxyapi")
    old = _set_top_level_bool(old, "supports_websockets", True)
    old = _ensure_model_catalog(old)

    with open(CODEX_CONFIG, 'w', encoding='utf-8') as f:
        f.write(old)

    return True, "修复完成，备份已保存到 " + backup


def switch_to_official_only():
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = CODEX_CONFIG + ".bak-official-" + stamp
    os.makedirs(CODEX_HOME, exist_ok=True)
    if os.path.exists(CODEX_CONFIG):
        with open(CODEX_CONFIG, encoding="utf-8") as f:
            old = f.read()
    else:
        old = ""
    with open(backup, "w", encoding="utf-8") as f:
        f.write(old)
    # Do not touch auth.json, global state, sessions, or archived sessions.
    # The official client falls back when no active custom provider is selected.
    new = re.sub(r'(?m)^\s*model_provider\s*=\s*"cliproxyapi"\s*\n?', "", old)
    new = _remove_model_catalog(new)
    with open(CODEX_CONFIG, "w", encoding="utf-8") as f:
        f.write(new)
    return True, "已切换为纯官方订阅。备份已保存到 " + backup


def read_effective_provider_state():
    if not os.path.exists(CODEX_CONFIG):
        return {"model_provider": "", "requires_openai_auth": None, "uses_gateway": False}
    text = open(CODEX_CONFIG, encoding="utf-8").read()
    m = re.search(r'(?m)^\s*model_provider\s*=\s*"([^"]*)"', text)
    r = re.search(r'requires_openai_auth\s*=\s*(true|false)', text, re.I)
    provider = m.group(1) if m else ""
    return {
        "model_provider": provider or "官方默认",
        "requires_openai_auth": (r.group(1).lower() == "true") if r else None,
        "uses_gateway": provider == "cliproxyapi",
    }
