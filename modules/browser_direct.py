def _strip_browser_prefix(user):
    text = str(user or "").strip()
    lower = text.lower()

    for prefix in ["browser", "браузер"]:
        if lower.startswith(prefix):
            return text[len(prefix):].strip(" :,-")

    return text


def _extract_after(text, markers):
    lower = text.lower()

    for marker in markers:
        index = lower.find(marker)

        if index != -1:
            return text[index + len(marker):].strip(" :,-")

    return ""


def browser_action_direct_plan(user):
    source = str(user or "").strip()
    lower_source = source.lower()
    platform_site_request = (
        any(marker in lower_source for marker in ["используй платформу", "tilda", "тильда", "wix", "webflow", "framer", "carrd"])
        and any(marker in lower_source for marker in ["сайт", "site"])
    )

    if not lower_source.startswith(("browser", "браузер")) and not platform_site_request:
        return None

    text = _strip_browser_prefix(source) if lower_source.startswith(("browser", "браузер")) else source
    lower = text.lower()

    if lower in ["observe", "наблюдай", "осмотри страницу"]:
        return {"tool": "browser", "action": "observe"}

    if lower in ["autopilot last report", "autopilot report", "last autopilot report"]:
        return {"tool": "browser", "action": "autopilot_last_report"}

    if lower in ["super last report", "super report", "last super report"]:
        return {"tool": "browser", "action": "super_last_report"}

    if lower.startswith(("super plan ", "operator plan ")):
        marker = "super plan " if lower.startswith("super plan ") else "operator plan "
        task = text[len(marker):].strip()
        return {"tool": "browser", "action": "super_plan", "task": task, "max_results": 3}

    if lower.startswith(("super run ", "do ", "operator run ")):
        for marker in ["super run ", "operator run ", "do "]:
            if lower.startswith(marker):
                task = text[len(marker):].strip()
                return {"tool": "browser", "action": "super_run", "task": task, "max_results": 3}

    if lower.startswith(("research ", "deep research ", "исследуй ", "изучи ")):
        for marker in ["deep research ", "research ", "исследуй ", "изучи "]:
            if lower.startswith(marker):
                task = text[len(marker):].strip()
                return {"tool": "browser", "action": "research", "task": task, "max_results": 3}

    if lower.startswith(("compare ", "сравни ")):
        marker = "compare " if lower.startswith("compare ") else "сравни "
        task = text[len(marker):].strip()
        return {"tool": "browser", "action": "compare_research", "task": task, "max_results": 3}

    if lower in ["page audit", "audit page", "аудит страницы", "проверь текущую страницу"]:
        return {"tool": "browser", "action": "page_audit", "task": "current page"}

    if lower in ["form map", "forms map", "form audit", "карта форм", "поля формы"]:
        return {"tool": "browser", "action": "form_map", "task": "current page"}

    if lower.startswith(("build site ", "site workflow ", "напиши сайт ", "создай сайт ", "сделай сайт ")):
        for marker in ["site workflow ", "build site ", "напиши сайт ", "создай сайт ", "сделай сайт "]:
            if lower.startswith(marker):
                task = text[len(marker):].strip()
                return {"tool": "browser", "action": "platform_site_workflow", "task": task}

    if platform_site_request:
        return {"tool": "browser", "action": "platform_site_workflow", "task": text}

    if lower.startswith("autopilot dry "):
        task = text[len("autopilot dry "):].strip()
        return {"tool": "browser", "action": "autopilot_dry", "task": task, "max_steps": 8}

    if lower.startswith("autopilot run "):
        task = text[len("autopilot run "):].strip()
        return {"tool": "browser", "action": "autopilot_run", "task": task, "max_steps": 8}

    if lower.startswith("plan "):
        task = text[len("plan "):].strip()
        return {"tool": "browser", "action": "plan", "task": task, "max_steps": 8}

    if lower.startswith("task "):
        task = text[len("task "):].strip()
        return {"tool": "browser", "action": "browser_task", "task": task, "max_steps": 8}

    if lower == "workflow python search":
        return {
            "tool": "browser",
            "action": "browser_workflow",
            "steps": [
                {"action": "search", "args": {"query": "Python official website"}},
                {"action": "open_first"},
                {"action": "summarize"},
                {"action": "extract_links"},
                {"action": "extract_inputs"},
                {"action": "screenshot"}
            ],
            "title": "python search workflow"
        }

    if lower == "workflow current page":
        return {
            "tool": "browser",
            "action": "browser_workflow",
            "steps": [
                {"action": "summarize"},
                {"action": "extract_links"},
                {"action": "extract_inputs"},
                {"action": "screenshot"}
            ],
            "title": "current page workflow"
        }

    if lower in ["screenshot", "скрин", "скриншот"]:
        return {"tool": "browser", "action": "screenshot"}

    if lower in ["links", "ссылки"]:
        return {"tool": "browser", "action": "extract_links"}

    if lower in ["inputs", "поля", "формы"]:
        return {"tool": "browser", "action": "extract_inputs"}

    if lower in ["summarize", "summary", "резюме", "кратко", "summary page"]:
        return {"tool": "browser", "action": "summarize"}

    if lower in ["tabs", "вкладки"]:
        return {"tool": "browser", "action": "list_tabs"}

    if lower in ["close tab", "закрой вкладку", "close current tab"]:
        return {"tool": "browser", "action": "close_tab"}

    if lower in ["action status", "action статус", "actions status"]:
        return {"tool": "browser", "action": "action_status"}

    if lower.startswith(("find text", "найди текст")):
        value = _extract_after(text, ["find text", "найди текст"])
        return {"tool": "browser", "action": "find_text", "text": value}

    if lower.startswith(("click selector", "selector click")):
        value = _extract_after(text, ["click selector", "selector click"])
        return {"tool": "browser", "action": "click_selector", "selector": value}

    if lower.startswith(("click ", "клик ")):
        value = _extract_after(text, ["click", "клик"])
        return {"tool": "browser", "action": "click_text", "text": value}

    if lower.startswith(("fill selector", "selector fill")):
        value = _extract_after(text, ["fill selector", "selector fill"])

        if "=" in value:
            selector, fill_value = value.split("=", 1)
        else:
            selector, fill_value = value, ""

        return {
            "tool": "browser",
            "action": "fill_selector",
            "selector": selector.strip(),
            "value": fill_value.strip(),
        }

    if lower.startswith(("fill ", "введи ")):
        value = _extract_after(text, ["fill", "введи"])

        if "=" in value:
            label, fill_value = value.split("=", 1)
        else:
            label, fill_value = value, ""

        return {
            "tool": "browser",
            "action": "fill_label",
            "label": label.strip(),
            "value": fill_value.strip(),
        }

    if lower.startswith(("press ", "нажми ")):
        key = _extract_after(text, ["press", "нажми"]) or "Enter"
        return {"tool": "browser", "action": "press_key", "key": key.strip()}

    if lower.startswith(("wait ", "жди ", "подожди ")):
        raw = _extract_after(text, ["wait", "жди", "подожди"])
        digits = "".join(ch for ch in raw if ch.isdigit())
        return {"tool": "browser", "action": "wait", "ms": int(digits or "1000")}

    if lower.startswith(("new tab", "новая вкладка")):
        url = _extract_after(text, ["new tab", "новая вкладка"])
        return {"tool": "browser", "action": "open_new_tab", "url": url}

    if lower.startswith(("switch tab", "переключи вкладку")):
        raw = _extract_after(text, ["switch tab", "переключи вкладку"])
        digits = "".join(ch for ch in raw if ch.isdigit())
        return {"tool": "browser", "action": "switch_tab", "index": int(digits or "0")}

    return None
