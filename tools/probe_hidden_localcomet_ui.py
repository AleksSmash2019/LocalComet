from __future__ import annotations

import asyncio
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import websockets

CDP = "http://127.0.0.1:58215"
URL = "http://127.0.0.1:1420/"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Projects" / "Reports" / "computer_use_real_actions" / "hidden_ui_run" / "ui_probe.json"


async def main() -> int:
    request = urllib.request.Request(f"{CDP}/json/new?{urllib.parse.quote(URL, safe=':/?=&')}", method="PUT")
    with urllib.request.urlopen(request, timeout=10) as response:
        target = json.loads(response.read().decode("utf-8"))
    ws_url = target["webSocketDebuggerUrl"]
    next_id = 0
    pending: dict[int, asyncio.Future] = {}

    async with websockets.connect(ws_url, max_size=8 * 1024 * 1024) as ws:
        async def receiver() -> None:
            async for raw in ws:
                message = json.loads(raw)
                if "id" in message and message["id"] in pending:
                    pending.pop(message["id"]).set_result(message)

        receive_task = asyncio.create_task(receiver())

        async def call(method: str, params: dict | None = None) -> dict:
            nonlocal next_id
            next_id += 1
            future = asyncio.get_running_loop().create_future()
            pending[next_id] = future
            await ws.send(json.dumps({"id": next_id, "method": method, "params": params or {}}))
            return await asyncio.wait_for(future, timeout=15)

        await call("Page.enable")
        await call("Runtime.enable")
        await call("Page.bringToFront")
        await asyncio.sleep(2)
        expression = """(() => ({
          url: location.href,
          title: document.title,
          bodyText: document.body?.innerText || '',
          controls: [...document.querySelectorAll('button,a,input,textarea,[role=button],[role=tab]')].map((el) => ({
            tag: el.tagName,
            text: (el.innerText || el.getAttribute('aria-label') || el.getAttribute('placeholder') || '').trim().slice(0, 160),
            type: el.getAttribute('type') || '',
            disabled: !!el.disabled,
            checked: 'checked' in el ? !!el.checked : null
          })).filter((item) => item.text || item.type)
        }))()"""
        result = await call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
        value = result.get("result", {}).get("result", {}).get("value", {})
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"target_id": target.get("id"), "url": value.get("url"), "title": value.get("title"), "control_count": len(value.get("controls", [])), "body_preview": value.get("bodyText", "")[:1200]}, ensure_ascii=False))
        receive_task.cancel()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
