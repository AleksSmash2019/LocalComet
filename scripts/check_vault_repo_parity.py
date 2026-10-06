#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vault <-> repository parity gate.

Prevents the failure class found by the 2026-09-09 audit: the Obsidian vault
declared a "current state" that was 8 commits behind the repository, kept a
3-week-old copy of AGENTS.md, and cited four evidence artifacts that did not
exist. All of that is mechanically detectable, so it is checked here.

Checks
  1. repository_commit in the canonical current-state note == git HEAD (fail closed if
     the repository identity cannot be read at all).
  2. source_sha256 of every repository projection (13 Репозиторий/**) == real file.
  3. every evidence_refs entry resolves to a note carrying that evidence_id, and no
     evidence_id is claimed by two different notes.
  4. notes whose status claims currency are not older than --max-age days.
  5. no multi-pipe wikilinks ([[a|b|c]] — Obsidian only reads two segments).
  6. no unresolvable wikilinks, and every `#fragment` resolves to a real heading.
  7. frontmatter dialect: notes using non-ASCII keys are invisible to this gate, and
     notes with no ASCII mirror for those keys are reported separately.
  8. root index notes (00 *.md) must mention the current HEAD, not only old ones.
  9. commit/snapshot fields must carry a recognised historical marker when they are not HEAD.
 10. the release line declared in the canonical note matches package.json / tauri.conf.json.
 11. a dirty working tree is reported, because every "clean tree" claim goes stale.

Exit codes: 0 = clean, 1 = violations, 2 = gate not run (bad input / unreadable identity).
"""
from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

WIKILINK = re.compile(r"\[\[([^\]\n]+)\]\]")
FM_SPLIT = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?", re.S)
ASCII_KEY = re.compile(r"^[A-Za-z0-9_\-\.]+$")
ANY_KEY = re.compile(r"^([^:\s][^:]*?):\s*(.*)$")
HEX_TOKEN = re.compile(r"`([0-9a-f]{7,40})`")
ATX_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", re.M)
FENCE = re.compile(r"^```.*?^```", re.S | re.M)
INLINE_CODE = re.compile(r"`[^`\n]*`")

# Only these values may suppress the non-HEAD commit-field check. An arbitrary
# non-empty string must not be able to silence the gate.
SNAPSHOT_ROLES = {
    "historical_mapping_baseline",
    "historical_snapshot",
    "historical_evidence",
    "archived_projection",
}

COMMIT_FIELDS = (
    "repository_commit", "snapshot_commit", "current_repository_snapshot_commit",
    "snapshot_head", "source_mapping_baseline_commit", "commit",
)
HISTORICAL_STATUSES = {
    "historical", "superseded", "archived", "documented", "resolved",
    "rejected_by_independent_audit", "partially-superseded",
    "artifact_not_preserved", "evidence-limited",
}
HISTORICAL_TYPES = {
    "session-note", "session", "session_update", "release", "evidence", "archive",
    "archive_stub", "audit-result", "checkpoint", "handoff", "research", "incident",
}

CURRENT_STATUSES = {
    "active", "current", "verified_current", "accepted", "open", "in_progress",
    "continuation_active", "reported_complete", "partially-superseded",
    "active-work-awaiting-acceptance",
    "remediation-complete-awaiting-independent-acceptance",
}


def read(path: str) -> str:
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw.decode("utf-8", errors="replace")


def frontmatter(text: str):
    m = FM_SPLIT.match(text)
    if not m:
        return {}, text
    data: dict[str, object] = {}
    key = None
    for line in m.group(1).splitlines():
        s = line.strip()
        if s.startswith("- ") and key and isinstance(data.get(key), list):
            data[key].append(s[2:].strip().strip('"').strip("'"))  # type: ignore[union-attr]
            continue
        kv = re.match(r"^([A-Za-z0-9_\-\.]+):\s*(.*)$", s)
        if kv and not line.startswith((" ", "\t")):
            key = kv.group(1)
            v = kv.group(2).strip().strip('"').strip("'")
            if v in ("", "|", ">"):
                data[key] = []
            elif v.startswith("[") and v.endswith("]"):
                inner = v[1:-1].strip()
                data[key] = [x.strip().strip('"').strip("'")
                             for x in inner.split(",") if x.strip()] if inner else []
            else:
                data[key] = v
        else:
            key = None
    return data, text[m.end():]


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def frontmatter_block(text: str) -> str | None:
    m = FM_SPLIT.match(text)
    return m.group(1) if m else None


def non_ascii_frontmatter_keys(block: str) -> list[str]:
    """Keys the ASCII-only frontmatter parser above silently drops.

    A note written with `название:`/`тип:`/`обновлено:` parses as an empty
    mapping, so it escapes the commit, freshness, evidence and type checks
    without a single warning. That blind spot hid a false class-A
    current-state claim in the vault's own entry point.
    """
    keys: list[str] = []
    for line in block.splitlines():
        if line.startswith((" ", "\t", "-")):
            continue
        m = ANY_KEY.match(line.strip())
        if not m:
            continue
        key = m.group(1)
        if ASCII_KEY.match(key):
            continue
        if any(ord(ch) > 127 for ch in key):
            keys.append(key)
    return sorted(set(keys))


def release_from_package_json(repo: str) -> str | None:
    """`0.0.0-v7.0.5` -> `v7.0.5`; `7.0.5` -> `v7.0.5`."""
    p = os.path.join(repo, "desktop", "localcomet-desktop", "package.json")
    try:
        with open(p, "rb") as fh:
            data = json.loads(fh.read().decode("utf-8", errors="replace"))
    except (OSError, ValueError):
        return None
    raw = str(data.get("version", "")).strip()
    # `0.0.0-v7.0.5` is the local placeholder prefix; the real line is the last match.
    found = re.findall(r"(\d+\.\d+\.\d+(?:\.\d+)?)", raw)
    return f"v{found[-1]}" if found else None


def git_head(repo: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def collect(vault: str) -> list[tuple[str, str, dict, str]]:
    """[(rel_path, abs_path, frontmatter, text)] for every markdown note."""
    notes = []
    for root, dirs, names in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in (".git", ".obsidian", ".pi-subagents")]
        for n in names:
            if not n.lower().endswith(".md"):
                continue
            p = os.path.join(root, n)
            text = read(p)
            fm, _ = frontmatter(text)
            notes.append((os.path.relpath(p, vault).replace("\\", "/"), p, fm, text))
    return notes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Vault/repository parity gate")
    ap.add_argument("--vault", default=r"C:\Users\DNS\Documents\LocalCometVault")
    ap.add_argument("--repo", default=r"C:\Users\DNS\Documents\LocalComet-build-week-clean")
    ap.add_argument("--canon", default="00 Канон/Текущее состояние LocalComet.md")
    ap.add_argument("--max-age", type=int, default=30,
                    help="max age in days for notes claiming current status")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD (default: system date)")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.vault):
        print("GATE NOT RUN: vault not found:", args.vault)
        return 2
    if not os.path.isdir(args.repo):
        print("GATE NOT RUN: repository not found:", args.repo)
        return 2

    today = (datetime.date.fromisoformat(args.today) if args.today
             else datetime.date.today())
    errors: list[str] = []
    warnings: list[str] = []
    notes = collect(args.vault)

    # ---- 1. canonical commit vs git HEAD -------------------------------------
    head = git_head(args.repo)
    canon_path = os.path.join(args.vault, args.canon)
    if not head:
        # Fail closed. An unreadable repository identity is missing evidence, and
        # missing evidence must never be reported as a passing parity result.
        print("GATE NOT RUN: cannot read git HEAD for", args.repo)
        print("  Every repository-parity claim depends on this identity; refusing to guess.")
        return 2
    if not os.path.exists(canon_path):
        errors.append(f"canonical note missing: {args.canon}")
    else:
        fm, _ = frontmatter(read(canon_path))
        declared = str(fm.get("repository_commit", "")).strip()
        if not declared:
            errors.append(f"{args.canon}: no repository_commit in frontmatter")
        elif declared.split()[0] != head:
            errors.append(
                f"{args.canon}: repository_commit={declared[:12]} != git HEAD={head[:12]} "
                f"(vault is behind or ahead)"
            )

    # ---- 2. projection sha256 -------------------------------------------------
    proj = [n for n in notes if n[2].get("type") == "projection"]
    drift = 0
    missing = 0
    for relp, _abs, fm, _text in proj:
        src = str(fm.get("source_path", "")).strip()
        want = str(fm.get("source_sha256", "")).strip()
        if not src:
            continue
        rp = os.path.join(args.repo, src)
        if not os.path.exists(rp):
            if str(fm.get("source_exists", "true")).lower() == "true":
                errors.append(f"projection source vanished: {relp} -> {src}")
            missing += 1
            continue
        if not want:
            warnings.append(f"projection without source_sha256: {relp}")
            continue
        if sha256(rp) != want:
            drift += 1
            errors.append(f"projection drift: {relp} (source {src} changed)")
    print(f"  projections checked: {len(proj)} (drifted {drift}, source-missing {missing})")

    # ---- 3. evidence_refs resolve, and identities are unambiguous -------------
    by_evidence_id: dict[str, list[str]] = collections.defaultdict(list)
    for relp, _abs, fm, _text in notes:
        eid = str(fm.get("evidence_id", "")).strip()
        if eid:
            by_evidence_id[eid].append(relp)
    duplicates = {k: v for k, v in by_evidence_id.items() if len(v) > 1}
    for eid, holders in sorted(duplicates.items()):
        errors.append(
            f"duplicate evidence_id {eid} claimed by {len(holders)} notes: "
            + ", ".join(sorted(holders))
        )
    registered_ids = set(by_evidence_id)
    dangling = collections.Counter()
    for relp, _abs, fm, _text in notes:
        refs = fm.get("evidence_refs") or []
        if isinstance(refs, str):
            refs = [refs]
        for ref in refs:
            ref = str(ref).strip()
            if not ref:
                continue
            if ref not in registered_ids:
                # A path to an external artifact is a warning, not a vault error.
                if re.match(r"^[A-Za-z]:\\|^\.\.?/|^/", ref):
                    warnings.append(f"external evidence_ref (not a vault note): {ref}")
                    continue
                dangling[ref] += 1
                errors.append(f"dangling evidence_ref: {ref} (cited in {relp})")
    print(f"  evidence ids registered: {len(registered_ids)} "
          f"(duplicated {len(duplicates)}), dangling refs: {sum(dangling.values())}")

    # ---- 4. freshness of current-status notes --------------------------------
    stale = []
    for relp, _abs, fm, _text in notes:
        status = str(fm.get("status", "")).strip()
        if status not in CURRENT_STATUSES:
            continue
        upd = str(fm.get("updated", "")).strip().strip('"').strip("'")
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", upd)
        if not m:
            continue
        try:
            stamped = datetime.date(*map(int, m.groups()))
        except ValueError:
            warnings.append(f"unparseable updated date in {relp}: {upd!r}")
            continue
        age = (today - stamped).days
        if age > args.max_age:
            stale.append((age, relp, status, upd))
    for age, relp, status, upd in sorted(stale, reverse=True)[:40]:
        warnings.append(f"stale {age}d: {relp} (status={status}, updated={upd})")
    print(f"  current-status notes older than {args.max_age}d: {len(stale)}")

    # ---- 5/6. link integrity --------------------------------------------------
    by_name = collections.defaultdict(list)
    by_path = {}
    for relp, _abs, _fm, _text in notes:
        by_path[relp[:-3].lower()] = relp
        by_name[os.path.basename(relp)[:-3].lower()].append(relp)
    for root, dirs, names in os.walk(args.vault):
        dirs[:] = [d for d in dirs if d not in (".git", ".obsidian")]
        for n in names:
            if not n.lower().endswith((".md", ".canvas")):
                continue
            by_name[os.path.splitext(n)[0].lower()].append(
                os.path.relpath(os.path.join(root, n), args.vault).replace("\\", "/"))

    fence = re.compile(r"^```.*?^```", re.S | re.M)
    inline_code = re.compile(r"`[^`\n]*`")


    def headings_of(text: str) -> tuple[set[str], set[str]]:
        """(raw headings lowercased, Obsidian-ish slugs) outside code fences."""
        scan = FENCE.sub("\n", text)
        raw: set[str] = set()
        slugs: set[str] = set()
        for title in ATX_HEADING.findall(scan):
            cleaned = INLINE_CODE.sub("", title)
            cleaned = re.sub(r"[*_~\[\]()>#]", "", cleaned).strip()
            if not cleaned:
                continue
            raw.add(cleaned.lower())
            slug = cleaned.lower()
            slug = re.sub(r"[^\w\s\-]", "", slug, flags=re.UNICODE)
            slug = re.sub(r"\s+", "-", slug.strip())
            slugs.add(slug)
        return raw, slugs


    headings: dict[str, tuple[set[str], set[str]]] = {}
    for relp, _abs, _fm, text in notes:
        headings[relp.lower()] = headings_of(text)

    multipipe = 0
    unresolved = 0
    broken_anchor = 0
    for relp, _abs, _fm, text in notes:
        src_dir = os.path.dirname(relp)
        # links inside code blocks or inline code are documentation, not navigation
        scan = fence.sub("\n", text)
        scan = inline_code.sub(" ", scan)
        for m in WIKILINK.finditer(scan):
            content = m.group(1)
            if content.count("|") >= 2:
                multipipe += 1
                errors.append(f"multi-pipe link in {relp}: [[{content[:60]}]]")
                continue
            target, _, fragment = content.split("|", 1)[0].partition("#")
            target = target.strip().replace("\\", "/")
            fragment = fragment.strip()
            for pref in ("./", "../"):
                if target.startswith(pref):
                    target = target[len(pref):]
                    break
            if not target:
                continue
            key = target.lower()
            for ext in (".md", ".canvas"):
                if key.endswith(ext):
                    key = key[: -len(ext)]
                    break
            cands = [key, os.path.normpath(os.path.join(src_dir, key)).replace("\\", "/").lower()]
            resolved_rel: str | None = None
            for c in cands:
                if c in by_path:
                    resolved_rel = by_path[c]
                    break
            if resolved_rel is None:
                if key in by_name:
                    resolved_rel = sorted(by_name[key])[0]
                elif os.path.basename(key) in by_name:
                    resolved_rel = sorted(by_name[os.path.basename(key)])[0]
            if resolved_rel is None:
                unresolved += 1
                errors.append(f"unresolved link in {relp}: [[{content[:60]}]]")
                continue
            if not fragment:
                continue
            raw_headings, slug_headings = headings.get(resolved_rel.lower(), (set(), set()))
            if not raw_headings:
                continue
            if fragment.lower() in raw_headings:
                continue
            if fragment.lower() in slug_headings:
                continue
            broken_anchor += 1
            errors.append(
                f"broken anchor in {relp}: [[{content[:80]}]] "
                f"(no heading {fragment!r} in {resolved_rel})"
            )
    print(f"  multi-pipe links: {multipipe}, unresolved links: {unresolved}, "
          f"broken anchors: {broken_anchor}")

    # ---- 7. frontmatter dialect (non-ASCII keys are invisible here) -----------
    # A Cyrillic key is valid YAML; it is this gate's ASCII-only parser that drops
    # it. Report the real consequence instead of a blanket claim: which notes still
    # have a non-ASCII key with no ASCII mirror, so their fields stay unread.
    MIRRORS = {
        "название": "title", "тип": "type", "обновлено": "updated",
        "источник": "source", "дата": "date", "импортировано": "imported",
    }
    dialect = []
    unmapped = []
    for relp, _abs, _fm, text in notes:
        block = frontmatter_block(text)
        if not block:
            continue
        keys = non_ascii_frontmatter_keys(block)
        if not keys:
            continue
        dialect.append((relp, keys))
        ascii_present = {
            m.group(1) for m in
            (re.match(r"^([A-Za-z0-9_\-\.]+):", ln.strip()) for ln in block.splitlines())
            if m
        }
        missing = sorted(k for k in keys if MIRRORS.get(k) not in ascii_present)
        if missing:
            unmapped.append((relp, missing))
    if unmapped:
        sample = ", ".join(f"{r} ({'/'.join(k)})" for r, k in unmapped[:3])
        warnings.append(
            f"{len(unmapped)} note(s) have non-ASCII frontmatter keys with no ASCII mirror, "
            f"so those fields are not parsed by this gate: {sample}"
            + (" ..." if len(unmapped) > 3 else "")
        )
    elif dialect:
        warnings.append(
            f"{len(dialect)} note(s) keep non-ASCII frontmatter keys alongside ASCII mirrors; "
            f"the Russian keys remain unread by this gate but every field has an ASCII twin"
        )
    print(f"  non-ASCII frontmatter dialect: {len(dialect)} note(s), "
          f"{len(unmapped)} without an ASCII mirror")

    # ---- 8. root index notes must advertise the current HEAD ------------------
    head_short = head[:12] if head else ""
    foreign_index = 0
    if head_short:
        for relp, _abs, fm, text in notes:
            if os.path.dirname(relp) or not os.path.basename(relp).startswith("00 "):
                continue
            if str(fm.get("snapshot_role", "")).strip() in SNAPSHOT_ROLES:
                continue
            tokens = set(HEX_TOKEN.findall(text))
            if not tokens:
                continue
            if any(t.startswith(head_short) or head_short.startswith(t) for t in tokens):
                continue
            foreign_index += 1
            errors.append(
                f"index note advertises no current HEAD: {relp} "
                f"(mentions {sorted(tokens)[:4]}, git HEAD={head_short})"
            )
    print(f"  root index notes without current HEAD: {foreign_index}")

    # ---- 9. snapshot/commit fields need a historical marker -------------------
    unmarked = 0
    bad_role = 0
    if head_short:
        for relp, _abs, fm, _text in notes:
            vals = [(f, str(fm[f]).strip()) for f in COMMIT_FIELDS if f in fm]
            if not vals:
                continue
            role = str(fm.get("snapshot_role", "")).strip()
            if role and role not in SNAPSHOT_ROLES:
                bad_role += 1
                errors.append(
                    f"unrecognised snapshot_role in {relp}: {role!r} "
                    f"(allowed: {', '.join(sorted(SNAPSHOT_ROLES))})"
                )
                continue
            if role:
                continue
            if str(fm.get("status", "")).strip() in HISTORICAL_STATUSES:
                continue
            if str(fm.get("type", "")).strip() in HISTORICAL_TYPES:
                continue
            live = [
                f"{f}={v[:12]}" for f, v in vals
                if v and not (v.split()[0].startswith(head_short) or head_short.startswith(v.split()[0]))
            ]
            if live:
                unmarked += 1
                errors.append(
                    f"commit field without historical marker in {relp}: {', '.join(live)}"
                )
    print(f"  unmarked non-HEAD commit fields: {unmarked}, unrecognised snapshot roles: {bad_role}")

    # ---- 10. declared release line vs shipped version bytes -------------------
    declared_release = release_from_package_json(args.repo)
    if declared_release:
        if canon_path and os.path.exists(canon_path):
            canon_text = read(canon_path)
            canon_fm, _ = frontmatter(canon_text)
            releases = canon_fm.get("releases") or []
            if isinstance(releases, str):
                releases = [releases]
            releases = [str(r).strip() for r in releases]
            if not releases:
                warnings.append(
                    f"{args.canon}: no releases list; cannot tie the shipped "
                    f"release {declared_release} to a declared line"
                )
            elif declared_release not in releases:
                errors.append(
                    f"{args.canon}: shipped release {declared_release} (package.json) "
                    f"is not in the declared releases {releases}"
                )
            elif declared_release not in canon_text:
                warnings.append(
                    f"{args.canon}: declares {declared_release} in frontmatter but never "
                    f"mentions it in the body"
                )
        else:
            warnings.append(f"cannot verify release line {declared_release}: canonical note missing")
        print(f"  shipped release line: {declared_release}")

    # ---- 11. dirty working tree makes every "clean tree" claim stale ----------
    dirty_count = None
    try:
        st = subprocess.run(["git", "-C", args.repo, "status", "--porcelain"],
                            capture_output=True, text=True, timeout=60)
        if st.returncode == 0:
            dirty_count = len([ln for ln in st.stdout.splitlines() if ln.strip()])
    except (OSError, subprocess.SubprocessError):
        dirty_count = None
    if dirty_count:
        warnings.append(
            f"working tree is dirty ({dirty_count} entries): any 'рабочее дерево чистое' "
            f"claim in the vault is stale and must be re-measured with git status"
        )
    print(f"  working tree entries: {dirty_count if dirty_count is not None else 'unknown'}")

    # ---- verdict --------------------------------------------------------------
    for w in warnings:
        print("WARN", w)
    if errors:
        print()
        for e in errors[:60]:
            print("FAIL", e)
        if len(errors) > 60:
            print(f"... and {len(errors) - 60} more")
        print()
        print(f"RESULT: FAIL ({len(errors)} violation(s), {len(warnings)} warning(s))")
        return 1

    print()
    print(f"RESULT: PASS (0 violations, {len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
