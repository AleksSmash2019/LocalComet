import json
from json_repair import repair_json
from core.llm import ask_llm, is_llm_offline_error, format_llm_offline_message
from modules.browser_direct import browser_action_direct_plan
from modules.natural_command_intents import natural_command_plan


SYSTEMS = {
    "system": """
You are LocalComet System Planner.
Return ONLY valid JSON.

Available actions:
{"tool":"system","action":"help"}
{"tool":"system","action":"status"}
{"tool":"system","action":"memory"}
{"tool":"system","action":"recent"}
{"tool":"system","action":"model"}
{"tool":"system","action":"health"}
{"tool":"system","action":"health_report"}
{"tool":"system","action":"regression_suite"}
{"tool":"system","action":"regression_report"}
{"tool":"system","action":"auto_verify"}
{"tool":"system","action":"auto_verify_full"}

Rules:
- If user asks what LocalComet can do, use help.
- If user asks status, use status.
- If user asks memory, use memory.
- If user asks recent/last actions, use recent.
- If user asks current model, use model.
- If user asks project health, use health.
- If user asks project health report, use health_report.
- If user asks regression suite/check, use regression_suite.
- If user asks regression report, use regression_report.
- If user asks auto verify, verify quick, or check all, use auto_verify.
- If user asks auto verify full, verify full, or post patch verify, use auto_verify_full.
- Do not explain.
- Do not use markdown.
- Return JSON only.

Examples:
User: что ты умеешь
{"tool":"system","action":"help"}

User: статус
{"tool":"system","action":"status"}

User: память
{"tool":"system","action":"memory"}

User: последние действия
{"tool":"system","action":"recent"}

User: какая модель
{"tool":"system","action":"model"}

User: health
{"tool":"system","action":"health"}

User: health report
{"tool":"system","action":"health_report"}

User: regression suite
{"tool":"system","action":"regression_suite"}

User: regression report
{"tool":"system","action":"regression_report"}

User: auto verify
{"tool":"system","action":"auto_verify"}

User: verify full
{"tool":"system","action":"auto_verify_full"}
""",

    "windows": """
You are LocalComet Windows Planner.
Return ONLY valid JSON.

Available actions:
{"tool":"windows","action":"open_app","app":"calc"}
{"tool":"windows","action":"open_app","app":"notepad"}
{"tool":"windows","action":"type_text","text":"Hello"}

Rules:
- If user asks to open an app, use open_app.
- If user asks to write/type/enter/print text, use type_text.
- If user asks to open an app AND write/type text, return {"actions":[...]}.
- For Russian "блокнот", use app "notepad".
- For Russian "калькулятор", use app "calc".
- For Russian "напиши", "напечатай", "введи", "набери", "вставь", use type_text.
- Preserve the user's text language.
- Do not translate Russian text to English.
- If user says "напиши привет", text must be "привет".
- If user says "напиши привет мир", text must be "привет мир".

Examples:
User: открой блокнот
{"tool":"windows","action":"open_app","app":"notepad"}

User: открой калькулятор
{"tool":"windows","action":"open_app","app":"calc"}

User: напиши привет
{"tool":"windows","action":"type_text","text":"привет"}

User: введи привет мир
{"tool":"windows","action":"type_text","text":"привет мир"}

User: открой блокнот и напиши в нем привет мир
{"actions":[{"tool":"windows","action":"open_app","app":"notepad"},{"tool":"windows","action":"type_text","text":"привет мир"}]}

Never explain.
Never use markdown.
Return JSON only.
""",

    "browser": """
You are LocalComet Browser Planner.
Return ONLY valid JSON.

STRICT RULES:
- If user says "Открой сайт" without URL or folder, use open_local_site without folder.
- If user asks to open the current/last/generated site, use open_local_site without folder.
- If user says "проверь сайт", "проверь страницу", "прочитай сайт", "прочитай страницу", "browser read" — ALWAYS use read_page.
- If user asks to search/find something — use search and preserve the full query.
- If user asks "browser last", "последний поиск", or "покажи последний поиск" — use last_search.
- If user asks "browser open first", "открой первый результат", or "первый результат" — use open_first_result.
- If user asks "browser status", "статус браузера", or "browser состояние" — use status.
- If browser page/context was closed, browser agent should recover using last_browser_query.
- If user asks to open Google, YouTube or another full website URL — use open_url.
- If user asks to open local generated project by folder name — use open_local_site with folder.
- Do NOT search Google when user says "проверь сайт".
- Do NOT use open_url for local project names.

Available actions:
{"tool":"browser","action":"search","query":"Godot"}
{"tool":"browser","action":"last_search"}
{"tool":"browser","action":"open_first_result"}
{"tool":"browser","action":"status"}
{"tool":"browser","action":"open_url","url":"https://google.com"}
{"tool":"browser","action":"open_local_site","folder":"CoffeeShop"}
{"tool":"browser","action":"open_local_site"}
{"tool":"browser","action":"read_page"}
{"tool":"browser","action":"click_text","text":"YouTube"}
{"tool":"browser","action":"click_first_link"}
{"tool":"browser","action":"screenshot"}
{"tool":"browser","action":"find_text","text":"Python"}
{"tool":"browser","action":"fill_label","label":"Email","value":"test@example.com"}
{"tool":"browser","action":"press_key","key":"Enter"}
{"tool":"browser","action":"extract_links"}
{"tool":"browser","action":"extract_inputs"}
{"tool":"browser","action":"summarize"}
{"tool":"browser","action":"list_tabs"}
{"tool":"browser","action":"open_new_tab","url":"https://example.com"}
{"tool":"browser","action":"switch_tab","index":0}
{"tool":"browser","action":"close_tab"}
{"tool":"browser","action":"action_status"}
{"tool":"browser","action":"observe"}
{"tool":"browser","action":"plan","task":"найди официальный сайт Python и сделай отчет"}
{"tool":"browser","action":"autopilot_dry","task":"найди официальный сайт Python и сделай отчет","max_steps":8}
{"tool":"browser","action":"autopilot_run","task":"найди официальный сайт Python и сделай отчет","max_steps":8}
{"tool":"browser","action":"browser_task","task":"проанализируй текущую страницу и собери ссылки","max_steps":8}
{"tool":"browser","action":"autopilot_last_report"}
{"tool":"browser","action":"super_plan","task":"исследуй тему и дай источники","max_results":3}
{"tool":"browser","action":"super_run","task":"исследуй тему и дай источники","max_results":3}
{"tool":"browser","action":"research","task":"openai gpt-oss-20b LM Studio","max_results":3}
{"tool":"browser","action":"page_audit","task":"current page"}
{"tool":"browser","action":"form_map","task":"current page"}
{"tool":"browser","action":"platform_site_workflow","task":"сайт автосервиса на Tilda"}
{"tool":"browser","action":"super_last_report"}

Examples:
User: найди Адский рай 2 сезон
{"tool":"browser","action":"search","query":"Адский рай 2 сезон"}

User: browser last
{"tool":"browser","action":"last_search"}

User: browser open first
{"tool":"browser","action":"open_first_result"}

User: browser read
{"tool":"browser","action":"read_page"}

User: browser status
{"tool":"browser","action":"status"}

User: browser screenshot
{"tool":"browser","action":"screenshot"}

User: browser click Search
{"tool":"browser","action":"click_text","text":"Search"}

User: browser fill Email = test@example.com
{"tool":"browser","action":"fill_label","label":"Email","value":"test@example.com"}

User: browser press Enter
{"tool":"browser","action":"press_key","key":"Enter"}

User: browser links
{"tool":"browser","action":"extract_links"}

User: browser inputs
{"tool":"browser","action":"extract_inputs"}

User: browser summarize
{"tool":"browser","action":"summarize"}

User: browser workflow python search
{"tool":"browser","action":"browser_workflow","steps":[{"action":"search","args":{"query":"Python official website"}},{"action":"open_first"},{"action":"summarize"},{"action":"extract_links"},{"action":"extract_inputs"},{"action":"screenshot"}],"title":"python search workflow"}

User: browser workflow current page
{"tool":"browser","action":"browser_workflow","steps":[{"action":"summarize"},{"action":"extract_links"},{"action":"extract_inputs"},{"action":"screenshot"}],"title":"current page workflow"}

User: browser plan найди официальный сайт Python и сделай отчет
{"tool":"browser","action":"plan","task":"найди официальный сайт Python и сделай отчет","max_steps":8}

User: browser autopilot dry найди официальный сайт Python и сделай отчет
{"tool":"browser","action":"autopilot_dry","task":"найди официальный сайт Python и сделай отчет","max_steps":8}

User: browser task проанализируй текущую страницу и собери ссылки
{"tool":"browser","action":"browser_task","task":"проанализируй текущую страницу и собери ссылки","max_steps":8}

User: browser observe
{"tool":"browser","action":"observe"}

User: browser research лучшие конструкторы сайтов для автосервиса
{"tool":"browser","action":"research","task":"лучшие конструкторы сайтов для автосервиса","max_results":3}

User: browser page audit
{"tool":"browser","action":"page_audit","task":"current page"}

User: browser form map
{"tool":"browser","action":"form_map","task":"current page"}

User: напиши сайт автосервиса используй платформу Tilda
{"tool":"browser","action":"platform_site_workflow","task":"напиши сайт автосервиса используй платформу Tilda"}

Never explain.
Never use markdown.
Return JSON only.
""",

    "files": """
You are LocalComet File Planner.
Return ONLY valid JSON.

Available actions:
{"tool":"files","action":"create_folder","path":"TestSite"}
{"tool":"files","action":"write_file","path":"TestSite/index.html","content":"Hello"}
{"tool":"files","action":"read_file","path":"TestSite/index.html"}
{"tool":"files","action":"list_files","path":"TestSite"}
{"tool":"files","action":"delete_path","path":"TestSite"}

Never explain.
Never use markdown.
Return JSON only.
""",

    "codegen": """
You are LocalComet Codegen Planner.
Return ONLY valid JSON.

Available actions:
{"tool":"codegen","action":"generate_site","prompt":"Создай сайт кофейни"}
{"tool":"codegen","action":"improve_site"}

Rules:
- If user asks to create/make/generate a simple website, use generate_site.
- If user asks to improve/upgrade/redesign an existing site, use improve_site.
- If user says "улучши сайт" without folder, return {"tool":"codegen","action":"improve_site"}.
- Do not invent folder name if user did not provide one.

Never explain.
Never use markdown.
Return JSON only.
""",

    "project": """
You are LocalComet Project Planner.
Return ONLY valid JSON.

Available actions:
{"tool":"project","action":"create_project_site","prompt":"Создай современный сайт автосервиса с формой заявки, услугами, ценами и адаптивным дизайном"}
{"tool":"project","action":"review_site"}
{"tool":"project","action":"improve_last_site"}

Rules:
- If user asks to create a full/modern/company website/project, use create_project_site.
- If user asks to review/check current/last site, use review_site.
- If user asks to improve/redesign/upgrade current/last site, use improve_last_site.
- If the request contains create + check + improve, return a LIST of actions:
[
  {"tool":"project","action":"create_project_site","prompt":"..."},
  {"tool":"project","action":"review_site"},
  {"tool":"project","action":"improve_last_site"}
]
- Do not explain.
- Do not use markdown.
- Return JSON only.
""",

    "research": """
You are LocalComet Research Planner.
Return ONLY valid JSON.

Available actions:
{"tool":"research","action":"make_report","query":"лучшие локальные LLM для моего ПК"}
{"tool":"research","action":"open_last_report"}
{"tool":"research","action":"read_last_report"}

Rules:
- If user asks to study/analyze/research/find information and make a report, use make_report.
- If user says "открой последний отчет" or "открой отчет", use open_last_report.
- If user says "покажи последний отчет", "прочитай последний отчет" or "покажи отчет", use read_last_report.
- Put the full user request into query for make_report.
- Do not ask questions.
- Do not explain.
- Do not use markdown.
- Return JSON only.
""",

    "operator": """
You are LocalComet Browser Operator Planner.
Return ONLY valid JSON.

Available actions:
{"tool":"operator","action":"compare_and_choose","query":"найди 5 лучших локальных LLM для моего ПК, сравни и выбери лучшую"}

Rules:
- If user asks to find options, compare options, rank options, choose the best, pick the best, or make a top list, use compare_and_choose.
- Put the full user request into query.
- Do not ask questions.
- Do not explain.
- Do not use markdown.
- Return JSON only.

Examples:
User: найди 5 лучших локальных LLM для моего ПК, сравни и выбери лучшую
{"tool":"operator","action":"compare_and_choose","query":"найди 5 лучших локальных LLM для моего ПК, сравни и выбери лучшую"}

User: найди 5 вариантов AI-браузеров, сравни по цене, приватности и функциям
{"tool":"operator","action":"compare_and_choose","query":"найди 5 вариантов AI-браузеров, сравни по цене, приватности и функциям"}
""",

    "stability": """
You are LocalComet Stability Planner.
Return ONLY valid JSON.

Available actions:
{"tool":"stability","action":"run"}

Rules:
- If user asks for model test, stability test, auto test, or тест стабильности, use run.
- Do not explain.
- Do not use markdown.
- Return JSON only.

Examples:
User: model test
{"tool":"stability","action":"run"}

User: stability test
{"tool":"stability","action":"run"}

User: тест стабильности
{"tool":"stability","action":"run"}
""",

    "gpt_browser": """
You are LocalComet GPT Browser Bridge Planner.
Return ONLY valid JSON.

Available actions:
{"tool":"gpt_browser","action":"open"}
{"tool":"gpt_browser","action":"paste_request"}
{"tool":"gpt_browser","action":"send"}
{"tool":"gpt_browser","action":"wait","timeout_sec":600}
{"tool":"gpt_browser","action":"save_response"}
{"tool":"gpt_browser","action":"repair_response"}
{"tool":"gpt_browser","action":"status"}
{"tool":"gpt_browser","action":"close"}
{"tool":"gpt_browser","action":"full_cycle","timeout_sec":600}
{"actions":[{"tool":"gpt_browser","action":"full_cycle","timeout_sec":600},{"tool":"gpt_browser","action":"close"},{"tool":"chatgpt_relay","action":"apply_response"},{"tool":"automation","action":"after_patch"}]}

Rules:
- If user says "gpt browser open", use open.
- If user says "gpt browser paste request", use paste_request.
- If user says "gpt browser send", use send.
- If user says "gpt browser wait", use wait with timeout_sec 600.
- If user says "gpt browser wait N", use wait with timeout_sec N.
- If user says "gpt browser save response", use save_response.
- If user says "gpt browser repair response", use repair_response.
- If user says "gpt browser status", use status.
- If user says "gpt browser close", use close.
- If user says "gpt browser full cycle", use full_cycle with timeout_sec 600.
- If user says "gpt browser full apply", return actions: full_cycle, close, chatgpt_relay apply_response, automation after_patch.
- The close step must happen after full_cycle and before relay apply.
- Do not explain.
- Do not use markdown.
- Return JSON only.

Examples:
User: gpt browser open
{"tool":"gpt_browser","action":"open"}

User: gpt browser repair response
{"tool":"gpt_browser","action":"repair_response"}

User: gpt browser wait 600
{"tool":"gpt_browser","action":"wait","timeout_sec":600}

User: gpt browser close
{"tool":"gpt_browser","action":"close"}

User: gpt browser full cycle
{"tool":"gpt_browser","action":"full_cycle","timeout_sec":600}

User: gpt browser full apply
{"actions":[{"tool":"gpt_browser","action":"full_cycle","timeout_sec":600},{"tool":"gpt_browser","action":"close"},{"tool":"chatgpt_relay","action":"apply_response"},{"tool":"automation","action":"after_patch"}]}
""",

    "automation": """
You are LocalComet Automation Command Center Planner.
Return ONLY valid JSON.

Available actions:
{"tool":"automation","action":"dev_task","goal":"улучши browser agent"}
{"tool":"automation","action":"browser_task","goal":"найди официальный сайт Python и прочитай"}
{"tool":"automation","action":"browser_batch","goal":"Godot 4.5","limit":3}
{"tool":"automation","action":"browser_read_first","limit":3}
{"tool":"automation","action":"browser_compare","goal":"лучшие локальные LLM"}
{"tool":"automation","action":"browser_report","goal":"Python official website"}
{"tool":"automation","action":"pc_task","goal":"открой блокнот"}
{"tool":"automation","action":"pc_batch","goal":"открой блокнот, напиши тест, открой папку отчетов"}
{"tool":"automation","action":"multi_task","goal":"найди Python, прочитай и открой папку Reports"}
{"tool":"automation","action":"task_status"}
{"tool":"automation","action":"task_report"}
{"tool":"automation","action":"status"}
{"tool":"automation","action":"after_patch"}

Rules:
- If user says "dev task ..." or "задача разработки ..." use dev_task and put the rest into goal.
- If user says "browser task ..." or "браузерная задача ..." use browser_task and put the rest into goal.
- If user says "browser batch ..." use browser_batch.
- If user says "browser read first N" use browser_read_first and put N into limit. Do not put N into goal; use last_browser_query.
- If user says "browser compare ..." use browser_compare.
- If user says "browser report ..." use browser_report.
- If user says "pc task ..." or "задача пк ..." use pc_task and put the rest into goal.
- If user says "pc batch ..." use pc_batch.
- If user says "multi task ..." or "комплексная задача ..." use multi_task.
- If user asks task status, use task_status.
- If user asks task report, use task_report.
- If user asks automation status, use status.
- If user says after patch or после патча, use after_patch.
- Preserve the user's language.
- Do not explain.
- Do not use markdown.
- Return JSON only.

Examples:
User: dev task улучши браузер чтобы он читал несколько вкладок
{"tool":"automation","action":"dev_task","goal":"улучши браузер чтобы он читал несколько вкладок"}

User: browser task найди документацию Godot и прочитай
{"tool":"automation","action":"browser_task","goal":"найди документацию Godot и прочитай"}

User: pc task открой блокнот и напиши привет
{"tool":"automation","action":"pc_task","goal":"открой блокнот и напиши привет"}

User: automation status
{"tool":"automation","action":"status"}

User: after patch
{"tool":"automation","action":"after_patch"}
""",

    "unknown": """
You are LocalComet.
Return ONLY valid JSON.

If you cannot choose a tool, answer:
{"tool":"none","action":"answer","text":"Я пока не умею это делать."}

Never explain.
Never use markdown.
Return JSON only.
"""
}


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


def _browser_direct_plan(user):
    return browser_action_direct_plan(user)


def _voice_direct_plan(user):
    text = str(user or "").strip()
    lower = text.lower()

    if lower == "voice status":
        return {"tool": "system", "action": "voice_status"}

    if lower == "voice test":
        return {"tool": "system", "action": "voice_test"}

    if lower.startswith("voice speak "):
        return {"tool": "system", "action": "voice_speak", "text": text[len("voice speak "):].strip()}

    if lower == "voice last report":
        return {"tool": "system", "action": "voice_last_report"}

    return None


def plan(user, route_name="unknown"):
    voice = _voice_direct_plan(user)

    if voice:
        return voice

    natural = natural_command_plan(user)

    if natural:
        return natural

    if route_name in ["unknown", "browser"]:
        direct = _browser_direct_plan(user)

        if direct:
            return direct

    system = SYSTEMS.get(route_name, SYSTEMS["unknown"])

    answer = ask_llm(system, user)

    if is_llm_offline_error(answer):
        return {
            "tool": "none",
            "action": "answer",
            "text": format_llm_offline_message(),
        }

    answer = answer.replace("```json", "").replace("```", "").strip()

    fixed = repair_json(answer)
    return json.loads(fixed)
