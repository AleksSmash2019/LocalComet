# Repository Guidelines

## Project Rules

Project: LocalComet / LocalAgent

Run:

```powershell
python -m next.app_v5
```

Rules:

- Do not delete files.
- Do not create `.exe`, `.bat`, or `.ps1` files.
- Make small safe changes.
- Prefer targeted edits over full rewrites.
- Run `py_compile` for changed Python files.
- Run `stability test` after important changes.
- Do not modify `Projects/BrowserProfile`.
- Do not apply multiple risky changes at once.
- Preserve the existing LocalComet workflow: `request.md -> response.json -> validate -> apply -> after patch`.
- When changing UI, do not remove existing buttons or functions.

## Project Structure & Module Organization

LocalComet / LocalAgent is a local Python agent project. The current console entry point is `next/app_v5.py`, launched with `python -m next.app_v5`. The older loop is in `app.py`. Core orchestration lives in `core/`: routing, planning, execution, LLM access, and state. Agent adapters live in `agents/` and should stay thin. Implementation logic belongs in `modules/`, including browser control, ChatGPT relay, self-edit, automation, diagnostics, workspace, and reporting. `LocalComet_Control_Panel.py` is the Tkinter control panel. Runtime data and generated artifacts are under `Projects/`; persistent state is in `memory/state.json`; utility scripts are in `tools/`.

## Build, Test, and Development Commands

- `python -m next.app_v5`: run the main LocalComet v5 console.
- `python LocalComet_Control_Panel.py`: open the Tkinter control panel.
- `python -m py_compile path/to/file.py`: syntax-check a changed Python file.
- `python tools/model_tester.py`: run local model behavior tests.
- `python tools/hard_model_tester.py`: run stricter model tests.
- `python tools/test_gpt_bridge.py`: check OpenAI/GPT bridge status.

Some commands write reports to `Projects/Reports` or update `memory/state.json`.

## Coding Style & Naming Conventions

Use standard Python style with 4-space indentation, small functions, and explicit names. Keep agent `handle(action, data)` functions simple and delegate real work to `modules/`. Use `snake_case` for functions, variables, and module names. Prefer small, targeted edits over rewriting large files. Keep path handling explicit with `pathlib.Path`, and preserve existing Russian user-facing text where behavior already uses it.

## Testing Guidelines

There is no formal pytest suite in this checkout. For Python changes, always run `py_compile` on touched files. For routing/planning/agent changes, test through `python -m next.app_v5` with commands such as `diag`, `status`, `help`, and the affected direct command. Use `stability test` for broader regression checks, noting that it may launch browser automation and create report files.

## Commit & Pull Request Guidelines

No Git repository or history is present in this checkout. Use concise, imperative commit titles if this project is later placed under Git, for example `Fix relay response validation`. Pull requests should describe the user-visible change, list touched modules, include test commands run, and mention generated files or state changes.

## Security & Configuration Tips

Configuration is in `config.py`, including LM Studio and OpenAI endpoints. Do not commit API keys, browser profile data, generated relay responses, or backups. Avoid editing `Projects/BrowserProfile`, `__pycache__`, `.pyc` files, and generated reports unless the task explicitly requires it.
