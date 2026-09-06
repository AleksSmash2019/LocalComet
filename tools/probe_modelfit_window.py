#!/usr/bin/env python3
"""Probe: does clicking ModelFit open the dedicated window in the installed app?"""
import json, os, subprocess, sys, time
sys.path.insert(0, 'tools')
from sweep_installed_release import (MiniWs, CdpSession, cdp_json, cdp_ready,
                                     launch, user32, CDP_PORT, WORKSPACE_SNIPPET)

pid, desktop = launch()
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
    s.command('Page.enable')
    s.command('Runtime.evaluate', {
        'expression': "(() => { const k='localcomet.ui.preferences.v1'; const v=JSON.parse(localStorage.getItem(k)||'{}'); v.accentColor='#8B5CF6'; localStorage.setItem(k, JSON.stringify(v)); return 'accent-set'; })()",
        'returnByValue': True})
    s.command('Runtime.evaluate', {'expression': f"({WORKSPACE_SNIPPET})('modelfit')", 'returnByValue': True})
    mf = []
    for _ in range(20):
        time.sleep(1.0)
        targets = cdp_json('/json/list')
        mf = [t for t in targets
              if 'modelfit' in str(t.get('url', '')) or 'ModelFit' in str(t.get('title', ''))]
        if mf:
            break
    print('modelfit window targets:', [{'url': t.get('url'), 'title': t.get('title')} for t in mf])
    if mf:
        ws2 = MiniWs(CDP_PORT, mf[0]['webSocketDebuggerUrl'].split(f'127.0.0.1:{CDP_PORT}', 1)[1])
        s2 = CdpSession(ws2)
        s2.command('Runtime.enable')
        accent = s2.command('Runtime.evaluate', {
            'expression': "getComputedStyle(document.documentElement).getPropertyValue('--mf-accent').trim()",
            'returnByValue': True})
        doc = s2.command('Runtime.evaluate', {
            'expression': "document.title + ' | bytes=' + document.body.innerHTML.length",
            'returnByValue': True})
        print('accent in window:', accent.get('result', {}).get('result', {}).get('value'))
        print('window doc:', doc.get('result', {}).get('result', {}).get('value'))
        ws2.close()
    ws.close()
finally:
    subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True)
    user32.CloseDesktop(desktop)
