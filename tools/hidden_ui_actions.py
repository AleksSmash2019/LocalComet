from __future__ import annotations

import asyncio
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

import websockets

CDP = "http://127.0.0.1:58215"
ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "Projects" / "Reports" / "computer_use_real_actions" / "hidden_ui_run"


async def get_target() -> dict[str, Any]:
    with urllib.request.urlopen(f"{CDP}/json/list", timeout=10) as response:
        targets = json.loads(response.read().decode("utf-8"))
    local = [item for item in targets if item.get("type") == "page" and "127.0.0.1:1420" in item.get("url", "")]
    if not local:
        raise RuntimeError("LocalComet page is not present in CDP target list")
    return local[0]


class Browser:
    def __init__(self, ws_url: str) -> None:
        self.ws_url = ws_url
        self.ws = None
        self.pending: dict[int, asyncio.Future] = {}
        self.next_id = 0
        self.receiver_task: asyncio.Task | None = None

    async def __aenter__(self) -> "Browser":
        self.ws = await websockets.connect(self.ws_url, max_size=16 * 1024 * 1024)
        self.receiver_task = asyncio.create_task(self._receiver())
        await self.call("Page.enable")
        await self.call("Runtime.enable")
        await self.call("Page.bringToFront")
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.receiver_task:
            self.receiver_task.cancel()
        if self.ws:
            await self.ws.close()

    async def _receiver(self) -> None:
        assert self.ws is not None
        async for raw in self.ws:
            message = json.loads(raw)
            future = self.pending.pop(message.get("id"), None)
            if future is not None:
                future.set_result(message)

    async def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        assert self.ws is not None
        self.next_id += 1
        future = asyncio.get_running_loop().create_future()
        self.pending[self.next_id] = future
        await self.ws.send(json.dumps({"id": self.next_id, "method": method, "params": params or {}}))
        return await asyncio.wait_for(future, timeout=20)

    async def evaluate(self, expression: str) -> Any:
        result = await self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
        remote = result.get("result", {}).get("result", {})
        if remote.get("subtype") == "error" or "exceptionDetails" in result.get("result", {}):
            raise RuntimeError(json.dumps(result, ensure_ascii=False))
        return remote.get("value")

    async def snapshot(self, label: str) -> dict[str, Any]:
        value = await self.evaluate("""(() => ({
          url: location.href,
          title: document.title,
          bodyText: document.body?.innerText || '',
          controls: [...document.querySelectorAll('button,a,input,textarea,[role=button],[role=tab]')].map((el) => ({
            tag: el.tagName,
            text: (el.innerText || el.getAttribute('aria-label') || el.getAttribute('placeholder') || '').trim().slice(0, 200),
            type: el.getAttribute('type') || '',
            disabled: !!el.disabled,
            checked: 'checked' in el ? !!el.checked : null,
            value: 'value' in el ? String(el.value || '').slice(0, 120) : null
          })).filter((item) => item.text || item.type)
        }))()""")
        path = EVIDENCE / f"{label}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        return value

    async def click_text(self, text: str, occurrence: int = 0) -> dict[str, Any]:
        expression = """(text, occurrence) => {
          const nodes = [...document.querySelectorAll('button,a,[role=button],[role=tab]')]
            .filter((el) => (el.innerText || el.getAttribute('aria-label') || '').trim().includes(text));
          const el = nodes[occurrence];
          if (!el) return {ok:false, reason:'not_found', count:nodes.length};
          if (el.disabled) return {ok:false, reason:'disabled', count:nodes.length};
          el.click();
          return {ok:true, tag:el.tagName, text:(el.innerText || '').trim().slice(0,200), count:nodes.length};
        }"""
        return await self.evaluate(f"({expression})({json.dumps(text, ensure_ascii=False)}, {occurrence})")

    async def set_textarea(self, text: str) -> dict[str, Any]:
        expression = """(text) => {
          const el = document.querySelector('textarea');
          if (!el) return {ok:false, reason:'textarea_not_found'};
          if (el.disabled) return {ok:false, reason:'textarea_disabled', placeholder:el.placeholder};
          const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
          setter.call(el, text);
          el.dispatchEvent(new Event('input', {bubbles:true}));
          el.dispatchEvent(new Event('change', {bubbles:true}));
          return {ok:true, value:el.value};
        }"""
        return await self.evaluate(f"({expression})({json.dumps(text, ensure_ascii=False)})")

    async def click_button_text(self, text: str, occurrence: int = 0) -> dict[str, Any]:
        return await self.click_text(text, occurrence)


async def main() -> int:
    target = await get_target()
    async with Browser(target["webSocketDebuggerUrl"]) as browser:
        await browser.click_text("Чат")
        await asyncio.sleep(0.8)
        await browser.click_text("Настроить локальный AI")
        await asyncio.sleep(0.5)
        await browser.click_text("Свой .gguf")
        await asyncio.sleep(0.5)
        result = await browser.click_text("Импорт .gguf")
        await asyncio.sleep(0.8)
        input_count = await browser.evaluate("document.querySelectorAll('input[type=file]').length")
        file_set = False
        if input_count:
            await browser.call("DOM.enable")
            document = await browser.call("DOM.getDocument", {"depth": 0})
            node = await browser.call("DOM.querySelector", {"nodeId": document["result"]["root"]["nodeId"], "selector": "input[type=file]"})
            node_id = node.get("result", {}).get("nodeId", 0)
            if node_id:
                await browser.call("DOM.setFileInputFiles", {"nodeId": node_id, "files": [r"C:\\Users\\DNS\\Downloads\\Qwen3-1.7B-Q4_K_M.gguf"]})
                file_set = True
        await asyncio.sleep(1.5)
        snapshot = await browser.snapshot("qwen3_gguf_selected")
        print(json.dumps({"click": result, "file_input_count": input_count, "file_set": file_set, "body_preview": snapshot.get("bodyText", "")[:4000], "control_count": len(snapshot.get("controls", []))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
