from pathlib import Path
from modules.project_paths import get_project_root
import importlib

from core.state import set_value


ROOT_DIR = get_project_root()
BROWSER_PROFILE_REL = Path("Projects") / "BrowserProfile"
BROWSER_PROFILE_DIR = ROOT_DIR / BROWSER_PROFILE_REL

RELAY_APPLY_ACTIONS = {
    "apply",
    "apply_response",
    "apply_answer",
    "apply_last_response",
    "relay_apply",
}


def _resolve(path):
    try:
        return Path(path).resolve()
    except Exception:
        return Path(str(path or ""))


def is_browser_profile_path(path, root_dir=ROOT_DIR):
    full = _resolve(path)
    profile = _resolve(Path(root_dir) / BROWSER_PROFILE_REL)

    return full == profile or profile in full.parents


def should_ignore_path(path):
    return is_browser_profile_path(path)


def filter_walk_dirs(current_root, dirs):
    safe_dirs = []

    for name in list(dirs):
        candidate = Path(current_root) / name

        if is_browser_profile_path(candidate):
            continue

        safe_dirs.append(name)

    dirs[:] = safe_dirs
    return dirs


def copytree_ignore(src, names):
    ignored = set()
    src_path = Path(src)

    for name in names:
        candidate = src_path / name

        if is_browser_profile_path(candidate):
            ignored.add(name)

    return ignored


def is_relay_apply_action(tool, action):
    return str(tool or "") == "chatgpt_relay" and str(action or "") in RELAY_APPLY_ACTIONS


def close_gpt_browser_context():
    """Close GPT Browser Bridge so Chromium releases BrowserProfile locks."""
    try:
        bridge = importlib.import_module("modules.gpt_browser_bridge")
    except Exception as e:
        result = f"GPT Browser Bridge close skipped: {e}"
        set_value("last_gpt_browser_action", "close")
        set_value("last_gpt_browser_close_result", result)
        return result

    close_bridge = getattr(bridge, "close_bridge", None)

    if callable(close_bridge):
        try:
            result = close_bridge()
            text = str(result or "GPT Browser Bridge close: close_bridge executed")
            set_value("last_gpt_browser_action", "close")
            set_value("last_gpt_browser_close_result", text)
            return text
        except Exception:
            pass

    closed = []

    for attr in ["_page", "_context", "_browser"]:
        obj = getattr(bridge, attr, None)

        if obj is None:
            continue

        try:
            obj.close()
            closed.append(attr)
        except Exception:
            pass

        try:
            setattr(bridge, attr, None)
        except Exception:
            pass

    playwright = getattr(bridge, "_playwright", None)

    if playwright is not None:
        try:
            playwright.stop()
            closed.append("_playwright")
        except Exception:
            pass

        try:
            setattr(bridge, "_playwright", None)
        except Exception:
            pass

    if closed:
        text = "GPT Browser Bridge close: closed " + ", ".join(closed)
    else:
        text = "GPT Browser Bridge close: no active Playwright objects found"

    set_value("last_gpt_browser_action", "close")
    set_value("last_gpt_browser_close_result", text)
    return text
