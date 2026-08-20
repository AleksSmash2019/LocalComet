from __future__ import annotations

import ctypes
import os
import signal
import sys
import time


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: graceful_stop_console.py PID")
    pid = int(sys.argv[1])
    delivered = False
    try:
        os.kill(pid, signal.CTRL_BREAK_EVENT)
        delivered = True
    except (OSError, AttributeError, SystemError) as exc:
        print(f"os_kill_ctrl_break_failed={exc}")
    if not delivered:
        kernel32 = ctypes.windll.kernel32
        if kernel32.AttachConsole(pid):
            try:
                delivered = bool(kernel32.GenerateConsoleCtrlEvent(1, 0))
            finally:
                kernel32.FreeConsole()
    print(f"ctrl_break_delivered={delivered} pid={pid}")
    time.sleep(3)
