from modules.self_edit import (
    create_patch,
    show_last_patch,
    apply_last_patch,
    rollback_last_patch,
    project_health,
    auto_edit,
)


def handle(action: str, data: dict):
    if action == "health":
        return project_health()

    if action == "create_patch":
        return create_patch(data.get("goal", ""))

    if action == "show_last_patch":
        return show_last_patch()

    if action == "apply_last_patch":
        return apply_last_patch()

    if action == "rollback_last_patch":
        return rollback_last_patch()

    if action == "auto_edit":
        return auto_edit(data.get("goal", ""))

    return "SelfEdit Agent: неизвестное действие."