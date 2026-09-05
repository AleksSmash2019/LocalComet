from __future__ import annotations

import shutil
import os
from pathlib import Path
from typing import Optional

from modules.project_paths import projects_dir

BASE_DIR = projects_dir()
BASE_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB guard — fail early on huge payloads
MAX_LIST_ENTRIES = 500

def _is_symlink_or_reparse(p: Path) -> bool:
    # Fail closed: any inability to determine reparse status is treated as link.
    try:
        if p.is_symlink():
            return True
        if hasattr(p, "is_junction"):
            try:
                if p.is_junction():  # type: ignore[attr-defined]
                    return True
            except OSError:
                return True
        if p.exists() and os.name == "nt":
            import ctypes

            FILE_ATTRIBUTE_REPARSE_POINT = 0x400
            try:
                GetFileAttributesW = ctypes.windll.kernel32.GetFileAttributesW
                GetFileAttributesW.argtypes = [ctypes.c_wchar_p]
                GetFileAttributesW.restype = ctypes.c_uint32
                attrs = GetFileAttributesW(str(p))
                if attrs != 0xFFFFFFFF and (attrs & FILE_ATTRIBUTE_REPARSE_POINT):
                    return True
            except Exception as exc:
                # Fail closed: if reparse attribute cannot be determined for an existing path,
                # treat as link to avoid bypass via exception.
                raise ValueError("Символические ссылки запрещены.") from exc
    except OSError:
        raise ValueError("Символические ссылки запрещены.")
    return False


def _reject_pre_resolve_links(user_path: str) -> None:
    # Check every existing component of the raw candidate WITHOUT following links.
    # This catches a symlink/junction/reparse component that points even inside
    # BASE_DIR, where the later resolve() would hide the link.
    base_resolved = BASE_DIR.resolve()
    p = Path(user_path)
    if p.is_absolute():
        cur = Path(p.anchor)
        # anchor parts already counted; iterate remaining segments lexically
        anchor_len = len(Path(p.anchor).parts)
        segments = p.parts[anchor_len:]
        for seg in segments:
            if seg in ("", "."):
                continue
            if seg == "..":
                cur = cur.parent
                continue
            cur = cur / seg
            try:
                if cur.exists() or cur.is_symlink():
                    if _is_symlink_or_reparse(cur):
                        raise ValueError("Символические ссылки запрещены.")
            except ValueError:
                raise
            except OSError:
                raise ValueError("Символические ссылки запрещены.")
        return
    cur = base_resolved
    for seg in p.parts:
        if seg in ("", "."):
            continue
        if seg == "..":
            # Lexical .. : move up but never below base's parent check — containment will fail later.
            if cur == base_resolved:
                cur = cur.parent
            else:
                cur = cur.parent
            continue
        cur = cur / seg
        try:
            if cur.exists() or cur.is_symlink():
                if _is_symlink_or_reparse(cur):
                    raise ValueError("Символические ссылки запрещены.")
        except ValueError:
            raise
        except OSError:
            raise ValueError("Символические ссылки запрещены.")


def _reject_symlink(target: Path) -> None:
    # Post-resolve defense-in-depth: check resolved ancestors up to BASE_DIR.
    base = BASE_DIR.resolve()
    try:
        resolved = target.resolve()
        cur = resolved
        while True:
            try:
                if _is_symlink_or_reparse(cur):
                    raise ValueError("Символические ссылки запрещены.")
            except ValueError:
                raise
            if cur == base or cur.parent == cur:
                break
            cur = cur.parent
            try:
                cur.relative_to(base)
            except ValueError:
                if cur != base:
                    break
    except ValueError:
        raise
    except OSError:
        raise ValueError("Символические ссылки запрещены.")


def safe_path(path: str) -> Path:
    # Pre-resolve link check must happen before resolve() hides the component.
    _reject_pre_resolve_links(path)
    target = (BASE_DIR / path).resolve()
    base = BASE_DIR.resolve()

    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError("Запрещенный путь за пределами Projects.") from exc

    # Post-resolve check remains as defense-in-depth for any race.
    _reject_symlink(target)

    return target


def create_folder(path: str):
    target = safe_path(path)
    target.mkdir(parents=True, exist_ok=True)
    return f"Папка создана: {target}"


def write_file(path: str, content: str):
    if len(content.encode("utf-8")) > MAX_FILE_BYTES:
        return f"Отклонено: файл превышает лимит {MAX_FILE_BYTES} байт"
    target = safe_path(path)
    _reject_symlink(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Файл создан: {target}"


def read_file(path: str):
    target = safe_path(path)

    if not target.exists():
        return f"Файл не найден: {target}"

    if target.stat().st_size > MAX_FILE_BYTES:
        return f"Отклонено: файл превышает лимит {MAX_FILE_BYTES} байт — используйте предпросмотр"

    return target.read_text(encoding="utf-8")


def list_files(path: str = ""):
    target = safe_path(path)

    if not target.exists():
        return f"Папка не найдена: {target}"

    entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    if len(entries) > MAX_LIST_ENTRIES:
        shown = entries[:MAX_LIST_ENTRIES]
        hidden = len(entries) - MAX_LIST_ENTRIES
        items = [f"{'DIR ' if p.is_dir() else 'FILE'}: {p.name}" for p in shown]
        items.append(f"... ещё {hidden} элементов скрыто (лимит {MAX_LIST_ENTRIES})")
        return "\n".join(items)
    items = [f"{'DIR ' if p.is_dir() else 'FILE'}: {p.name}" for p in entries]

    return "\n".join(items) if items else "Папка пустая."


def delete_path(path: str):
    target = safe_path(path)

    if not target.exists():
        return f"Не найдено: {target}"

    _reject_symlink(target)
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

    # M2 (external audit 2026-09-03): both reads are bounded by the same
    # 10 MB guard as files.write. An unbounded read here turned the guarded
    # rollback into a free "load anything inside Projects into RAM" primitive
    # and the journal into unbounded memory growth.
    source_size = source.stat().st_size
    if source_size > MAX_FILE_BYTES:
        return f"Отклонено: снимок превышает лимит {MAX_FILE_BYTES} байт"
    if target.exists() and target.stat().st_size > MAX_FILE_BYTES:
        return f"Отклонено: текущий файл превышает лимит {MAX_FILE_BYTES} байт, откат невозможен"

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
    # M2: an empty journal entry means the file did NOT exist before the
    # rollback; deleting is only correct when it is still absent-content, and
    # a same-named empty file must round-trip back to empty, not vanish.
    if prior_bytes:
        target.write_bytes(prior_bytes)
    elif not target.exists():
        pass
    elif target.stat().st_size == 0:
        target.unlink()
    else:
        return (
            "Отклонено: текущий файл не пуст, а снимок утверждал, что файла не было — "
            "ручное разрешение конфликта требуется"
        )

    return f"Откат отменён: {target} восстановлен в предыдущее состояние"