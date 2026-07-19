from modules import gpt_browser_bridge


def handle(action: str, data: dict):
    if action in ["open", "gpt_browser_open"]:
        return gpt_browser_bridge.open_chatgpt()

    if action in ["set_chat", "set_project_chat", "gpt_browser_set_chat"]:
        return gpt_browser_bridge.set_chat_url(data.get("url", ""))

    if action in ["show_chat", "show_project_chat", "gpt_browser_show_chat"]:
        return gpt_browser_bridge.show_chat_url()

    if action in ["clear_chat", "clear_project_chat", "gpt_browser_clear_chat"]:
        return gpt_browser_bridge.clear_chat_url()

    if action in ["open_project_chat", "project_chat", "gpt_browser_open_project_chat"]:
        return gpt_browser_bridge.open_project_chat()

    if action in ["paste_request", "paste", "gpt_browser_paste_request"]:
        return gpt_browser_bridge.paste_request()

    if action in ["send", "gpt_browser_send"]:
        return gpt_browser_bridge.send_prompt()

    if action in ["wait", "wait_response", "gpt_browser_wait"]:
        return gpt_browser_bridge.wait_response(
            timeout_sec=int(data.get("timeout_sec", 600) or 600)
        )

    if action in ["save_response", "save", "gpt_browser_save_response"]:
        return gpt_browser_bridge.save_response()

    if action in [
        "import_downloaded_response",
        "download_response",
        "save_file_response",
        "gpt_browser_import_downloaded_response",
    ]:
        return gpt_browser_bridge.import_downloaded_response()

    if action in ["downloads", "downloads_status", "gpt_browser_downloads"]:
        return gpt_browser_bridge.downloads_status()

    if action in ["open_downloads", "gpt_browser_open_downloads"]:
        return gpt_browser_bridge.open_downloads()

    if action in ["repair_response", "repair", "gpt_browser_repair_response"]:
        return gpt_browser_bridge.repair_response()

    if action in ["close", "shutdown", "gpt_browser_close"]:
        return gpt_browser_bridge.close_bridge()

    if action in ["status", "gpt_browser_status"]:
        return gpt_browser_bridge.status()

    if action in ["full_cycle", "cycle", "gpt_browser_full_cycle"]:
        return gpt_browser_bridge.full_cycle(
            timeout_sec=int(data.get("timeout_sec", 600) or 600)
        )

    if action in ["full_apply", "apply", "gpt_browser_full_apply"]:
        return gpt_browser_bridge.full_apply(
            timeout_sec=int(data.get("timeout_sec", 600) or 600)
        )

    if action in ["download_latest_response_artifact", "download_response_artifact"]:
        return gpt_browser_bridge.download_latest_response_artifact(
            timeout_sec=int(data.get("timeout_sec", 900) or 900)
        )

    if action in ["true_auto_relay_cycle", "auto_relay_cycle", "true_auto"]:
        return gpt_browser_bridge.true_auto_relay_cycle(
            goal=data.get("goal", ""),
            timeout_sec=int(data.get("timeout_sec", 900) or 900),
        )

    return "GPT Browser Agent: неизвестное действие."
