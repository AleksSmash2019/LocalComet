from modules.automation_center import handle_automation


def handle(action: str, data: dict):
    return handle_automation(action, data)
