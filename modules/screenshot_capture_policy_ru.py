from pathlib import Path
from typing import Dict, Any
import time

# Configuration
SCREENSHOT_DIR = Path("Projects/Reports/desktop_observer/screenshots")
MAX_STORAGE_GB = 30.0
ENABLE_BY_DEFAULT = False


def get_screenshot_storage_status() -> Dict[str, Any]:
    """Получает статус хранилища скриншотов с подробной информацией."""
    status: Dict[str, Any] = {
        "mode": "screenshot_capture_policy",
        "version": "v6.65b",
        "enabled_by_default": ENABLE_BY_DEFAULT,
        "config_status": "dry_run_only",
        "dangerous_size_detected": False,
        "newest_screenshot_timestamp": None,
        "warning_message": None,
    }

    # Check if directory exists and is accessible
    if not SCREENSHOT_DIR.exists():
        status["directory_exists"] = False
        status["warning_message"] = (
            "Папка для скриншотов не существует. "
            "Сценарий локализации: `mkdir -p Projects/Reports/desktop_observer/screenshots`"
        )
        return status

    status["directory_exists"] = True

    # Get file list and information
    try:
        bmp_files = list(SCREENSHOT_DIR.glob("*.bmp"))
        png_files = list(SCREENSHOT_DIR.glob("*.png"))

        status["bmp_file_count"] = len(bmp_files)
        status["png_file_count"] = len(png_files)
        status["total_file_count"] = len(bmp_files) + len(png_files)

        # Calculate size
        total_size_bytes = 0
        for f in bmp_files + png_files:
            total_size_bytes += f.stat().st_size

        status["total_size_bytes"] = total_size_bytes
        status["total_size_mb"] = round(total_size_bytes / (1024 * 1024), 2)
        status["total_size_gb"] = round(total_size_bytes / (1024 * 1024 * 1024), 2)

        # Detect dangerous size
        status["dangerous_size_detected"] = status["total_size_gb"] > MAX_STORAGE_GB

        # Get newest timestamp
        if bmp_files:
            newest_bmp = max(bmp_files, key=lambda f: f.stat().st_mtime)
            newest_timestamp = newest_bmp.stat().st_mtime
            status["newest_screenshot_timestamp"] = newest_timestamp

            # Get human-readable timestamp
            status["newest_screenshot_age_hours"] = round(
                (time.time() - newest_timestamp) / 3600, 1
            )

        if png_files:
            newest_png = max(png_files, key=lambda f: f.stat().st_mtime)
            newest_timestamp = newest_png.stat().st_mtime
            status["newest_screenshot_timestamp"] = newest_timestamp
            status["newest_screenshot_age_hours"] = round(
                (time.time() - newest_timestamp) / 3600, 1
            )

        # Determine warning message
        if status["dangerous_size_detected"]:
            status["warning_message"] = (
                f"Опасное накопление скриншотов: {status['total_size_gb']} ГБ > {MAX_STORAGE_GB} ГБ. "
                "Капсуляция отключена, чтобы предотвратить исчерпание дискового пространства."
            )
        elif status["total_file_count"] > 1000:
            status["warning_message"] = (
                f"Обширная коллекция скриншотов: {status['total_file_count']} файлов, {status['total_size_gb']} ГБ. "
                "Рекомендуется очистка старых скриншотов."
            )
        elif not ENABLE_BY_DEFAULT:
            status["warning_message"] = (
                "Капсуляция скриншотов отключена по умолчанию. "
                "Для разрешенного захвата выполните: `config enable screenshot capture`"
            )

    except Exception as exc:
        status["directory_error"] = str(exc)
        status["warning_message"] = f"Ошибка при проверке скриншотов: {exc}"

    return status


def is_screenshot_capture_enabled() -> bool:
    """Проверяет, разрешена ли капсуляция скриншотов."""
    return ENABLE_BY_DEFAULT


