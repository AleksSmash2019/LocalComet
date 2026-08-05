from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from modules.project_paths import projects_dir

BASE_DIR = projects_dir()
BASE_DIR.mkdir(parents=True, exist_ok=True)


def safe_path(path: str) -> Path:
    target = (BASE_DIR / path).resolve()
    base = BASE_DIR.resolve()

    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError("Запрещенный путь за пределами Projects.") from exc

    return target


def create_folder(path: str):
    target = safe_path(path)
    target.mkdir(parents=True, exist_ok=True)
    return f"Папка создана: {target}"


def write_file(path: str, content: str):
    target = safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Файл создан: {target}"


def read_file(path: str):
    target = safe_path(path)

    if not target.exists():
        return f"Файл не найден: {target}"

    return target.read_text(encoding="utf-8")


def list_files(path: str = ""):
    target = safe_path(path)

    if not target.exists():
        return f"Папка не найдена: {target}"

    items = []
    for item in target.iterdir():
        kind = "DIR " if item.is_dir() else "FILE"
        items.append(f"{kind}: {item.name}")

    return "\n".join(items) if items else "Папка пустая."


def delete_path(path: str):
    target = safe_path(path)

    if not target.exists():
        return f"Не найдено: {target}"

    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()

    return f"Удалено: {target}"


# Rollback journal: maps canonical target path → snapshot bytes taken before
# the most recent restore call.  Kept in memory; survives the process lifetime
# of the sidecar session.  Allows one undo level (rollback of a rollback).
_rollback_journal: dict[str, bytes] = {}


def rollback(path: str, snapshot_path: str) -> str:
    """Restore *path* from *snapshot_path* (GUARDED, requires_approval).

    Path A (T9):
    1. Snapshot current state of *path* into the in-memory journal so the
       rollback itself can be undone.
    2. Overwrite *path* with the bytes read from *snapshot_path*.
    3. The snapshot file is NOT deleted — it remains available for further
       audits or re-apply.

    Both paths must reside inside the Projects/ confinement zone.
    """
    target = safe_path(path)
    source = safe_path(snapshot_path)

    if not source.exists():
        return f"Snapshot не найден: {source}"

    # Save current state before overwriting (allows rollback of rollback).
    if target.exists():
        _rollback_journal[str(target)] = target.read_bytes()
    else:
        _rollback_journal[str(target)] = b""

    snapshot_bytes = source.read_bytes()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(snapshot_bytes)

    return f"Восстановлено: {target} из {source}"


def rollback_undo(path: str) -> str:
    """Undo the most recent rollback() call for *path* (GUARDED, requires_approval).

    Restores the content that was displaced by the preceding rollback() call.
    Returns an error string if no prior rollback snapshot exists.
    """
    target = safe_path(path)
    key = str(target)

    if key not in _rollback_journal:
        return f"Нет сохранённого снимка для отката: {target}"

    prior_bytes = _rollback_journal.pop(key)
    target.parent.mkdir(parents=True, exist_ok=True)
    if prior_bytes:
        target.write_bytes(prior_bytes)
    elif target.exists():
        target.unlink()

    return f"Откат отменён: {target} восстановлен в предыдущее состояние"