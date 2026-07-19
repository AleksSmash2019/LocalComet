import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from modules.project_paths import get_project_root

from core.state import set_value, get_value
from modules import gpt_browser_bridge


ROOT_DIR = get_project_root()
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports"
RESPONSE_GLOB = "response*.json"


def _short(text, limit: int = 1800):
    value = str(text or "")

    if len(value) <= limit:
        return value

    return value[:limit] + "\n...[обрезано]"


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _cycle_id():
    return "auto_" + _stamp()


def _new_report_path():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR / f"true_auto_relay_{_stamp()}.md"


def _new_screenshot_path():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR / f"true_auto_relay_error_{_stamp()}.png"


def _downloads_dir():
    downloads_dir = getattr(gpt_browser_bridge, "DOWNLOADS_DIR")
    downloads_dir.mkdir(parents=True, exist_ok=True)
    return downloads_dir


def _archive_old_downloads(cycle_id: str):
    downloads_dir = _downloads_dir()
    archive_dir = downloads_dir / "Archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    moved = []

    for path in sorted(downloads_dir.glob(RESPONSE_GLOB)):
        if not path.is_file():
            continue

        target = archive_dir / f"{cycle_id}_{path.stat().st_mtime_ns}_{path.name}"

        try:
            shutil.move(str(path), str(target))
            moved.append(f"{path.name} -> {target.name}")
        except Exception as e:
            moved.append(f"НЕ ПЕРЕНЕСЕН: {path.name} -> {e}")

    set_value("last_true_auto_archived_downloads", "\n".join(moved))
    return moved


def _save_report(lines, report_path):
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(str(line) for line in lines), encoding="utf-8")
    set_value("last_true_auto_relay_report", str(report_path))
    return report_path


def _save_screenshot():
    screenshot_path = _new_screenshot_path()

    try:
        page = gpt_browser_bridge._get_page()
        page.screenshot(path=str(screenshot_path), full_page=True)
        set_value("last_true_auto_relay_screenshot", str(screenshot_path))
        return str(screenshot_path)
    except Exception as e:
        set_value("last_true_auto_relay_screenshot_error", str(e))
        return ""


def _stop(lines, report_path, message, make_screenshot=True):
    set_value("last_true_auto_patch_status", "stopped")
    lines.append("")
    lines.append(message)

    if make_screenshot:
        screenshot = _save_screenshot()

        if screenshot:
            lines.append(f"Screenshot: {screenshot}")
        else:
            lines.append("Screenshot: не удалось сделать screenshot текущей страницы.")

    saved = _save_report(lines, report_path)
    lines.append(f"Log: {saved}")
    return "\n".join(lines)


def _patch_is_valid(data):
    return (
        isinstance(data, dict)
        and isinstance(data.get("summary"), str)
        and isinstance(data.get("operations"), list)
        and len(data.get("operations", [])) > 0
        and isinstance(data.get("tests"), list)
    )


def _patch_cycle_id(data):
    if not isinstance(data, dict):
        return ""

    meta = data.get("meta")

    if isinstance(meta, dict):
        return str(meta.get("cycle_id", "") or "").strip()

    return ""


def _read_patch(path: Path, expected_cycle_id: str = ""):
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    data = json.loads(raw)

    if not _patch_is_valid(data):
        raise ValueError("JSON есть, но это не рабочий patch: нужны summary, operations > 0, tests.")

    expected_cycle_id = str(expected_cycle_id or "").strip()

    if expected_cycle_id:
        actual_cycle_id = _patch_cycle_id(data)

        if actual_cycle_id != expected_cycle_id:
            raise ValueError(
                "response freshness guard: meta.cycle_id не совпадает. "
                f"expected={expected_cycle_id}; actual={actual_cycle_id or 'нет'}"
            )

    return data


