from agents import browser_agent
from agents import code_agent
from agents import file_agent
from agents import operator_agent
from agents import project_agent
from agents import research_agent
from agents import windows_agent
from agents import system_agent
from agents import workspace_agent
from agents import diagnostics_agent
from agents import history_agent
from agents import maintenance_agent
from agents import self_edit_agent
from agents import gpt_agent
from agents import chatgpt_relay_agent
from agents import stability_agent
from agents import automation_agent
from agents import gpt_browser_agent


def execute(plan):
    if plan is None:
        return "Executor: пустой план."

    if isinstance(plan, list):
        results = []

        for i, action_plan in enumerate(plan, start=1):
            result = execute(action_plan)
            results.append(f"{i}. {result}")

        return "\n".join(results)

    if not isinstance(plan, dict):
        return f"Executor: неправильный формат плана: {plan}"

    if "actions" in plan:
        actions = plan.get("actions")

        if not isinstance(actions, list):
            return "Executor: поле actions должно быть списком."

        results = []

        for i, action_plan in enumerate(actions, start=1):
            result = execute(action_plan)
            results.append(f"{i}. {result}")

        return "\n".join(results)

    tool = plan.get("tool")
    action = plan.get("action")

    if not tool:
        return f"Executor: неизвестный инструмент. План: {plan}"

    if tool == "none":
        return plan.get("text", "OK")

    if tool == "system":
        return system_agent.handle(action, plan)

    if tool == "diagnostics":
        return diagnostics_agent.handle(action, plan)

    if tool == "history":
        return history_agent.handle(action, plan)

    if tool == "maintenance":
        return maintenance_agent.handle(action, plan)

    if tool == "self_edit":
        return self_edit_agent.handle(action, plan)

    if tool == "gpt":
        return gpt_agent.handle(action, plan)

    if tool == "chatgpt_relay":
        if action in [
            "apply",
            "apply_response",
            "apply_answer",
            "apply_last_response",
            "relay_apply",
        ]:
            try:
                from modules.browser_profile_ignore import close_gpt_browser_context

                close_gpt_browser_context()
            except Exception:
                pass

        return chatgpt_relay_agent.handle(action, plan)

    if tool == "stability":
        return stability_agent.handle(action, plan)

    if tool == "automation":
        return automation_agent.handle(action, plan)

    if tool == "gpt_browser":
        return gpt_browser_agent.handle(action, plan)

    if tool == "workspace":
        return workspace_agent.handle(action, plan)

    if tool == "browser":
        return browser_agent.handle(action, plan)

    if tool in ["file", "files"]:
        return file_agent.handle(action, plan)

    if tool in ["code", "codegen"]:
        return code_agent.handle(action, plan)

    if tool == "project":
        return project_agent.handle(action, plan)

    if tool == "research":
        return research_agent.handle(action, plan)

    if tool == "operator":
        return operator_agent.handle(action, plan)

    if tool == "windows":
        return windows_agent.handle(action, plan)

    return f"Executor: неизвестный инструмент: {tool}"