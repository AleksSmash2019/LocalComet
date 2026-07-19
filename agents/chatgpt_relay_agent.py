from modules.chatgpt_relay import (
    relay_status,
    create_request,
    create_snapshot,
    create_error_doctor,
    copy_request,
    open_chatgpt,
    open_relay_folder,
    start_relay,
    start_relay_silent,
    show_request,
    last_request_path,
    open_last_request,
    save_clipboard_response,
    show_response,
    validate_response,
    clear_response,
    import_response_as_patch,
    apply_response,
)
from modules.relay_diagnostics import (
    format_relay_diagnostics_text,
    run_relay_smoke_test,
)


def handle(action: str, data: dict):
    if action == "status":
        return relay_status()

    if action in ["diagnostics", "relay_diagnostics"]:
        return format_relay_diagnostics_text()

    if action in ["smoke", "smoke_test", "relay_smoke"]:
        return run_relay_smoke_test(dry_run=True)

    if action == "create_request":
        return create_request(data.get("goal", ""))

    if action == "create_snapshot":
        return create_snapshot(data.get("goal", ""))

    if action == "error_doctor":
        return create_error_doctor(data.get("goal", ""))

    if action == "copy_request":
        return copy_request()

    if action == "open_chatgpt":
        return open_chatgpt()

    if action == "open_relay_folder":
        return open_relay_folder()

    if action == "start":
        return start_relay(data.get("goal", ""))

    if action == "start_silent":
        return start_relay_silent(data.get("goal", ""))

    if action == "show_request":
        return show_request()

    if action == "last_request_path":
        return last_request_path()

    if action == "open_last_request":
        return open_last_request()

    if action == "save_clipboard_response":
        return save_clipboard_response()

    if action == "show_response":
        return show_response()

    if action == "validate_response":
        return validate_response()

    if action == "clear_response":
        return clear_response()

    if action == "import_response_as_patch":
        return import_response_as_patch()

    if action == "apply_response":
        return apply_response()

    return "ChatGPT Relay Agent: неизвестное действие."
