# LocalComet Computer Use — verified improvement pass

**Date:** 2026-08-20  
**Scope:** hidden audit, reliability fixes, Computer Use result UI and sidecar parity.  
**User-data policy:** no user files, notes, model files, browser profiles or application data were removed during this pass.

## Confirmed findings and corrections

| Finding | Correction | User-visible effect |
|---|---|---|
| Non-ASCII typing through the grounded action executor was rejected before it reached Windows input. | Added direct Unicode `SendInput` delivery using UTF-16 code units. It does not use or overwrite the clipboard. | Russian text and other Unicode input can proceed through the guarded, grounded path. |
| `paste_text` replaced the user clipboard via Tkinter before invoking `Ctrl+V`. | Routed normal active-window text through the same Unicode input path. | A routine Computer Use text action no longer replaces clipboard contents. |
| A normal UI button named «Закрыть» could make visual guard classify the screen as a modal dialog. | Dialog/error detection now requires modal/dialog/alert semantics in the UI map, not button text alone. | Fewer false `ask_user`/`stop` outcomes after ordinary UI actions. |
| Interrupted hotkeys and drag operations did not guarantee input release. | Added cleanup paths that release pressed key codes and mouse button state. | Reduced risk of a stuck Ctrl/Alt/Shift or primary mouse button after a failed action. |
| Computer Use chat cards hid the meaningful result whenever a screenshot was present. | Added a compact action/state/next-step summary and localized details controls. | The chat now explains what happened, whether consent is needed, and whether to continue, refresh the plan, inspect the screen, ask the user, or stop. |

## Verification evidence

| Gate | Result |
|---|---|
| Python syntax check for changed Computer Use modules | PASS |
| `tests/test_computer_use_reliability.py` | PASS — 5 tests |
| Computer Use contract suite on synthetic UI fixtures | PASS |
| `npm run check` | PASS — 0 errors, 0 warnings |
| `npm test -- --run` | PASS — 26 files, 404 tests |
| `scripts/check_bundle_parity.py` | PASS — 258 shipped modules match source across build and DevRuntime locations |
| `tests/test_check_bundle_parity.py` | PASS |
| `tests/test_tool_execution_fail_closed.py` | PASS |
| `scripts/check_tool_risk_registry.py` | PASS — 7 console tools classified, mutating calls approval-gated |
| `scripts/check_ui_fake_state.py` | PASS — no fake-state violations |
| `scripts/check_command_parity.py` | PASS — 60 commands registered and invoked |
| `scripts/check_real_sidecar_tests.py` | PASS — required real-sidecar mode, no silent skips |
| `scripts/refresh_evidence.py` and `scripts/check_evidence_provenance.py` | PASS — fresh source-bound evidence |

## Deployment state

The modified sidecar modules were synchronized byte-for-byte into the build source bundle and `%LOCALAPPDATA%\LocalComet\DevRuntime`. LocalComet was then rebuilt in debug mode and restarted with its primary user profile. Startup reports `LC_START_200` and the application process remains responsive.

## Boundaries retained by design

Computer Use deliberately does not bypass UAC, protected desktop, passwords, secrets, payment flows, terminal/admin actions, or destructive file operations. Such requests must remain blocked or require the existing explicit approval path. The final end-to-end verification intentionally used synthetic UI fixtures and simulated actions so that no user app, note, browser tab or desktop state was manipulated during testing.

## Research basis

Microsoft UI Automation describes control patterns as the semantic capability contract for desktop controls. The fixes therefore favor grounded control state and safe input release over blind timing or button-label heuristics.[1][2] Windows also protects elevated and UAC interfaces from ordinary cross-process automation, which LocalComet must not attempt to bypass.[3]

## References

[1]: https://learn.microsoft.com/en-us/windows/win32/winauto/entry-uiautocore-overview
[2]: https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-controlpatternsoverview
[3]: https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/ui-automation-security-overview
