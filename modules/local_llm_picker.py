from datetime import datetime
from pathlib import Path
from modules.project_paths import projects_dir


PROJECTS_DIR = projects_dir()
REPORTS_DIR = PROJECTS_DIR / "Reports"


def make_local_llm_picker_report(query: str):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Выбор локальной LLM для LocalComet",
        "",
        "## Задача",
        "",
        "Выбрать лучшую локальную модель для LocalComet.",
        "",
        "LocalComet — это локальный AI-агент на Python, который работает через LM Studio и выполняет задачи через инструменты:",
        "",
        "- browser",
        "- research",
        "- operator",
        "- files",
        "- codegen",
        "- project",
        "- windows",
        "",
        "Для LocalComet важнее не просто красивый текст, а стабильность:",
        "",
        "- строгий JSON",
        "- tool/action",
        "- работа с кодом",
        "- планирование",
        "- меньше галлюцинаций",
        "- нормальная скорость",
        "",
        "## Железо пользователя",
        "",
        "- CPU: Intel Core i7-14700KF",
        "- GPU: RTX 5070 12 GB",
        "- RAM: 32 GB DDR5",
        "- OS: Windows",
        "- Запуск моделей: LM Studio",
        "",
        "## Сравнение моделей",
        "",
        "| Модель | Плюсы | Минусы | Итог |",
        "|---|---|---|---|",
        "| Qwen3-14B Q4_K_M | Быстрая, свежая, хорошо держит JSON, подходит для агента | Не специализирована только под код | Лучший основной вариант |",
        "| Qwen2.5-Coder-14B Q4_K_M | Очень хороша для кода, Python, tool/action | Старее Qwen3 | Лучший вариант для кодинга |",
        "| Qwen3-Coder-30B-A3B | Сильная coder-модель | У пользователя около 4.5 t/s, слишком медленно | Только для тяжёлых задач |",
        "| Gemma 4 e4b | Быстрая, уже работала | Слабее как агент | Запасной вариант |",
        "| Gemma 4 31B QAT | Потенциально мощная | Тяжёлая, может быть медленной | Эксперимент |",
        "",
        "## Лучший выбор",
        "",
        "### Qwen3-14B Q4_K_M",
        "",
        "Это лучший основной мозг для LocalComet прямо сейчас.",
        "",
        "Почему:",
        "",
        "1. На hard-test модель дала 9.4/10.",
        "2. Скорость около 44 t/s — это отлично.",
        "3. Она примерно в 9–10 раз быстрее Qwen3-Coder-30B-A3B.",
        "4. Хорошо подходит для planner, router, operator, research и windows-задач.",
        "5. Нормально работает на RTX 5070 12 GB.",
        "",
        "## Что оставить вторым вариантом",
        "",
        "### Qwen3-Coder-30B-A3B",
        "",
        "Её можно оставить как тяжёлую модель для сложного кода, но не как основной мозг LocalComet.",
        "",
        "Причина: скорость около 4.5 t/s слишком низкая для многошагового агента.",
        "",
        "## Финальная рекомендация",
        "",
        "Основная модель:",
        "",
        "qwen3-14b",
        "",
        "Тяжёлая coder-модель:",
        "",
        "qwen3-coder-30b-a3b-instruct",
        "",
        "Запасная модель:",
        "",
        "google/gemma-4-e4b",
        "",
        "## Что сделать дальше",
        "",
        "1. Оставить в config.py:",
        "",
        'MODEL = "qwen3-14b"',
        "",
        "2. Не использовать Qwen3-Coder-30B как основную модель.",
        "3. Продолжать разработку LocalComet на Qwen3-14B.",
    ]

    report = "\n".join(lines)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"Reports/{stamp}_localcomet_llm_picker.md"
    full_path = PROJECTS_DIR / path

    full_path.write_text(report, encoding="utf-8")

    return {
        "path": path,
        "report": report,
        "sources": [],
        "search_queries": [
            "local LocalComet model picker",
            "Qwen3-14B RTX 5070 12GB LM Studio"
        ],
        "items": [
            {"name": "Qwen3-14B Q4_K_M"},
            {"name": "Qwen2.5-Coder-14B Q4_K_M"},
            {"name": "Qwen3-Coder-30B-A3B"},
            {"name": "Gemma 4 e4b"},
            {"name": "Gemma 4 31B QAT"}
        ],
        "collected_count": 0
    }