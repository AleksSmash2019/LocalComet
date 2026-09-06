#!/usr/bin/env python3
"""Verify the ModelFit WebviewWindow actually creates an OS window (hidden desktop)."""
import ctypes, json, subprocess, sys, time
import ctypes.wintypes as wintypes
sys.path.insert(0, 'tools')
from sweep_installed_release import (MiniWs, CdpSession, cdp_json, cdp_ready,
                                     launch, user32, CDP_PORT, DESKTOP_NAME)

DESKTOP_READOBJECTS = 0x0001
DESKTOP_ENUMERATE = 0x0040
user32.OpenDesktopW.restype = wintypes.HANDLE
user32.OpenDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
user32.SetThreadDesktop.restype = wintypes.BOOL
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW = user32.GetWindowTextW
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

pid, desktop = launch()
found = []
try:
    assert cdp_ready(), 'cdp not ready'
    page = None
    for _ in range(60):
        for t in cdp_json('/json/list'):
            if t.get('type') == 'page' and 'tauri.localhost' in str(t.get('url', '')):
                page = t
                break
        if page:
            break
        time.sleep(1.0)
    ws = MiniWs(CDP_PORT, page['webSocketDebuggerUrl'].split(f'127.0.0.1:{CDP_PORT}', 1)[1])
    s = CdpSession(ws)
    s.command('Runtime.enable')
    s.command('Runtime.evaluate', {
        'expression': "(() => { const b=[...document.querySelectorAll('button')].find(x=>(x.getAttribute('aria-label')||'').includes('Подобрать')); if(b){b.click(); return 'clicked';} return 'not-found'; })()",
        'returnByValue': True})
    time.sleep(5.0)
    # Attach this thread to the hidden desktop so EnumWindows sees its windows
    handle = user32.OpenDesktopW(DESKTOP_NAME, 0, False, DESKTOP_READOBJECTS | DESKTOP_ENUMERATE)
    if handle:
        attached = user32.SetThreadDesktop(handle)
        print('attached:', bool(attached))
        @WNDENUMPROC
        def cb(hwnd, lparam):
            wpid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
            if wpid.value == pid:
                length = user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                found.append((int(hwnd), buf.value))
            return True
        user32.EnumWindows(cb, 0)
        user32.CloseDesktop(handle)
    else:
        print('OpenDesktopW failed:', ctypes.get_last_error())
    print('windows of pid:', found)
    print('has modelfit hwnd:', any('ModelFit' in (t or '') for _, t in found))
    ws.close()
finally:
    subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True)
    user32.CloseDesktop(desktop)
