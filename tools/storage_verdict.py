"""Storage-verdict selection driven strictly by recorded evidence state.

The three allowed outcomes mirror the unified prompt §16 verbatim. The
selector refuses optimistic wording: any missing precondition degrades the
verdict one level down. Unit-tested on synthetic states only.
"""

from __future__ import annotations

from typing import Any

VERDICT_FULL = (
    "STORAGE HYGIENE IMPLEMENTED FOR SUPPORTED LOCALCOMET ENTRY POINTS — "
    "REPO-LEVEL DEFAULT CARGO TARGET IS EXTERNAL — LEGACY ARTIFACTS "
    "INVENTORIED READ-ONLY — AUTOMATED CLEANUP: 0 DELETIONS, 0 PROCESSES "
    "STOPPED — SEPARATELY, TWO EXPLICITLY AUTHORIZED MANUAL BUILD-CACHE "
    "DELETIONS WERE PERFORMED AND ARE NOT PART OF AUTOMATED CLEANUP."
)

VERDICT_PARTIAL = (
    "STORAGE HYGIENE PARTIALLY IMPLEMENTED — REPO-LEVEL DEFAULT CARGO TARGET "
    "IS EXTERNAL FOR VERIFIED ENTRY POINTS — EXPLICIT ENV/CLI OVERRIDES "
    "REMAIN POSSIBLE — LEGACY ARTIFACTS INVENTORIED READ-ONLY — AUTOMATED "
    "CLEANUP: 0 DELETIONS, 0 PROCESSES STOPPED — TWO EXPLICITLY AUTHORIZED "
    "MANUAL BUILD-CACHE DELETIONS ARE REPORTED SEPARATELY."
)

VERDICT_NOT_ACCEPTED = (
    "STORAGE HYGIENE NOT ACCEPTED — SOURCE-LOCAL CARGO TARGET REMAINS "
    "POSSIBLE OR WAS RECREATED — LEGACY INVENTORY PRESERVED — NO AUTOMATED "
    "DELETIONS OR PROCESS STOPS."
)


def select_storage_verdict(state: dict[str, Any]) -> str:
    """Pick exactly one verdict string based on boolean/numeric facts."""
    repo_config_valid = bool(state.get("repo_config_valid"))
    default_resolves_external = bool(state.get("default_resolves_external"))
    source_local_recreated = bool(state.get("source_local_recreated_after_fix"))
    direct_invocation_proven = bool(state.get("direct_invocation_uses_external"))
    entry_points_enforced = bool(state.get("supported_entry_points_enforced"))
    legacy_readonly_done = bool(state.get("legacy_inventory_read_only_complete"))
    deletions = int(state.get("automated_cleanup_deletions", 1))
    stops = int(state.get("automated_cleanup_process_stops", 1))
    overrides_remain_possible = bool(state.get("explicit_overrides_remain_possible", True))

    if (
        not repo_config_valid
        or not default_resolves_external
        or source_local_recreated
        or not direct_invocation_proven
    ):
        return VERDICT_NOT_ACCEPTED
    if deletions != 0 or stops != 0:
        # Automated cleanup touched something: none of the clean verdicts apply.
        return VERDICT_NOT_ACCEPTED
    if not entry_points_enforced or not legacy_readonly_done:
        return VERDICT_PARTIAL
    if overrides_remain_possible:
        return VERDICT_PARTIAL
    return VERDICT_FULL
