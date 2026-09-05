#!/usr/bin/env python
"""H1+H2 negative fixtures (external audit 2026-09-03).

H1: modules/browser.py::open_url must refuse model-supplied file:// URLs —
page.goto(file://...) is an arbitrary file reader; the only sanctioned local
path is open_local_site() behind Projects safe_path() containment.

H2: modules/tool_execution_ru.py::_web_search must bound the response body
and reject non-HTML content types, mirroring _web_fetch's 10 KiB discipline.

unittest.TestCase so both `python tests/...` and pytest collect and run them;
plain check_* functions are invisible to pytest's collector.
"""
from __future__ import annotations

import io
import pathlib
import sys
import unittest
import urllib.error

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "modules"))


class H1FileUrlRefusalTests(unittest.TestCase):
    def test_file_urls_rejected(self) -> None:
        import browser

        hostile_targets = [
            "file:///C:/Windows/win.ini",
            "file://C:/Windows/win.ini",
            "file:///etc/passwd",
            "FILE:///C:/Users/DNS/secret.txt",
        ]
        for target in hostile_targets:
            result = browser.open_url(target)
            self.assertIn("Отказано", str(result), f"file:// target was not refused: {target!r} -> {result!r}")

    def test_non_file_input_misses_the_file_refusal(self) -> None:
        import browser

        result = browser.open_url("some-project")
        self.assertNotIn("Отказано: прямые file://", str(result))


class H2BoundedWebSearchTests(unittest.TestCase):
    def test_search_bounds_body_and_checks_content_type_first(self) -> None:
        import tool_execution_ru

        source = pathlib.Path(REPO_ROOT / "modules" / "tool_execution_ru.py").read_text(
            encoding="utf-8"
        )
        search_start = source.index("def _web_search")
        search_body = source[search_start : source.index("\ndef ", search_start + 10)]
        self.assertIn("resp.read(_MAX_FETCH_BYTES + 1)", search_body)
        self.assertIn("content_type", search_body.replace("Content-Type", "content_type"))

    def test_non_html_content_type_is_refused_before_buffering(self) -> None:
        import tool_execution_ru
        import urllib.request

        class HostileResponse:
            def __init__(self) -> None:
                self.headers = {"Content-Type": "application/octet-stream"}
                self.read_calls = 0

            def read(self, amount=-1):
                self.read_calls += 1
                return b"MIME-confused body"

        class FakeUrlopen:
            def __init__(self, response: HostileResponse) -> None:
                self.response = response

            def __enter__(self):
                return self.response

            def __exit__(self, *exc):
                return False

        hostile = HostileResponse()
        real_urlopen = urllib.request.urlopen
        urllib.request.urlopen = lambda req, timeout=10: FakeUrlopen(hostile)  # type: ignore[assignment]
        try:
            with self.assertRaises(tool_execution_ru.ToolExecutionError) as ctx:
                tool_execution_ru._web_search(
                    None, "web.search", {"query": "hostile content type probe"}
                )
            self.assertIn("content-type", str(ctx.exception.message).lower())
            self.assertEqual(hostile.read_calls, 0, "body was buffered before the content-type check")
        finally:
            urllib.request.urlopen = real_urlopen  # type: ignore[assignment]
