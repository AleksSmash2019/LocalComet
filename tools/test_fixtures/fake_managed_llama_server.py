#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


FLAGS = (
    "--model",
    "--host",
    "--port",
    "--api-key-file",
    "--no-webui",
    "--no-agent",
    "--ctx-size",
    "--n-predict",
    "--alias",
)
MAX_BODY = 64 * 1024
MAX_SSE_BYTES = 64 * 1024


def _version() -> int:
    print("fake managed llama.cpp test fixture 1")
    return 0


def _help() -> int:
    print(" ".join(FLAGS))
    return 0


class Handler(BaseHTTPRequestHandler):
    server_version = "FakeManagedLlama/1"
    protocol_version = "HTTP/1.1"

    def log_message(self, *_: Any) -> None:
        return

    def _authorized(self) -> bool:
        expected = f"Bearer {self.server.credential}"  # type: ignore[attr-defined]
        return self.headers.get("Authorization") == expected

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path not in {"/health", "/v1/models"}:
            self._send_json(404, {"error": "not_found"})
            return
        if not self._authorized():
            self._send_json(401, {"error": "unauthorized"})
            return
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
            return
        self._send_json(200, {"object": "list", "data": [{"id": self.server.alias}]})  # type: ignore[attr-defined]

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self._send_json(404, {"error": "not_found"})
            return
        if not self._authorized():
            self._send_json(401, {"error": "unauthorized"})
            return
        length_text = self.headers.get("Content-Length", "0")
        if not length_text.isdecimal() or int(length_text) > MAX_BODY:
            self._send_json(413, {"error": "too_large"})
            return
        body = self.rfile.read(int(length_text))
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            self._send_json(400, {"error": "bad_json"})
            return
        if payload.get("model") != self.server.alias or payload.get("stream") is not True:  # type: ignore[attr-defined]
            self._send_json(400, {"error": "bad_request"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Connection", "close")
        self.end_headers()
        chunks = [
            b'data: {"choices":[{"index":0,"delta":{"content":"fake"},"finish_reason":null}]}\n\n',
            b"data: [DONE]\n\n",
        ]
        total = 0
        for chunk in chunks:
            total += len(chunk)
            if total > MAX_SSE_BYTES:
                break
            self.wfile.write(chunk)
            self.wfile.flush()


def _parse(argv: list[str]) -> argparse.Namespace:
    if argv == ["--version"]:
        raise SystemExit(_version())
    if argv == ["--help"]:
        raise SystemExit(_help())
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--model", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", required=True)
    parser.add_argument("--api-key-file", required=True)
    parser.add_argument("--no-webui", action="store_true", required=True)
    parser.add_argument("--no-agent", action="store_true", required=True)
    parser.add_argument("--ctx-size", required=True)
    parser.add_argument("--n-predict", required=True)
    parser.add_argument("--alias", required=True)
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        raise SystemExit("unknown flag rejected")
    if args.host != "127.0.0.1":
        raise SystemExit("host rejected")
    if not args.port.isdecimal() or not (1024 <= int(args.port) <= 65535):
        raise SystemExit("port rejected")
    if not str(args.ctx_size).isdecimal() or not str(args.n_predict).isdecimal():
        raise SystemExit("numeric flag rejected")
    model = Path(args.model)
    key_file = Path(args.api_key_file)
    if not model.is_file() or model.is_symlink() or not key_file.is_file() or key_file.is_symlink():
        raise SystemExit("fixture path rejected")
    if model.read_bytes()[:4] != b"GGUF":
        raise SystemExit("model magic rejected")
    credential = key_file.read_text(encoding="utf-8").strip()
    if len(credential) < 64 or any(ch not in "0123456789abcdef" for ch in credential):
        raise SystemExit("credential rejected")
    args.credential = credential
    return args


def main(argv: list[str]) -> int:
    args = _parse(argv)
    httpd = ThreadingHTTPServer(("127.0.0.1", int(args.port)), Handler)
    httpd.credential = args.credential  # type: ignore[attr-defined]
    httpd.alias = args.alias  # type: ignore[attr-defined]
    try:
        httpd.serve_forever(poll_interval=0.1)
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
