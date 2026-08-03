# MVP-P0-A Contract: Legacy Execution Quarantine

## Cycle: MVP-P0-A
## Finding: F-001
## Status: CONTRACT_RATIFIED

## Discovery Summary

5 concurrent read-only agents confirmed:
- MVP desktop path (Tauri -> IPC -> Python sidecar) is architecturally isolated from legacy code
- Zero legacy imports in the sidecar's transitive dependency chain
- Zero subprocess/shell calls in MVP modules
- Rust control plane has zero references to legacy modules
- Strict placeholder ACTIVE blocking model-initiated tool events

However:
- `modules/windows.py:152` uses `shell=True` with unvalidated model input (CWE-78)
- `modules/self_edit.py:751,1129` uses `shell=True` with model-controlled test strings
- `core/executor.py` dispatches to 18 agents with no authorization gate
- `localcomet_runtime_manifest.json` lists `next/app_v5.py` as an entrypoint
- No explicit tests prove quarantine

## Contract

### 1. modules/windows.py — open_app() deny-by-default

**Before:** `APP_COMMANDS.get(app, app)` passes unknown strings to `shell=True`
**After:**
- Unknown app values raise `ValueError("unknown application identifier: {app}")`
- Known apps map to fixed executable + argument vectors (list form)
- `shell=True` is eliminated entirely
- `subprocess.Popen(command, shell=True)` becomes `subprocess.Popen([exe], shell=False)`

Exact behavior:
- `open_app("notepad")` -> launches `["notepad", str(NOTEPAD_FILE)]` (existing path)
- `open_app("calc")` -> launches `["calc"]`
- `open_app("mspaint")` -> launches `["mspaint"]`
- `open_app("chrome")` -> launches `["chrome"]`
- `open_app("explorer")` -> launches `["explorer"]`
- `open_app("evil & whoami")` -> raises ValueError
- `open_app("")` -> raises ValueError

### 2. modules/self_edit.py — _run_tests() command validation

**Before:** Model-generated test strings passed to `shell=True`
**After:**
- Each command must match `^python -m py_compile [a-zA-Z0-9_/.\\-]+\.py$`
- Non-matching commands are rejected with explicit error
- `shell=True` replaced with `shell=False` and `shlex.split()`
- `project_health()` similarly converted to `shell=False`

### 3. core/executor.py — quarantine gate

**Before:** Unrestricted dispatch to 18 agents
**After:**
- A `LEGACY_QUARANTINE_ACTIVE` flag (default True) at module level
- When active, dangerous tools (windows, self_edit, automation, browser, gpt_browser, chatgpt_relay, operator, code, codegen) return explicit error: `"quarantined: {tool} execution is disabled"`
- Read-only/informational tools (system, diagnostics, history, maintenance, project, research, workspace, file, files, gpt, stability, none) remain available
- The flag can be set to False only by explicit code change (no runtime toggle)

### 4. localcomet_runtime_manifest.json — entrypoint cleanup

**Before:** `entrypoints` includes `next/app_v5.py`
**After:** `next/app_v5.py` removed from `entrypoints`

### 5. tools/test_p0a_legacy_quarantine.py — quarantine proof tests

Required RED tests (fail before GREEN, pass after):
1. `test_unknown_open_app_rejected` — `open_app("evil")` raises ValueError
2. `test_shell_metacharacters_rejected` — `open_app("calc & whoami")` raises ValueError
3. `test_known_app_uses_fixed_vector` — `open_app("calc")` uses list-form Popen (mock)
4. `test_self_edit_model_command_rejected` — `_run_tests(["rm -rf /"], [])` returns failure
5. `test_self_edit_valid_py_compile_accepted` — `_run_tests(["python -m py_compile foo.py"], [])` works
6. `test_executor_quarantine_blocks_windows` — `execute({"tool": "windows", ...})` returns quarantine error
7. `test_executor_quarantine_blocks_self_edit` — `execute({"tool": "self_edit", ...})` returns quarantine error
8. `test_executor_allows_read_only_tools` — `execute({"tool": "none", "text": "ok"})` still works
9. `test_manifest_excludes_legacy_entrypoint` — `next/app_v5.py` not in manifest entrypoints
10. `test_no_shell_true_in_windows_module` — source scan of windows.py has no `shell=True`

## Non-goals

- Do not delete legacy files
- Do not modify Rust code
- Do not modify frontend code
- Do not add npm dependencies
- Do not touch the MVP sidecar modules (_ru family)
- Do not weaken existing tests

## Validation Order

1. Quarantine gate check (executor level)
2. Tool-specific validation (windows.py, self_edit.py)
3. Source-level invariant (no shell=True)

## State Transitions

- QUARANTINE_ACTIVE=True: dangerous tools return error string
- QUARANTINE_ACTIVE=False: legacy behavior restored (for development only)

## Windows Semantics

- All subprocess calls use list-form arguments (no shell interpretation)
- Path handling unchanged (existing _safe_path, projects_dir)
