from pathlib import Path
from modules.project_paths import get_project_root
from typing import Dict, Any

ROOT_DIR = get_project_root()


def get_project_root_indicators() -> Dict[str, Any]:
    """Проверяет основные индикаторы корня проекта LocalAgent."""
    indicators = {
        "localcomet_control_panel_exists": False,
        "modules_directory_exists": False,
        "agents_md_exists": False,
    }
    
    try:
        indicators["localcomet_control_panel_exists"] = (
            ROOT_DIR / "LocalComet_Control_Panel.py"
        ).exists()
    except Exception:
        pass
    
    try:
        indicators["modules_directory_exists"] = (
            ROOT_DIR / "modules"
        ).exists()
    except Exception:
        pass
    
    try:
        indicators["agents_md_exists"] = (
            ROOT_DIR / "AGENTS.md"
        ).exists()
    except Exception:
        pass
    
    return indicators


def check_working_directory() -> Dict[str, Any]:
    """Проверяет, запущена ли команда из корня проекта LocalAgent."""
    try:
        current_path = Path.cwd()
        indicators = get_project_root_indicators()
        
        if indicators["localcomet_control_panel_exists"] and \
           indicators["modules_directory_exists"] and \
           indicators["agents_md_exists"]:
            return {
                "ok": True,
                "mode": "working_directory_guard",
                "version": "v6.65b",
                "message": "Команда запущена из корня проекта LocalAgent.",
                "current_directory": str(current_path),
                "project_root": str(ROOT_DIR),
                "indicators": indicators,
            }
        else:
            return {
                "ok": False,
                "mode": "working_directory_guard",
                "version": "v6.65b",
                "message": (
                    "Команда запущена не из корня проекта LocalAgent. "
                    f'Выполни: cd "{ROOT_DIR}"'
                ),
                "current_directory": str(current_path),
                "project_root": str(ROOT_DIR),
                "indicators": indicators,
                "error": "wrong_directory",
                "suggestion": f'cd "{ROOT_DIR}"',
            }
    except Exception as exc:
        return {
            "ok": False,
            "mode": "working_directory_guard",
            "version": "v6.65b",
            "message": f"Ошибка при проверке рабочей директории: {str(exc)}",
            "current_directory": str(Path.cwd()),
            "project_root": str(ROOT_DIR),
            "indicators": {},
            "error": "exception",
            "exception": str(exc),
        }


def status() -> Dict[str, Any]:
    """Возвращает статус модуля."""
    return get_status()


def report() -> Dict[str, Any]:
    """Возвращает отчёт о проверке рабочей директории."""
    return check_working_directory()


def dispatch(command: str) -> Dict[str, Any]:
    """Обработчик команд для маршрутизации."""
    normalized = str(command or "").strip().lower().replace("ё", "е")
    
    if normalized in {
        "проверь рабочую папку",
        "проверь рабочую папу",
        "working directory guard",
        "проверь рабочую директорию",
        "working dir guard",
    }:
        return {
            "mode": "command",
            "route": "modules.working_directory_guard_ru",
            "plan": {"tool": "modules.working_directory_guard_ru", "action": "dispatch"},
            "result": check_working_directory(),
        }
    
    return {
        "ok": False,
        "mode": "working_directory_guard",
        "version": "v6.65b",
        "message": f"Неизвестная команда: {command}",
    }


def is_working_directory_guard_command(command: str) -> bool:
    """Проверяет, является ли команда командой проверки рабочей директории."""
    if not isinstance(command, str):
        return False
    
    normalized = command.strip().lower().replace("ё", "е")
    return normalized in {
        "проверь рабочую папку",
        "проверь рабочую папу",
        "working directory guard",
        "проверь рабочую директорию",
        "working dir guard",
    }


def get_status() -> Dict[str, Any]:
    """Возвращает статус модуля."""
    return {
        "module": "working_directory_guard_ru",
        "version": "v6.65b",
        "status": "ready",
        "commands": [
            "проверь рабочую папу",
            "working directory guard",
            "проверь рабочую директорию",
            "working dir guard",
        ],
        "description": "Гарантирует, что команды LocalComet запускаются из корня проекта.",
    }
