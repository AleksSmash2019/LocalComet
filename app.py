# DEPRECATED: This is the v3 legacy REPL.
# Use next/app_v5.py for the current command loop.
# Removal decision is reserved for the repository owner.

from core.router import route
from core.planner import plan
from core.executor import execute
from core.loop import run_loop


print("=" * 40)
print(" LocalComet v3 — Agent Loop ")
print("=" * 40)

print("Обычная команда: Открой калькулятор")
print("Длинная задача: задача: создай сайт кофейни и открой его")


while True:
    user = input("\nТы: ").strip()

    if user.lower() in ["exit", "выход"]:
        break

    try:
        if user.lower().startswith("задача:"):
            task = user.split(":", 1)[1].strip()
            print(run_loop(task))
            continue

        route_name = route(user)
        print("ROUTE:", route_name)

        result = plan(user, route_name)
        print(result)

        output = execute(result)
        print(output)

    except Exception as e:
        print("Ошибка:", e)