def _latest_valid_response_file(since_epoch: float = 0, expected_cycle_id: str = ""):
    downloads_dir = _downloads_dir()

    candidates = sorted(
        [path for path in downloads_dir.glob(RESPONSE_GLOB) if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    for path in candidates:
        if since_epoch and path.stat().st_mtime < since_epoch:
            continue

        try:
            _read_patch(path, expected_cycle_id=expected_cycle_id)
            return path
        except Exception as e:
            set_value("last_true_auto_rejected_response", f"{path}: {e}")
            continue

    return None


def _safe_filename(name: str):
    value = str(name or "").strip().replace("\\", "_").replace("/", "_")

    if not value:
        value = f"response_artifact_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    if not value.lower().endswith(".json"):
        value += ".json"

    if not value.lower().startswith("response"):
        value = "response_" + value

    return value


def _assistant_scopes(page):
    scopes = []

    for selector in [
        "[data-message-author-role='assistant']",
        "article",
    ]:
        try:
            locator = page.locator(selector)
            count = locator.count()

            if count:
                scopes.append(locator.nth(count - 1))
        except Exception:
            continue

    scopes.append(page)
    return scopes


def _try_download_from_page(page, timeout_ms: int = 12000, expected_cycle_id: str = ""):
    downloads_dir = _downloads_dir()

    selectors = [
        "a[download]",
        "a[href*='download']",
        "a[href*='response']",
        "button[data-testid*='download']",
        "[data-testid*='download']",
        "button:has-text('Download')",
        "button:has-text('Скачать')",
        "a:has-text('response.json')",
        "button:has-text('response.json')",
        "text=response.json",
    ]

    errors = []

    for scope in _assistant_scopes(page):
        for selector in selectors:
            try:
                locator = scope.locator(selector)
                count = min(locator.count(), 8)

                for index in range(count):
                    item = locator.nth(index)

                    try:
                        with page.expect_download(timeout=timeout_ms) as download_info:
                            item.click(timeout=5000)

                        download = download_info.value
                        suggested = _safe_filename(download.suggested_filename)
                        target = downloads_dir / suggested
                        download.save_as(str(target))

                        try:
                            data = _read_patch(target, expected_cycle_id=expected_cycle_id)
                        except Exception as e:
                            errors.append(f"{selector}[{index}]: скачан невалидный/устаревший файл {target.name}: {e}")
                            continue

                        set_value("last_true_auto_downloaded_response", str(target))
                        set_value("last_true_auto_downloaded_cycle_id", _patch_cycle_id(data))
                        return target

                    except Exception as e:
                        errors.append(f"{selector}[{index}]: {e}")
                        continue

            except Exception as e:
                errors.append(f"{selector}: {e}")
                continue

    set_value("last_true_auto_download_errors", "\n".join(errors[-20:]))
    return None


def download_latest_response_artifact(timeout_sec: int = 900, expected_cycle_id: str = ""):
    """Try to download or locate the newest valid response*.json artifact from ChatGPT.

    Returns a human-readable result with OK/STOP prefix and saves the found path in state.
    """
    started = time.time()
    timeout_sec = max(10, int(timeout_sec or 900))
    expected_cycle_id = str(expected_cycle_id or "").strip()

    try:
        downloads_dir = _downloads_dir()

        before_existing = _latest_valid_response_file(
            since_epoch=started - 2,
            expected_cycle_id=expected_cycle_id,
        )

        if before_existing:
            data = _read_patch(before_existing, expected_cycle_id=expected_cycle_id)
            actual_cycle_id = _patch_cycle_id(data)
            set_value("last_true_auto_downloaded_response", str(before_existing))
            return (
                "OK: найден свежий response*.json в Downloads.\n"
                f"Файл: {before_existing}\n"
                f"expected cycle_id: {expected_cycle_id or 'не задан'}\n"
                f"actual cycle_id: {actual_cycle_id or 'нет'}"
            )

        page = gpt_browser_bridge._get_page()

        clicked = _try_download_from_page(
            page,
            expected_cycle_id=expected_cycle_id,
        )

        if clicked:
            data = _read_patch(clicked, expected_cycle_id=expected_cycle_id)
            actual_cycle_id = _patch_cycle_id(data)
            return (
                "OK: response artifact скачан из ChatGPT.\n"
                f"Файл: {clicked}\n"
                f"expected cycle_id: {expected_cycle_id or 'не задан'}\n"
                f"actual cycle_id: {actual_cycle_id or 'нет'}"
            )

        while time.time() - started < timeout_sec:
            found = _latest_valid_response_file(
                since_epoch=started - 2,
                expected_cycle_id=expected_cycle_id,
            )

            if found:
                data = _read_patch(found, expected_cycle_id=expected_cycle_id)
                actual_cycle_id = _patch_cycle_id(data)
                set_value("last_true_auto_downloaded_response", str(found))
                return (
                    "OK: найден скачанный response*.json.\n"
                    f"Файл: {found}\n"
                    f"expected cycle_id: {expected_cycle_id or 'не задан'}\n"
                    f"actual cycle_id: {actual_cycle_id or 'нет'}"
                )

            time.sleep(2)

        return (
            "STOP: не удалось скачать или найти свежий response*.json с нужным cycle_id.\n"
            f"Папка Downloads: {downloads_dir}\n"
            f"expected cycle_id: {expected_cycle_id or 'не задан'}\n"
            "Дальше: проверь, создал ли ChatGPT новый файл именно для текущего auto-cycle."
        )

    except Exception as e:
        set_value("last_true_auto_download_error", str(e))
        return f"STOP: ошибка download_latest_response_artifact.\nОшибка: {e}"


def _extract_ok_path(result: str):
    text = str(result or "")

    if not text.lstrip().startswith("OK:"):
        return None

    for line in text.splitlines():
        clean = line.strip()

        if clean.lower().startswith("файл:"):
            return Path(clean.split(":", 1)[1].strip())

    return None


def import_response_file(path: Path, expected_cycle_id: str = ""):
    path = Path(path)

    if not path.exists() or not path.is_file():
        return f"STOP: response file не найден:\n{path}"

    try:
        data = _read_patch(path, expected_cycle_id=expected_cycle_id)
    except Exception as e:
        return f"STOP: response file не прошел JSON patch/freshness проверку.\nФайл: {path}\nОшибка: {e}"

    response_path = getattr(gpt_browser_bridge, "RESPONSE_PATH")
    response_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, response_path)

    actual_cycle_id = _patch_cycle_id(data)
    set_value("last_true_auto_imported_response", str(response_path))
    set_value("last_true_auto_imported_cycle_id", actual_cycle_id)

    return (
        "OK: response импортирован в Relay.\n"
        f"Источник: {path}\n"
        f"Цель: {response_path}\n"
        f"Summary: {data.get('summary')}\n"
        f"Операций: {len(data.get('operations', []))}\n"
        f"expected cycle_id: {expected_cycle_id or 'не задан'}\n"
        f"actual cycle_id: {actual_cycle_id or 'нет'}"
    )


def _ok(text):
    return str(text or "").lstrip().startswith("OK:")


def _generic_ok(text):
    lower = str(text or "").lower()

    bad = [
        "stop:",
        "ошибка",
        "не удалось",
        "traceback",
        "failed",
        "unknown",
        "неизвестное действие",
    ]

    return bool(str(text or "").strip()) and not any(marker in lower for marker in bad)


def _validate_ok(text):
    lower = str(text or "").lower()

    bad = [
        "stop:",
        "ошибка",
        "не удалось",
        "отклонен",
        "не пройд",
        "пустой",
        "применять нечего",
        "нет списка operations",
        "не найден",
    ]

    return (
        ("✅" in str(text) or "проверка пройдена" in lower)
        and not any(marker in lower for marker in bad)
    )


def _apply_ok(text):
    lower = str(text or "").lower()

    bad = [
        "patch не применен",
        "не применен",
        "ошибка",
        "не удалось",
        "stop:",
        "failed",
    ]

    return (
        ("patch успешно применен" in lower or "успешно применен" in lower)
        and not any(marker in lower for marker in bad)
    )


def _run_step_with_retry(lines, report_path, step_no, total_steps, title, func, checker=_generic_ok, retries=2):
    attempts = max(1, int(retries or 0) + 1)
    last_result = ""

    for attempt in range(1, attempts + 1):
        lines.append("")
        lines.append(f"STEP {step_no}/{total_steps} TRY {attempt}/{attempts}: {title}")

        try:
            result = func()
        except Exception as e:
            result = f"STOP: exception in {title}: {e}"

        last_result = str(result)
        lines.append(last_result)

        if checker(last_result):
            if attempt > 1:
                lines.append(f"STEP {step_no}/{total_steps} RECOVERED: {title}")
            lines.append(f"STEP {step_no}/{total_steps} OK: {title}")
            _save_report(lines, report_path)
            return True, last_result

        if attempt < attempts:
            lines.append(f"STEP {step_no}/{total_steps} retry через 2 сек: {title}")
            _save_report(lines, report_path)
            time.sleep(2)

    lines.append(f"STEP {step_no}/{total_steps} STOP: {title}")
    _save_report(lines, report_path)
    return False, last_result


def _download_and_import(expected_cycle_id: str = ""):
    from agents import gpt_browser_agent

    download_result = download_latest_response_artifact(
        timeout_sec=45,
        expected_cycle_id=expected_cycle_id,
    )

    if _ok(download_result):
        path = _extract_ok_path(download_result)

        if path:
            import_result = import_response_file(path, expected_cycle_id=expected_cycle_id)

            if _ok(import_result):
                return download_result + "\n\n" + import_result

            return download_result + "\n\n" + import_result

    save_result = gpt_browser_agent.handle("save_response", {})
    save_lower = str(save_result).lower()

    if "response.json сохранен" in save_lower or "response.json импортирован" in save_lower:
        response_path = getattr(gpt_browser_bridge, "RESPONSE_PATH")

        try:
            data = _read_patch(response_path, expected_cycle_id=expected_cycle_id)
            actual_cycle_id = _patch_cycle_id(data)
            return (
                "OK: fallback save_response сработал и прошел freshness guard.\n"
                + str(save_result)
                + f"\nexpected cycle_id: {expected_cycle_id or 'не задан'}"
                + f"\nactual cycle_id: {actual_cycle_id or 'нет'}"
            )
        except Exception as e:
            return (
                str(save_result)
                + "\n\nSTOP: fallback save_response получил response.json, но freshness guard не прошел.\n"
                + f"expected cycle_id: {expected_cycle_id or 'не задан'}\n"
                + f"Ошибка: {e}"
            )

    return (
        str(download_result)
        + "\n\n--- FALLBACK SAVE_RESPONSE ---\n"
        + str(save_result)
        + "\n\nSTOP: не удалось получить рабочий свежий response.json."
    )


def true_auto_relay_cycle(goal: str = "", timeout_sec: int = 900):
    """Full automatic safe Relay cycle with retries, report and screenshot on STOP."""
    from agents import automation_agent
    from agents import chatgpt_relay_agent
    from agents import gpt_browser_agent

    goal = str(goal or "").strip()
    timeout_sec = max(60, int(timeout_sec or 900))
    total_steps = 10
    report_path = _new_report_path()
    cycle_id = _cycle_id()

    lines = [
        "# TRUE AUTO RELAY CYCLE",
        "",
        f"- started: {datetime.now().isoformat(timespec='seconds')}",
        f"- timeout_sec: {timeout_sec}",
        f"- cycle_id: {cycle_id}",
        f"- goal: {goal}",
        "",
    ]

    set_value("last_true_auto_cycle_id", cycle_id)
    set_value("last_true_auto_relay_report", str(report_path))
    set_value("last_true_auto_relay_screenshot", "")
    set_value("last_true_auto_patch_status", "running")

    if not goal:
        return _stop(
            lines,
            report_path,
            "STEP 1/10 STOP: dev task пустой. Введи задачу в поле Dev task.",
            make_screenshot=False,
        )

    set_value("last_true_auto_relay_goal", goal)
    _save_report(lines, report_path)

    archived = _archive_old_downloads(cycle_id)
    lines.append("Response Freshness Guard: включен.")
    lines.append(f"Expected cycle_id: {cycle_id}")
    lines.append(
        "Archived old Downloads response*.json: "
        + (str(len(archived)) if archived else "0")
    )
    _save_report(lines, report_path)

    try:
        gpt_browser_bridge.reset_bridge_state("true_auto_relay_start")
        lines.append("GPT Browser Bridge reset before auto-cycle: OK")
        _save_report(lines, report_path)
    except Exception as e:
        lines.append(f"GPT Browser Bridge reset before auto-cycle: failed but ignored: {e}")
        _save_report(lines, report_path)

    ok, dev_result = _run_step_with_retry(
        lines,
        report_path,
        1,
        total_steps,
        "создать request.md через dev task",
        lambda: automation_agent.handle("dev_task", {"goal": goal}),
        checker=lambda r: (
            ("request.md" in str(r) or "Relay-запрос создан" in str(r))
            and _generic_ok(r)
        ),
        retries=0,
    )

    if not ok:
        return _stop(lines, report_path, "STEP 1/10 STOP: dev task не создал request.md.")

    retry_steps = [
        (2, "открыть ChatGPT", lambda: gpt_browser_agent.handle("open", {})),
        (3, "вставить request.md", lambda: gpt_browser_agent.handle("paste_request", {})),
        (4, "отправить request", lambda: gpt_browser_agent.handle("send", {})),
        (5, "дождаться ответа ChatGPT", lambda: gpt_browser_agent.handle("wait", {"timeout_sec": timeout_sec})),
        (6, f"скачать/импортировать response*.json для cycle_id {cycle_id}", lambda: _download_and_import(cycle_id)),
    ]

    for step_no, title, func in retry_steps:
        ok, result = _run_step_with_retry(
            lines,
            report_path,
            step_no,
            total_steps,
            title,
            func,
            checker=_generic_ok if step_no != 6 else _ok,
            retries=2,
        )

        if not ok:
            return _stop(lines, report_path, f"STEP {step_no}/{total_steps} STOP: {title}. Patch не применен.")

    ok, validate_result = _run_step_with_retry(
        lines,
        report_path,
        7,
        total_steps,
        "relay validate",
        lambda: chatgpt_relay_agent.handle("validate_response", {}),
        checker=_validate_ok,
        retries=0,
    )

    if not ok:
        return _stop(
            lines,
            report_path,
            "STEP 7/10 STOP: relay validate не прошел. GPT Browser не закрыт, patch не применен.",
        )

    ok, close_result = _run_step_with_retry(
        lines,
        report_path,
        8,
        total_steps,
        "закрыть GPT Browser",
        lambda: gpt_browser_agent.handle("close", {}),
        checker=_generic_ok,
        retries=0,
    )

    if not ok:
        return _stop(lines, report_path, "STEP 8/10 STOP: GPT Browser не закрыт. Patch не применен.")

    ok, apply_result = _run_step_with_retry(
        lines,
        report_path,
        9,
        total_steps,
        "применить response patch",
        lambda: chatgpt_relay_agent.handle("apply_response", {}),
        checker=_apply_ok,
        retries=0,
    )

    if not ok:
        return _stop(lines, report_path, "STEP 9/10 STOP: apply не прошел. after patch не запущен.")

    ok, after_result = _run_step_with_retry(
        lines,
        report_path,
        10,
        total_steps,
        "after patch",
        lambda: automation_agent.handle("after_patch", {}),
        checker=_generic_ok,
        retries=0,
    )

    if not ok:
        return _stop(lines, report_path, "STEP 10/10 STOP: after patch завершился ошибкой.")

    lines.append("")
    lines.append("OK: TRUE AUTO RELAY CYCLE завершен.")
    lines.append(f"Log: {report_path}")

    _save_report(lines, report_path)
    set_value("last_true_auto_relay_result", _short("\n".join(lines), 4000))

    return "\n".join(lines)
