#!/usr/bin/env python3
"""Gate: check that mockData is not imported outside allowed paths.

Allowed:
  - tests/ directory (test code)
  - src/lib/data/mockData.ts itself (definition)
  - Explicit allowlist entries (fallback constants / type-only imports)

Usage: python scripts/check_mockdata_imports.py
Exit 0 = clean, exit 1 = violations found.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "desktop" / "localcomet-desktop" / "src"

ALLOWLIST = {
    "src/lib/stores/shellStore.ts": "fallback constants (modeOptions, inspectorSections)",
    "src/lib/components/chat/CodeBlock.svelte": "type-only import",
    "src/lib/components/chat/ToolCallCard.svelte": "type-only import",
    "src/lib/components/chat/VerificationCard.svelte": "type-only import",
    "src/lib/components/common/ThemeToggle.svelte": "type-only import",
    "src/lib/components/shell/AppShell.svelte": "type-only import",
    "src/lib/components/shell/SettingsPanel.svelte": "type-only import",
}

IMPORT_RE = re.compile(
    r"""(?ms)^\s*import(?:\s+type)?(?:\s+.*?\s+from)?\s*['"](?P<specifier>[^'"]+)['"]"""
)
MOCK_DATA_SOURCE = SRC / "lib" / "data" / "mockData.ts"


def imports_mock_data(importer: Path, specifier: str) -> bool:
    """Recognize the alias and relative spellings of the mockData module."""
    if specifier == "$lib/data/mockData":
        return True
    if not specifier.startswith("."):
        return False
    resolved = (importer.parent / specifier).resolve()
    return resolved == MOCK_DATA_SOURCE.resolve().with_suffix("") or resolved == MOCK_DATA_SOURCE.resolve()


def main() -> int:
    violations: list[str] = []
    imported_paths: set[str] = set()
    checked = 0

    for ext in ("*.ts", "*.svelte"):
        for path in sorted(SRC.rglob(ext)):
            rel = path.relative_to(ROOT / "desktop" / "localcomet-desktop").as_posix()
            if "node_modules" in rel or ".svelte-kit" in rel:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if not any(imports_mock_data(path, match.group("specifier")) for match in IMPORT_RE.finditer(text)):
                continue
            checked += 1
            src_rel = rel.removeprefix("desktop/localcomet-desktop/")
            imported_paths.add(src_rel)
            if src_rel not in ALLOWLIST:
                violations.append(f"  VIOLATION: {src_rel}")

    for src_rel in sorted(set(ALLOWLIST) - imported_paths):
        violations.append(f"  INERT_ALLOWLIST: {src_rel}")

    print(f"mockData import gate: {checked} file(s) with mockData imports")
    if violations:
        print(f"FAIL: {len(violations)} import/allowlist violation(s):")
        for v in violations:
            print(v)
        return 1

    print(f"OK: all {checked} imports are in the allowlist")
    print(f"Allowlist: {len(ALLOWLIST)} entries")
    for path_key, reason in sorted(ALLOWLIST.items()):
        print(f"  {path_key}: {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
