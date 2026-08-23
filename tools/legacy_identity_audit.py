"""READ-ONLY legacy-artifact identity ledger (unified prompt Part B).

For every pre-existing LocalComet-related object this tool writes an EXTERNAL
JSON identity record and never touches the object itself: no marker inside,
no rename, no move, no copy, no delete. Historical association is derived
only from independent signals (owned report root, sibling manifests,
harness-vocabulary names, plain-text content sniff); a single signal can
never prove ownership, and ``cleanup_eligible`` is ALWAYS false for
pre-existing objects even at association strength ``strong``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

REPORT_ROOT = ROOT / "Projects" / "Reports" / "computer_use_real_actions"

REPO_ROOT_GROUPS = [
    "visual_demo_*.png",
    "probe_open_app_output.json",
    "probe_open_app_tmp.py",
    "run_*_tmp.py",
]

TOOLS_PROBE_GROUP = [
    "capture_tauri_window.py", "hidden_ui_actions.py", "hide_tauri_window.py",
    "probe_drawer_steady_state.py", "probe_hidden_localcomet_ui.py",
    "probe_tauri_uia.py", "run_1000_computer_use_campaign_tmp.py",
    "run_1000_real_tauri_ui_attempts.py", "run_200_scenarios_tmp.py",
    "set_tauri_window_visibility.py", "tauri_uia_user_actions.py",
]

AUDIT_HINTS = ("localcomet", "isolated_hidden_desktop", "ISOLATED_CDP_PORT",
               "LC_HIDDEN_DESKTOP_NAME", "computer_use")

SCHEMA = "localcomet.legacy-identity.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_small(path: Path, limit: int = 512 * 1024) -> str | None:
    try:
        if path.stat().st_size > limit:
            return None
    except OSError:
        return None
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 64), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def sniff_text(path: Path) -> bool:
    """True when small textual content mentions the LocalComet vocabulary."""
    try:
        if path.suffix.lower() not in {".py", ".json", ".txt", ".md", ".log"}:
            return False
        if path.stat().st_size > 256 * 1024:
            return False
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    lowered = text.lower()
    return any(hint.lower() in lowered for hint in AUDIT_HINTS)


def stat_identity(path: Path) -> dict[str, Any]:
    st = path.stat()
    return {
        "size_bytes": int(st.st_size),
        "created_utc": datetime.fromtimestamp(st.st_ctime, timezone.utc).isoformat(),
        "last_write_utc": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
        "file_id": f"vol:{int(getattr(st, 'st_dev', 0))}:ino:{int(getattr(st, 'st_ino', 0))}",
        "reparse": bool(getattr(st, "st_file_attributes", 0) & 0x400),
    }


def classify(path: Path) -> dict[str, Any]:
    under_report_root = False
    try:
        path.resolve().relative_to(REPORT_ROOT.resolve())
        under_report_root = True
    except ValueError:
        pass
    name_hits_harness_vocab = bool(re.search(
        r"(cdp_verification|isolation_selfcheck|owned_cleanup|campaign_|isolated_hidden|"
        r"visual_demo_|probe_|run_isolated|tauri_uia|hidden_ui)",
        path.name, re.IGNORECASE))
    content_hit = sniff_text(path)
    manifest_neighbor = any(
        (path.parent / candidate).exists()
        for candidate in ("owned_run_manifest.json", "isolated_hidden_summary.json",
                          "isolation_seed.json", "isolated_launch.json")
    )
    signals = [under_report_root, manifest_neighbor, name_hits_harness_vocab, content_hit]
    count = sum(1 for item in signals if item)

    if count >= 2:
        strength = "strong" if (under_report_root or manifest_neighbor) and count >= 2 else "probable"
    elif count == 1:
        strength = "weak"
    else:
        strength = "none"

    in_repo_untracked = not under_report_root
    if strength == "none":
        ownership_class = "unowned_or_ambiguous"
    elif strength == "weak" and in_repo_untracked:
        # One name/content signal alone cannot bind an untracked repo file to
        # any specific run.
        ownership_class = "unowned_or_ambiguous"
    else:
        ownership_class = "historically_associated_but_not_owned_for_cleanup"

    record = {
        "schema_version": SCHEMA,
        "record_id": hashlib.sha256(str(path).lower().encode("utf-8")).hexdigest()[:16],
        "canonical_path": str(path),
        "object_type": "directory" if path.is_dir() else "file",
        **stat_identity(path),
        "sha256": sha256_small(path),
        "owner_marker_present": (path.parent / "owned_run_manifest.json").exists(),
        "evidence_refs": [
            ref for ref, hit in (
                ("path_under_computer_use_report_root", under_report_root),
                ("sibling_run_manifest_or_summary", manifest_neighbor),
                ("name_matches_harness_vocabulary", name_hits_harness_vocab),
                ("plain_text_content_mentions_localcomet", content_hit),
            ) if hit
        ],
        "historical_association": strength,
        "ownership_class": ownership_class,
        "cleanup_eligible": False,
        "human_decision_required": True,
        "reason_not_cleanup_eligible": "pre-existing object without creation-time ownership proof",
    }
    if under_report_root:
        record["ownership_class"] = "historically_associated_but_not_owned_for_cleanup"
    return record


def collect_scope() -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()

    def add(item: Path) -> None:
        key = str(item).lower()
        if key not in seen:
            seen.add(key)
            found.append(item)

    for pattern in REPO_ROOT_GROUPS:
        for match in ROOT.glob(pattern):
            add(match)
    tools_dir = ROOT / "tools"
    for name in TOOLS_PROBE_GROUP:
        candidate = tools_dir / name
        if candidate.exists():
            add(candidate)
    if REPORT_ROOT.exists():
        for match in REPORT_ROOT.rglob("*"):
            if match.is_file():
                add(match)
    audit_dir = ROOT / "audit"
    if audit_dir.is_dir():
        for match in audit_dir.glob("*qwen3*"):
            add(match)
    return sorted(found, key=lambda item: str(item).lower())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    records = [classify(path) for path in collect_scope()]
    counts: dict[str, int] = {}
    strengths: dict[str, int] = {}
    for record in records:
        counts[record["ownership_class"]] = counts.get(record["ownership_class"], 0) + 1
        strengths[record["historical_association"]] = strengths.get(record["historical_association"], 0) + 1

    payload = {
        "schema_version": SCHEMA,
        "captured_utc": utc_now(),
        "read_only_guarantee": {"objects_modified": 0, "objects_moved": 0, "objects_deleted": 0},
        "total_objects": len(records),
        "association_strength_counts": strengths,
        "ownership_class_counts": counts,
        "cleanup_candidates_pre_existing": sum(
            1 for r in records if r["cleanup_eligible"] is not False),
        "records": records,
    }
    (out_dir / "legacy_identity_inventory.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    human_paths = [r["canonical_path"] for r in records
                   if r["ownership_class"] == "unowned_or_ambiguous"]
    lines = [
        "# Legacy artifact report (READ-ONLY ledger)",
        "",
        f"- captured_utc: {payload['captured_utc']}",
        f"- total objects inventoried: {len(records)}",
        f"- objects modified/moved/deleted by this audit: **0**",
        "",
        "## Totals",
        f"- historical association: {json.dumps(strengths)}",
        f"- ownership classes: {json.dumps(counts)}",
        f"- cleanup candidates among pre-existing objects: **0** (by policy, §9–§10)",
        "",
        "## Unowned/ambiguous items requiring separate human decision",
    ]
    lines += [f"- `{item}`" for item in human_paths[:60]] or ["- (none)"]
    lines += [
        "",
        "## Policy note",
        "`owned_temp_candidate=0` for old artifacts is the CORRECT safe state:",
        "association never upgrades to cleanup eligibility without a creation-time",
        "manifest written before the object existed.",
    ]
    (out_dir / "legacy_artifact_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "total_objects": len(records),
        "classes": counts,
        "strengths": strengths,
        "modified_objects": 0,
        "deleted_objects": 0,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
