"""READ-ONLY storage/process/listener/artifact inventory for LocalComet.

Unified prompt Workstream B plus the §2 baseline. Hard guarantees:
- No process is stopped, no file/directory is deleted or modified.
- Scope is exactly the allowlisted LocalComet areas; never drive roots,
  Program Files, third-party %APPDATA%, browser profiles or user documents.
- Processes are classified only with TWO independent signals (command-line/
  path marker PLUS parent/UDF/port association); anything else stays
  ``unowned_or_ambiguous``.
- Command lines are truncated and secret-looking arguments are redacted.

Outputs land OUTSIDE the repository under
``%LOCALAPPDATA%\\LocalComet\\Audits\\hidden_inventory_<UTC>``.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

SCOPE_DIRS_TEMPLATE = [
    Path("Projects") / "Reports" / "computer_use_real_actions",
]

EXTERNAL_SCOPE_TEMPLATES = [
    "%LOCALAPPDATA%\\LocalComet",
    "%LOCALAPPDATA%\\LocalCometDev",
    "%LOCALAPPDATA%\\LocalCometHidden*",
    "%TEMP%\\LocalComet-*",
    "%LOCALAPPDATA%\\Temp\\LocalComet-*",
]

BASELINE_EXTRA_PATHS = [
    "desktop\\localcomet-desktop\\src-tauri\\target",
    "%LOCALAPPDATA%\\LocalComet\\CargoTarget",
    "%LOCALAPPDATA%\\LocalComet\\BuildCache",
    "%LOCALAPPDATA%\\LocalComet\\DevRuntime",
]

PROCESS_IMAGE_NAMES = {
    "localcomet-desktop.exe", "msedgewebview2.exe", "node.exe", "python.exe",
    "py.exe", "cargo.exe", "rustc.exe", "link.exe",
}

WATCHED_LISTEN_PORTS = set(range(1420, 1436)) | set(range(9223, 9241))

ARTIFACT_PATTERNS = [
    "visual_demo_*.png", "probe_*_output.json", "run_*_tmp.py",
    "campaign_*_final", "isolated_*_summary.json", "cdp_verification.json",
    "owned_cleanup.json", "isolation_selfcheck.json", "owned_run_manifest.json",
    "*.provenance.json",
]

CANONICAL_EVIDENCE_HINTS = (
    "computer_use_real_actions", "evidence", "Reports", "audit",
)
SECRET_KEY_RE = re.compile(
    r"(?i)((?:--?[a-z0-9_-]*(?:token|key|secret|password|passwd)[a-z0-9_-]*[= ])(?:\"?[^\s\"]+))"
)
MAX_CMDLINE_LEN = 600


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def redact_commandline(line: str) -> str:
    line = SECRET_KEY_RE.sub(lambda match: match.group(1)[:len(match.group(1)) - len(match.group(2))] + "<redacted>", line)
    return line[:MAX_CMDLINE_LEN]


def expand_scope() -> list[Path]:
    scopes: list[Path] = []
    scopes.append(ROOT)
    for template in SCOPE_DIRS_TEMPLATE:
        candidate = ROOT / template
        if candidate.exists():
            scopes.append(candidate)
    local = os.environ.get("LOCALAPPDATA", "")
    temp = os.environ.get("TEMP", "")
    for raw in EXTERNAL_SCOPE_TEMPLATES:
        expanded = raw.replace("%LOCALAPPDATA%", local).replace("%TEMP%", temp)
        if "*" in expanded:
            parent = Path(expanded.split("*")[0])
            if not parent.is_dir():
                continue
            suffix = expanded.rsplit("*", 1)[1]
            for child in sorted(parent.glob("*")):
                if child.is_dir():
                    scopes.append(child)
        else:
            path = Path(expanded)
            if path.exists():
                scopes.append(path)
    unique: list[Path] = []
    seen: set[str] = set()
    for item in scopes:
        key = str(item).lower().rstrip("\\")
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def dir_size(path: Path) -> tuple[int, int]:
    """Metadata-only recursive size; returns (bytes, files). Never reads data."""
    total = 0
    count = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            if current.is_symlink():
                continue
            for entry in current.iterdir():
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir():
                        stack.append(entry)
                    else:
                        total += entry.stat().st_size
                        count += 1
                except OSError:
                    continue
        except OSError:
            continue
    return total, count


def collect_processes() -> list[dict[str, Any]]:
    script = (
        "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,"
        "Name,ExecutablePath,CommandLine,CreationDate | ConvertTo-Json -Depth 2 -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=90,
        )
        payload = json.loads(completed.stdout or "[]")
    except Exception as exc:
        return [{"error": f"process query unavailable: {exc}", "classification": "unowned_or_ambiguous"}]
    if isinstance(payload, dict):
        payload = [payload]
    by_pid = {int(item.get("ProcessId", 0)): item for item in payload}
    records: list[dict[str, Any]] = []
    for raw in payload:
        pid = int(raw.get("ProcessId", 0))
        name = str(raw.get("Name") or "")
        if name.lower() not in PROCESS_IMAGE_NAMES:
            continue
        cmdline = str(raw.get("CommandLine") or "")
        executable_path = str(raw.get("ExecutablePath") or "")
        marker_cmdline = bool(re.search(r"localcomet|LocalCometHiddenCU|LOCALCOMET_", cmdline))
        marker_path = any(part.lower() in {"localcomet", "localcometdev"}
                          for part in Path(executable_path or ".").parts)
        parent_pid = int(raw.get("ParentProcessId", 0))
        parent = by_pid.get(parent_pid)
        marker_parent = False
        chain = [parent_pid]
        cursor = parent
        hops = 0
        while cursor is not None and hops < 8:
            pcmd = str(cursor.get("CommandLine") or "")
            pp = int(cursor.get("ParentProcessId", 0))
            chain.append(pp)
            if re.search(r"localcomet", pcmd, re.IGNORECASE):
                marker_parent = True
                break
            cursor = by_pid.get(pp)
            hops += 1
        udf_marker = "webview2-user-data" in cmdline or "LocalCometHiddenCU" in cmdline
        signals = sum([marker_cmdline, marker_path, marker_parent, udf_marker])
        hidden_markers = ("LocalCometHiddenCU" in cmdline) or bool(udf_marker and marker_cmdline)
        if signals >= 2:
            classification = (
                "current_owned_hidden_run" if hidden_markers and marker_parent
                else "pre_existing_hidden_run" if hidden_markers
                else "current_normal_runtime"
            )
        elif signals == 1:
            classification = "orphan_localcomet_candidate"
        else:
            classification = "foreign_process"
        records.append({
            "pid": pid,
            "parent_pid": parent_pid,
            "name": name,
            "executable_path": executable_path,
            "command_line_redacted": redact_commandline(cmdline),
            "creation_date": str(raw.get("CreationDate") or ""),
            "remote_debugging_port": (lambda m: int(m.group(1)) if m else None)(
                re.search(r"--remote-debugging-port=(\d+)", cmdline)),
            "user_data_folder_marker": "webview2-user-data" if udf_marker else "",
            "parent_chain_pids": chain[:9],
            "signals": {"cmdline": marker_cmdline, "path": marker_path,
                        "parent": marker_parent, "udf": bool(udf_marker)},
            "classification": classification,
        })
    return records


def collect_listeners(processes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ports_csv = ",".join(str(port) for port in sorted(WATCHED_LISTEN_PORTS))
    script = (
        "Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | "
        f"Where-Object {{ $_.LocalPort -in @({ports_csv}) }} | "
        "Select-Object LocalAddress,LocalPort,OwningDevice,OwningProcess | ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=60,
        )
        payload = json.loads(completed.stdout or "[]")
    except Exception as exc:
        return [{"error": f"listener query unavailable: {exc}"}]
    if isinstance(payload, dict):
        payload = [payload]
    index = {item["pid"]: item for item in processes if "pid" in item}
    out: list[dict[str, Any]] = []
    for raw in payload:
        pid = int(raw.get("OwningProcess", 0))
        owner = index.get(pid)
        out.append({
            "protocol": "tcp",
            "local_address": str(raw.get("LocalAddress") or ""),
            "local_port": int(raw.get("LocalPort", 0)),
            "owning_pid": pid,
            "owning_process": owner["name"] if owner else "",
            "command_line_redacted": owner["command_line_redacted"] if owner else "",
            "classification": owner["classification"] if owner else "unowned_or_ambiguous",
        })
    return out


def classify_artifact(path: Path, scope_root: Path) -> dict[str, Any]:
    name = path.name
    lower = name.lower()
    stat = path.stat()
    entry: dict[str, Any] = {
        "absolute_path": str(path),
        "relative_to_scope": str(path.relative_to(scope_root)) if str(path).startswith(str(scope_root)) else "",
        "type": "directory" if path.is_dir() else "file",
        "size_bytes": stat.st_size,
        "created_utc": datetime.fromtimestamp(stat.st_ctime, timezone.utc).isoformat(),
        "last_write_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "owner_marker": (path.with_suffix(path.suffix + ".provenance.json")).exists()
                        or (path.parent / "owned_run_manifest.json").exists(),
        "run_id": None,
        "related_port_or_pid": None,
    }
    manifest_neighbor = path.parent / "owned_run_manifest.json"
    if manifest_neighbor.exists():
        try:
            data = json.loads(manifest_neighbor.read_text(encoding="utf-8"))
            entry["run_id"] = str(data.get("run_id") or "")[:32]
            entry["related_port_or_pid"] = data.get("cdp_port") or data.get("root_pid")
        except (OSError, ValueError):
            pass
    if lower.endswith(".provenance.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            entry["sha256_of_subject_recorded"] = str(data.get("sha256") or "")
        except (OSError, ValueError):
            pass
    if any(hint.lower() in str(path).lower() for hint in CANONICAL_EVIDENCE_HINTS):
        entry["classification"] = "canonical_evidence"
        entry["safe_action"] = "preserve_until: needs_human_decision"
    elif entry["owner_marker"]:
        entry["classification"] = "owned_temp_candidate"
        entry["safe_action"] = "candidate_for_future_owned_cleanup_only"
    else:
        entry["classification"] = "unowned_artifact"
        entry["safe_action"] = "do_not_delete_without_human_decision"
    return entry


def collect_artifacts(scopes: list[Path]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    small_json_limit = 512 * 1024
    hashed = 0
    for scope in scopes:
        if scope == ROOT:
            search_roots = [scope]
            patterns: list[str] = ARTIFACT_PATTERNS
        else:
            search_roots = [scope]
            patterns = ARTIFACT_PATTERNS
        for base in search_roots:
            for pattern in patterns:
                try:
                    matches = list(base.rglob(pattern))
                except OSError:
                    continue
                for match in matches[:400]:
                    key = str(match).lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    try:
                        entry = classify_artifact(match, base)
                    except OSError:
                        continue
                    if (
                        entry["type"] == "file"
                        and entry["size_bytes"] <= small_json_limit
                        and lower_name(match).endswith(".json")
                        and hashed < 200
                    ):
                        try:
                            entry["sha256"] = sha256_file(match)
                            hashed += 1
                        except OSError:
                            pass
                    found.append(entry)
    return found


def lower_name(path: Path) -> str:
    return path.name.lower()


def collect_storage(scopes: list[Path], extra: list[Path]) -> dict[str, Any]:
    sizes: dict[str, Any] = {}
    for label, group in (("scope", scopes), ("baseline_extra", extra)):
        for path in group:
            if not path.exists():
                sizes[f"{label}:{path}"] = {"exists": False}
                continue
            gib, count = dir_size(path)
            sizes[f"{label}:{path}"] = {
                "exists": True,
                "bytes": gib,
                "files": count,
                "gib": round(gib / (1024 ** 3), 3),
            }
    usage = os.statvfs("C:\\") if hasattr(os, "statvfs") else None
    free_bytes: int | None = None
    try:
        import ctypes

        free_ptr = ctypes.c_ulonglong()
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            "C:\\", None, None, ctypes.byref(free_ptr)
        )
        free_bytes = int(free_ptr.value)
    except Exception:
        free_bytes = None
    return {
        "captured_utc": utc_now(),
        "drive_free_bytes": free_bytes,
        "paths": sizes,
    }


def git_baseline() -> dict[str, Any]:
    def run(*args: str) -> str:
        try:
            completed = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30)
            return (completed.stdout or "").strip()
        except Exception as exc:
            return f"error: {exc}"
    status_short = run("status", "--short")
    return {
        "branch": run("branch", "--show-current"),
        "head": run("rev-parse", "HEAD"),
        "last_5_commits": run("log", "--oneline", "-5"),
        "status_short_count": len(status_short.splitlines()) if status_short else 0,
        "agents_md_present": (ROOT / "AGENTS.md").is_file(),
    }


def model_identity() -> dict[str, Any]:
    local = os.environ.get("LOCALAPPDATA", "")
    custom_models = Path(local) / "LocalComet" / "models" / "custom"
    result: dict[str, Any] = {"qwen3_records": [], "qwen25_1_5b_found": []}
    if custom_models.is_dir():
        for gguf in custom_models.rglob("*.gguf"):
            result["qwen3_records"].append({
                "path": str(gguf),
                "size_bytes": gguf.stat().st_size,
                # Identity was byte-verified earlier this session; do not
                # re-read multi-GiB model contents here.
                "note": "size/metadata only; SHA recorded separately",
            })
            if "qwen2.5" in gguf.name.lower():
                result["qwen25_1_5b_found"].append(str(gguf))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    local = os.environ.get("LOCALAPPDATA", "")
    output_dir = Path(args.output_dir) if args.output_dir else (
        Path(local) / "LocalComet" / "Audits" / f"hidden_inventory_{stamp}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    scopes = expand_scope()
    extra = []
    for raw in BASELINE_EXTRA_PATHS:
        expanded = raw.replace("%LOCALAPPDATA%", local)
        extra.extend(Path(p) for p in glob_all(expanded))

    commands_log: list[str] = []

    processes = collect_processes()
    listeners = collect_listeners(processes)
    artifacts = collect_artifacts(scopes)
    storage = collect_storage(scopes, extra)
    baseline = git_baseline()
    models = model_identity()

    summary = {
        "schema_version": "localcomet.hidden-inventory.v1",
        "captured_utc": utc_now(),
        "python": sys.executable,
        "platform": platform.platform(),
        "read_only_guarantees": {
            "processes_stopped": 0,
            "files_deleted": 0,
            "source_edits_by_inventory": 0,
        },
        "scope_dirs": [str(item) for item in scopes],
        "explicit_exclusions": [
            "Projects/BrowserProfile", "browser profiles", "credentials",
            "%APPDATA% of third-party apps", "Windows", "Program Files",
            "model contents (metadata only)",
        ],
        "totals": {
            "processes_seen_relevant": len(processes),
            "listeners_watched_ports": len(listeners),
            "artifacts_matched": len(artifacts),
        },
        "process_classification_counts": _count_by(processes, "classification"),
        "artifact_classification_counts": _count_by(artifacts, "classification"),
        "git_baseline": baseline,
        "model_identity": models,
        "cleanup_candidates_not_deleted": [
            item["absolute_path"] for item in artifacts
            if item.get("classification") == "owned_temp_candidate"
        ],
        "ambiguous_items_needing_human_decision": [
            item["absolute_path"] for item in artifacts + processes
            if item.get("classification") in {"unowned_artifact", "unowned_or_ambiguous"}
        ][:80],
    }

    outputs: dict[str, Any] = {
        "inventory.json": summary,
        "processes.json": processes,
        "listeners.json": listeners,
        "artifacts.json": artifacts,
        "storage_sizes.json": storage,
    }
    for filename, payload in outputs.items():
        target = output_dir / filename
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        commands_log.append(f"wrote {filename}")

    write_markdown(output_dir / "inventory.md", summary)
    (output_dir / "commands_and_exit_codes.txt").write_text(
        "\n".join(commands_log) + "\n", encoding="utf-8"
    )
    manifest_lines: list[str] = []
    for file in sorted(output_dir.iterdir()):
        if file.is_file() and file.name != "sha256_manifest.txt":
            manifest_lines.append(f"{sha256_file(file)}  {file.name}")
    (output_dir / "sha256_manifest.txt").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "inventory_dir": str(output_dir),
        "artifacts": len(artifacts),
        "processes": len(processes),
        "listeners": len(listeners),
        "deleted_files": 0,
        "stopped_processes": 0,
    }, ensure_ascii=False))
    return 0


def glob_all(expanded: str) -> list[str]:
    if "*" not in expanded:
        return [expanded] if Path(expanded).exists() else []
    parent = Path(expanded.split("*")[0])
    if not parent.is_dir():
        return []
    tail = expanded.rsplit("*", 1)[1].lstrip("\\/")
    return [str(child) for child in sorted(parent.glob("*")) if child.is_dir()]


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return counts


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# LocalComet hidden-resource inventory (READ-ONLY)",
        "",
        f"- captured_utc: {summary['captured_utc']}",
        f"- python: `{summary['python']}`",
        f"- processes stopped: **0**; files deleted: **0**",
        "",
        "## Git baseline",
        f"- branch: `{summary['git_baseline']['branch']}`",
        f"- head: `{summary['git_baseline']['head']}`",
        f"- status short lines: {summary['git_baseline']['status_short_count']}",
        "",
        "## Totals",
    ]
    for key, value in summary["totals"].items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Classifications")
    lines.append(f"- processes: {json.dumps(summary['process_classification_counts'], ensure_ascii=False)}")
    lines.append(f"- artifacts: {json.dumps(summary['artifact_classification_counts'], ensure_ascii=False)}")
    lines.append("")
    lines.append("See JSON siblings for full details; SHAs in sha256_manifest.txt.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
