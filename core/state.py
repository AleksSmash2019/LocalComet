import json
from pathlib import Path
from modules.project_paths import get_project_root

STATE_FILE = get_project_root() / "memory" / "state.json"
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_state():
    if not STATE_FILE.exists():
        return {}

    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except:
        return {}


def save_state(data: dict):
    STATE_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def set_value(key: str, value):
    state = load_state()
    state[key] = value
    save_state(state)


def get_value(key: str, default=None):
    state = load_state()
    return state.get(key, default)