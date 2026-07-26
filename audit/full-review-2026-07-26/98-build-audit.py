from __future__ import annotations

import datetime as dt
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
EXCLUDED_DIRS = {".git", ".svelte-kit", "node_modules", "target", "dist", "build"}
SOURCE_SUFFIXES = {
    ".rs", ".svelte", ".ts", ".js", ".json", ".toml", ".md", ".css",
    ".html", ".bat", ".ps1", ".py", ".yml", ".yaml", ".lock",
}
OMIT_LOCK_CONTENT = {"Cargo.lock", "package-lock.json"}
LANGUAGES = {
    ".rs": "rust", ".svelte": "svelte", ".ts": "typescript", ".js": "javascript",
    ".json": "json", ".toml": "toml", ".md": "markdown", ".css": "css",
    ".html": "html", ".bat": "bat", ".ps1": "powershell", ".py": "python",
    ".yml": "yaml", ".yaml": "yaml", ".lock": "text",
}
REDACTION_PATTERNS = (
    re.compile(r"ntn_[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?<![A-Za-z])sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"(?i)Bearer\s+(?!\[REDACTED\])[^\s\"']+"),
    re.compile(
        r"(?i)([\"']?(?:api[_-]?key|access[_-]?token|auth[_-]?token|authtoken|password|passwd|client[_-]?secret)"
        r"[\"']?\s*[:=]\s*)([\"'])(?!\[REDACTED\])([^\"']+)([\"'])"
    ),
    re.compile(r"(?i)(https?://[^\s:/@]+:)([^\s/@]+)(@)"),
)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def redact(text: str, source: str) -> str:
    output: list[str] = []
    for line_number, line in enumerate(text.splitlines(keepends=True), 1):
        marker = f"[REDACTED: secret in {source}:{line_number}]"
        line = REDACTION_PATTERNS[0].sub(lambda _match: marker, line)
        line = REDACTION_PATTERNS[1].sub(lambda _match: marker, line)
        line = REDACTION_PATTERNS[2].sub(lambda _match: f"Bearer {marker}", line)
        line = REDACTION_PATTERNS[3].sub(lambda match: f"{match.group(1)}{match.group(2)}{marker}{match.group(4)}", line)
        line = REDACTION_PATTERNS[4].sub(lambda match: f"{match.group(1)}{marker}{match.group(3)}", line)
        output.append(line)
    return "".join(output)


def write_text(name: str, text: str) -> None:
    (OUT / name).write_text(text, encoding="utf-8", newline="\n")


def run(command: list[str], cwd: Path = ROOT, timeout: int = 3600) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    return completed.returncode, completed.stdout.decode("utf-8", errors="replace")


def iter_repository_files() -> list[Path]:
    files: list[Path] = []
    for base, dirs, names in os.walk(ROOT):
        base_path = Path(base)
        dirs[:] = sorted(
            directory for directory in dirs
            if directory not in EXCLUDED_DIRS and (base_path / directory).resolve() != OUT.resolve()
        )
        for name in sorted(names):
            path = base_path / name
            if path.resolve() == (ROOT / "audit" / "LocalComet-full-review-2026-07-26.zip").resolve():
                continue
            files.append(path)
    return sorted(files, key=lambda path: rel(path).lower())


def build_tree() -> None:
    lines = [
        f"Generated: {now()}",
        "Excluded directories: node_modules, target, .git, .svelte-kit, dist, build",
        "Excluded from self-enumeration: audit/full-review-2026-07-26 and final ZIP",
        "Format: relative path<TAB>size in bytes",
        "",
    ]
    for path in iter_repository_files():
        try:
            size = path.stat().st_size
        except OSError as error:
            lines.append(f"{rel(path)}\t[STAT ERROR: {error}]")
        else:
            lines.append(f"{rel(path)}\t{size}")
    write_text("01-tree.txt", "\n".join(lines) + "\n")


def build_git_state() -> None:
    commands = [
        ("git status --short --branch", ["git", "status", "--short", "--branch"]),
        ("git log -30 --oneline", ["git", "log", "-30", "--oneline"]),
        ("git diff --stat", ["git", "diff", "--stat"]),
        ("git diff --cached --stat", ["git", "diff", "--cached", "--stat"]),
        ("git diff (unstaged tracked changes)", ["git", "diff", "--no-ext-diff", "--binary"]),
        ("git diff --cached (staged tracked changes)", ["git", "diff", "--cached", "--no-ext-diff", "--binary"]),
        ("git diff HEAD (combined tracked changes)", ["git", "diff", "HEAD", "--no-ext-diff", "--binary"]),
        ("untracked files: git ls-files --others --exclude-standard", ["git", "ls-files", "--others", "--exclude-standard"]),
        ("git stash list", ["git", "stash", "list"]),
    ]
    sections = [f"Generated: {now()}\n"]
    for title, command in commands:
        code, output = run(command)
        sections.append(f"\n===== {title} =====\nexit_code={code}\n")
        sections.append(redact(output, f"02-git-state.txt/{title}"))
        if output and not output.endswith("\n"):
            sections.append("\n")
    write_text("02-git-state.txt", "".join(sections))


def split_large_text(text: str, limit: int = 200_000) -> list[str]:
    if len(text.encode("utf-8")) <= limit:
        return [text]
    parts: list[str] = []
    current: list[str] = []
    current_size = 0
    for line in text.splitlines(keepends=True):
        encoded = line.encode("utf-8")
        if current and current_size + len(encoded) > limit:
            parts.append("".join(current))
            current = []
            current_size = 0
        if len(encoded) > limit:
            for start in range(0, len(line), 50_000):
                chunk = line[start:start + 50_000]
                parts.append(chunk)
        else:
            current.append(line)
            current_size += len(encoded)
    if current:
        parts.append("".join(current))
    return parts


def fence_for(text: str) -> str:
    longest = max((len(match.group(0)) for match in re.finditer(r"`+", text)), default=0)
    return "`" * max(4, longest + 1)


def build_sources() -> None:
    entries: list[str] = []
    omitted: list[str] = []
    for path in iter_repository_files():
        if path.name in OMIT_LOCK_CONTENT:
            omitted.append(f"- `{rel(path)}`: {path.stat().st_size} bytes; content intentionally omitted by request.")
            continue
        if path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        raw = path.read_bytes()
        try:
            original = raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                original = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                omitted.append(f"- `{rel(path)}`: {len(raw)} bytes; omitted because it is not UTF-8 text.")
                continue
        line_count = len(original.splitlines())
        sanitized = redact(original, rel(path))
        parts = split_large_text(sanitized)
        for index, part in enumerate(parts, 1):
            part_label = f"; часть {index}/{len(parts)}" if len(parts) > 1 else ""
            fence = fence_for(part)
            language = LANGUAGES.get(path.suffix.lower(), "text")
            entries.append(
                f"### ПУТЬ: {rel(path)} ({line_count} строк, {len(raw)} байт{part_label})\n\n"
                f"{fence}{language}\n{part}{'' if part.endswith(chr(10)) else chr(10)}{fence}\n\n"
            )
    intro = (
        "# Полный исходный код\n\n"
        f"Сформировано: {now()}. Файлы идут в лексикографическом порядке. "
        "Содержимое секретов заменено маркерами `[REDACTED: secret in путь:строка]`.\n\n"
        "## Lock-файлы и текстовые исключения\n\n"
        + ("\n".join(omitted) if omitted else "Нет.") + "\n\n"
    )
    documents: list[str] = []
    current = intro
    for entry in entries:
        if len(current.encode("utf-8")) >= 300_000 and current != intro:
            documents.append(current)
            current = "# Полный исходный код (продолжение)\n\n"
        current += entry
    documents.append(current)
    for index, document in enumerate(documents, 1):
        write_text(f"10-source-{index:02d}.md", document)


def build_gates() -> None:
    frontend = ROOT / "desktop" / "localcomet-desktop"
    rust = frontend / "src-tauri"
    gates = [
        ("cargo check", ["cargo", "check"], rust),
        ("cargo test", ["cargo", "test"], rust),
        ("cargo fmt --check", ["cargo", "fmt", "--check"], rust),
        ("cargo clippy --all-targets --all-features -- -D warnings", ["cargo", "clippy", "--all-targets", "--all-features", "--", "-D", "warnings"], rust),
        ("npm run build", ["npm.cmd", "run", "build"], frontend),
        ("npm run check", ["npm.cmd", "run", "check"], frontend),
        ("npm test", ["npm.cmd", "test"], frontend),
        ("python tests/test_trust_chain_invariants.py", [sys.executable, "tests/test_trust_chain_invariants.py"], ROOT),
        ("python scripts/check_command_parity.py", [sys.executable, "scripts/check_command_parity.py"], ROOT),
        ("python scripts/check_tool_risk_registry.py", [sys.executable, "scripts/check_tool_risk_registry.py"], ROOT),
        ("python scripts/check_ui_fake_state.py", [sys.executable, "scripts/check_ui_fake_state.py"], ROOT),
        ("python scripts/refresh_evidence.py", [sys.executable, "scripts/refresh_evidence.py"], ROOT),
        ("python scripts/check_evidence_provenance.py", [sys.executable, "scripts/check_evidence_provenance.py"], ROOT),
    ]
    write_text("30-gates.txt", f"Gate run started: {now()}\nRepository: {ROOT}\n\n")
    with (OUT / "30-gates.txt").open("a", encoding="utf-8", newline="\n") as stream:
        for title, command, cwd in gates:
            started = now()
            stream.write(f"===== {title} =====\nstarted={started}\ncwd={cwd}\ncommand={' '.join(command)}\n")
            stream.flush()
            try:
                code, output = run(command, cwd, timeout=7200)
            except subprocess.TimeoutExpired as error:
                code = 124
                output = (error.stdout or b"").decode("utf-8", errors="replace") + "\n[TIMEOUT]\n"
            stream.write(redact(output, f"30-gates.txt/{title}"))
            if output and not output.endswith("\n"):
                stream.write("\n")
            stream.write(f"exit_code={code}\nfinished={now()}\n\n")
            stream.flush()


def tail_text(path: Path, count: int = 200) -> str:
    if not path.exists():
        return f"[FILE NOT FOUND: {path}]\n"
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    return "\n".join(lines[-count:]) + ("\n" if lines else "")


def build_logs() -> None:
    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    paths = [
        local_app_data / "LocalComet" / "logs" / "startup.log",
        local_app_data / "LocalComet" / "logs" / "managed-runtime.log",
    ]
    sections = [f"Generated: {now()}\nLast 200 lines per file. Logs are non-authoritative evidence.\n"]
    for path in paths:
        sections.append(f"\n===== {path} =====\n")
        sections.append(redact(tail_text(path), str(path)))
    write_text("50-logs.txt", "".join(sections))


def build_versions() -> None:
    commands = [
        ("node --version", ["node", "--version"]),
        ("npm --version", ["npm.cmd", "--version"]),
        ("rustc --version --verbose", ["rustc", "--version", "--verbose"]),
        ("cargo --version --verbose", ["cargo", "--version", "--verbose"]),
        ("cargo tauri --version", ["cargo", "tauri", "--version"]),
        ("python --version", [sys.executable, "--version"]),
    ]
    sections = ["# Сборка и запуск\n\n", f"Версии получены: {now()}\n\n", "## Версии инструментов\n\n```text\n"]
    for title, command in commands:
        code, output = run(command, ROOT, timeout=120)
        sections.append(f"$ {title}\n{output}exit_code={code}\n")
    sections.append("```\n")
    write_text("60-build-run-versions.tmp", redact("".join(sections), "60-build-run.md/versions"))


def build_manifest() -> None:
    entries = []
    for path in sorted(OUT.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file() or path.name == "99-manifest.sha256":
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append(f"{digest}  {path.name}")
    header = (
        "# SHA-256 manifest generated " + now() + "\n"
        "# Every payload file is listed. This manifest cannot include a stable hash of itself.\n"
    )
    write_text("99-manifest.sha256", header + "\n".join(entries) + "\n")


def clean_gate_ansi() -> None:
    path = OUT / "30-gates.txt"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    path.write_text(text, encoding="utf-8", newline="\n")


MODES = {
    "tree": build_tree,
    "git": build_git_state,
    "sources": build_sources,
    "gates": build_gates,
    "logs": build_logs,
    "versions": build_versions,
    "clean-gates": clean_gate_ansi,
    "manifest": build_manifest,
}


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in MODES:
        raise SystemExit(f"usage: {Path(__file__).name} {{{'|'.join(MODES)}}}")
    MODES[sys.argv[1]]()
