# LocalComet Agent Operating Layer v1

Passive architecture foundation for agent-based development on LocalComet.

## Task intake

Every task must specify:
- **Baseline version** (current GREEN version before work)
- **Goal** (one sentence, no ambiguity)
- **Allowed files** (explicit paths or globs)
- **Forbidden files** (paths that must not change)
- **Risk level** (see classification below)

If any of these are missing, ask before proceeding.

## Risk classification

| Level | Criteria | Approval |
|---|---|---|
| **doc** | Docs, schemas, skills, config only. No Python edits. | Implicit |
| **config** | Changes to non-Python config files (JSON, YAML, TOML, env). No logic change. | Implicit |
| **safe_code** | Non-breaking Python change covered by existing tests. | Implicit after plan |
| **guarded** | Adds a new module without removing existing functionality. Changes runtime state. | Explicit confirmation |
| **dangerous** | Deletes files. Changes safety policy. Modifies tests to pass without fixing root cause. Changes disk I/O behavior. | Blocked unless explicit per-task override |

When risk level is unclear, default to **guarded**.

## Context pack

Before editing, load:
1. `AGENTS.md` — project operating contract
2. `OPENCODE_RULES.md` — tool-specific rules
3. Current GREEN baseline from `strict_project_stability` output
4. All files listed in "allowed_files" (read at least once)
5. Any file referenced by the task that exists

## Plan contract

Before touching files, produce a plan containing:
```text
task_id: <short unique label>
goal: <one sentence>
risk_level: <doc|config|safe_code|guarded|dangerous>
files_to_edit:
- <path> (reason)
files_to_create:
- <path> (reason)
pre_edit_backup: <path>
test_plan:
- <command 1>
- <command 2>
```

Present the plan. If risk is guarded or dangerous, wait for explicit approval.

## OpenCode implementation prompt

When handing work to an OpenCode agent:
```text
Read AGENTS.md and docs/agent_operating_layer.md.
Use the run_manifest schema at .localcomet/agent/run_manifest.schema.json.
Follow the stability-gate skill at .localcomet/skills/stability-gate/SKILL.md.
Green baseline: <version>
Task: <goal>
Allowed files: <list>
Forbidden files: <list>
Risk level: <level>
```

## Verification gates

After every edit, run in this exact order:

1. `python -m py_compile <every changed .py file>`
2. `python -m py_compile LocalComet_Control_Panel.py`
3. `python tools\localcomet_preflight_audit.py --include-tools`
4. `python -c "from modules.computer_use_core_ru import dispatch; r=dispatch('pc computer contracts'); print(r); assert r['ok']"`
5. `python -c "from modules.strict_project_stability_ru import dispatch; r=dispatch('проверь проект'); assert r['ok'] and r['summary']['hard_failures'] == 0 and r['summary']['warnings'] == 0"`

If any gate fails, stop. Revert or fix. Do not proceed until GREEN.

## Review report

After verification, produce a report with:
```text
task_id: <label>
files_changed:
- <path>
validation:
  py_compile: PASS
  preflight: PASS/FAIL
  contracts: PASS/FAIL
  strict_stability: <score>/<total>, hard_failures=<n>, warnings=<n>
final_status: GREEN|FAILED
risks:
- <any concern about this change>
```

## Accepted GREEN commit / rejected patch decision

- If final_status is GREEN and the change fulfills the goal, the patch is accepted.
- If final_status is GREEN but the change does NOT match the goal, reject and re-plan.
- If final_status is FAILED, reject. Revert all edits. Restore from backup. Re-plan.
