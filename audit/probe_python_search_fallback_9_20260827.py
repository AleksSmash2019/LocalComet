import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.local_model_gateway_ru import _deterministic_computer_use_call

PROMPT = "Открой браузер и найди официальный сайт Python. Ничего не отправляй и не заполняй формы."
expected = {
    "name": "computer_use",
    "arguments": {
        "action": "open_url",
        "target": "browser",
        "url": "https://www.python.org/search/?q=%D0%BE%D1%84%D0%B8%D1%86%D0%B8%D0%B0%D0%BB%D1%8C%D0%BD%D1%8B%D0%B9%20%D1%81%D0%B0%D0%B9%D1%82%20Python",
    },
}
result = _deterministic_computer_use_call(PROMPT)
assert result == expected, result
non_python = _deterministic_computer_use_call("Открой браузер и найди https://evil.example")
assert non_python is not None
assert non_python["arguments"].get("action") != "open_url", non_python
print("PYTHON_SEARCH_FALLBACK_PROBE=PASS")