def should_allow_screenshot_write() -> Dict[str, Any]:
    """
    Проверяет, можно ли писать скриншоты.

    Returns:
        Dict with keys:
        - allow: bool - whether screenshot can be written
        - reason: str - explanation
        - mode: str - "enabled", "dry_run", "blocked", "dangerous", "error"
    """
    if not ENABLE_BY_DEFAULT:
        return {
            "allow": False,
            "reason": "Капсуляция скриншотов отключена по умолчанию.",
            "mode": "blocked",
            "config_action": "set ENABLE_BY_DEFAULT = True to allow",
        }

    # If default is enabled, but directory is dangerous, block
    try:
        if SCREENSHOT_DIR.exists():
            bmp_files = list(SCREENSHOT_DIR.glob("*.bmp"))
            png_files = list(SCREENSHOT_DIR.glob("*.png"))

            total_files = len(bmp_files) + len(png_files)
            total_size_gb = sum(f.stat().st_size for f in bmp_files + png_files) / (1024 * 1024 * 1024)

            if total_size_gb > MAX_STORAGE_GB:
                return {
                    "allow": False,
                    "reason": f"Опасный размер хранилища: {total_size_gb:.2f} ГБ > {MAX_STORAGE_GB} ГБ.",
                    "mode": "dangerous",
                    "size_gb": round(total_size_gb, 2),
                    "max_gb": MAX_STORAGE_GB,
                }

        return {
            "allow": True,
            "reason": "Капсуляция скриншотов разрешена (режим dry-run/симуляции).",
            "mode": "dry_run",
        }

    except Exception as exc:
        return {
            "allow": False,
            "reason": f"Ошибка при проверке хранилища скриншотов: {exc}",
            "mode": "error",
            "error": str(exc),
        }


def status() -> Dict[str, Any]:
    """Возвращает статус модуля политики капсуляции скриншотов."""
    return {
        "ok": True,
        "mode": "screenshot_capture_policy_status",
        "version": "v6.65b",
        "enabled": is_screenshot_capture_enabled(),
        "allow_write": should_allow_screenshot_write(),
    }


def report() -> Dict[str, Any]:
    """Возвращает отчёт о состоянии хранилища скриншотов."""
    return get_screenshot_storage_status()


def dispatch(command: str) -> Dict[str, Any]:
    """Обработчик команд для маршрутизации."""
    normalized = str(command or "").strip().lower().replace("ё", "е")

    if normalized in {
        "статус скриншотов",
        "status screenshots",
        "screenshot storage status",
        "скриншоты статус",
        "screenshot status",
    }:
        return {
            "mode": "command",
            "route": "modules.screenshot_capture_policy_ru",
            "plan": {"tool": "modules.screenshot_capture_policy_ru", "action": "dispatch"},
            "result": get_screenshot_storage_status(),
        }

    return {
        "ok": False,
        "mode": "screenshot_capture_policy",
        "version": "v6.65b",
        "message": f"Неизвестная команда: {command}",
    }


def is_screenshot_capture_policy_command(command: str) -> bool:
    """Проверяет, является ли команда командой для работы с политикой капсуляции скриншотов."""
    if not isinstance(command, str):
        return False

    normalized = command.strip().lower().replace("ё", "е")
    return normalized in {
        "статус скриншотов",
        "status screenshots",
        "screenshot storage status",
        "скриншоты статус",
        "screenshot status",
    }


def enable_capture() -> Dict[str, Any]:
    """Включает капсуляцию скриншотов (должно выполняться с осторожностью)."""
    global ENABLE_BY_DEFAULT
    previous = ENABLE_BY_DEFAULT
    try:
        ENABLE_BY_DEFAULT = True

        # Проверить дисковое пространство перед включением
        if SCREENSHOT_DIR.exists():
            total_size_gb = sum(f.stat().st_size for f in SCREENSHOT_DIR.glob("*.bmp")) / (1024 * 1024 * 1024)

            if total_size_gb > MAX_STORAGE_GB:
                ENABLE_BY_DEFAULT = previous

                return {
                    "ok": False,
                    "mode": "screenshot_capture_policy",
                    "version": "v6.65b",
                    "message": (
                        f"Невозможно включить капсуляцию: опасный размер хранилища {total_size_gb:.2f} ГБ. "
                        "Для очистки выполните manual cleanup или введите конфигурацию для сброса."
                    ),
                    "action": "block",
                    "reason": "dangerous_storage_size",
                    "size_gb": round(total_size_gb, 2),
                    "max_gb": MAX_STORAGE_GB,
                }

        return {
            "ok": True,
            "mode": "screenshot_capture_policy",
            "version": "v6.65b",
            "message": "Капсуляция скриншотов включена.",
            "previous_status": "disabled",
            "current_status": "enabled",
        }
    except Exception as exc:
        ENABLE_BY_DEFAULT = previous
        return {
            "ok": False,
            "mode": "screenshot_capture_policy",
            "version": "v6.65b",
            "message": f"Ошибка при включении капсуляции скриншотов: {str(exc)}",
            "exception": str(exc),
        }
