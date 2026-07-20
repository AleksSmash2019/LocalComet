from __future__ import annotations

import json
import struct
import sys
import time


def main() -> int:
    message = {
        "type": "hello",
        "payload": {"role": "python_core"},
    }
    body = json.dumps(message, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(struct.pack(">I", len(body)) + body)
    sys.stdout.buffer.flush()
    time.sleep(30)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
