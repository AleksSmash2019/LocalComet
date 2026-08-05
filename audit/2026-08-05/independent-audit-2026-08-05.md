# Independent audit — 2026-08-05
Branch: feature/donor-ui-compatible-port
HEAD: a1ad496
Working tree: 23 files modified, 0 committed

## Verdict
Package is NOT ready to fast-forward into continue/after-build-week-2026.

## Blockers (descending)
1. Revert entrypoints added to localcomet_runtime_manifest.json (P0-A quarantine violation).
2. Explain pytest regression: report claims 179 passed, but full run shows 22 failed / 1022 passed / 1 skipped. Baseline protocol is 832 passed / 1 failed.
3. Close second T5 point at next/app_v5.py:2004 and remove two remaining T1 unused imports in modules/browser.py and modules/browser_actions.py.
4. Separate task for scan_hardware (introduced in a1ad496).

## Evidence summary
- pytest full run: 22 failed, 1022 passed, 1 skipped
- Legacy quarantine failures:
  - tools/test_p0a_legacy_quarantine.py::test_manifest_excludes_legacy_app FAILED
  - tools/test_p0a_legacy_quarantine.py::test_manifest_excludes_legacy_app_v5 FAILED
- scan_hardware introduced in a1ad496, causes 4 failures plus evidence/command-parity fallout
- T2 already fixed in current bytes (drift)
- T3: no hard data["..."] left in agents/
- T4: click_text has single processing point
- T6: shell=True count is 0 in report_opener.py
- T7 deferred correctly; single call-site .next() at app_v5.py:1991
- T8: control_plane_core.rs does not exist in this repo (spec drift confirmed)
- T9: files.rollback=GUARDED, docs/security-model.md and tests/test_files_rollback.py present
- T11: app.py and next/app_v5.py were added to manifest entrypoints (violation)
- T12: scripts/doctor.py predates package (should be NEW)
- T1: 14 of 18 registry entries are erroneous; 3 real unused imports fixed; 2 remain in modules/browser.py:3 and modules/browser_actions.py:3
- Gates: check_ui_fake_state OK, check_tool_risk_registry OK, check_bundle_parity 146 match, py_compile OK for all touched files

## Root causes
- Coder reported subset pytest result as final verification (NA-012 violation).
- T11 implementation violated P0-A quarantine by adding legacy entrypoints instead of deprecating them.
- Two T1 unused imports missed.
- Second T5 None-deref point left unclosed.
- scan_hardware was added without approval boundary review.

## Required actions
1. Revert manifest entrypoints change in localcomet_runtime_manifest.json.
2. Re-run pytest in full and provide raw output; compare against baseline 832/1.
3. Fix T5 point at app_v5.py:2004.
4. Remove Path imports from modules/browser.py:3 and modules/browser_actions.py:3.
5. Open separate task for scan_hardware approval boundary.
6. Replace scripts/doctor.py with actual NEW implementation or revert to pre-package version.
