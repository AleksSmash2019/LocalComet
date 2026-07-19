from modules.stability_test import run_auto_stability_test


def handle(action: str, data: dict):
    if action in ["run", "test", "stability_test", "model_test"]:
        return run_auto_stability_test()

    return "Stability Agent: неизвестное действие."
