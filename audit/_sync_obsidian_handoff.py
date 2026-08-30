from pathlib import Path

repo = Path(r"C:\Users\DNS\Documents\LocalComet-build-week-clean")
vault = Path(r"C:\Users\DNS\Documents\LocalCometVault")
src = repo / "audit" / "HANDOFF_2026-08-28_NEXT_CODER_RU.md"
dst = vault / "99 Handoffs" / "HANDOFF_2026-08-28_LOCALCOMET_NEXT_CODER.md"
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_bytes(src.read_bytes())
status = vault / "Projects" / "LocalComet" / "Status.md"
marker = "## 2026-08-28 — handoff после коммита B3 cancellation seam"
entry = """\n\n## 2026-08-28 — handoff после коммита B3 cancellation seam\n\nСоздан handoff для следующего кодера: [[99 Handoffs/HANDOFF_2026-08-28_LOCALCOMET_NEXT_CODER]]. Текущий коммит `a85bd2b` в ветке `feat/up00-wp01-windows-one-click-launch`; development-запуск работает через `py tools\\launch_localcomet_dev.py`. Перед коммитом подтверждены `npm run check` (0 errors/0 warnings), Python `py_compile` и focused hidden-evidence tests (25 passed). Native B3 дошёл до leased continuation, positive Rust revoke и terminal cancellation, но post-revoke replay proof остаётся `PENDING_TERMINAL` (`replay_rejected=false`). Остальной dirty WIP сохранён намеренно.\n"""
old = status.read_text(encoding="utf-8")
if marker not in old:
    status.write_text(old + entry, encoding="utf-8")
print(f"HANDOFF_EXISTS={dst.is_file()} BYTES={dst.stat().st_size}")
print(f"STATUS_MARKER={marker in status.read_text(encoding='utf-8')}")
