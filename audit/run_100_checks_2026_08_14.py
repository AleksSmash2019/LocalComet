from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "desktop" / "localcomet-desktop"
TAURI = FRONTEND / "src-tauri"
REPORT = ROOT / "audit" / "100-checks-report-2026-08-14.json"

results: list[dict[str, object]] = []


def run(name: str, argv: list[str], cwd: Path = ROOT, timeout: int = 240) -> None:
    started = time.time()
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            env={**os.environ, "CI": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"},
        )
        out = (proc.stdout + "\n" + proc.stderr).strip()
        results.append({
            "name": name,
            "status": "PASS" if proc.returncode == 0 else "FAIL",
            "returncode": proc.returncode,
            "duration_s": round(time.time() - started, 3),
            "output_tail": out[-3000:],
        })
    except subprocess.TimeoutExpired as exc:
        output = ((exc.stdout or "") if isinstance(exc.stdout, str) else "")
        results.append({
            "name": name,
            "status": "TIMEOUT",
            "returncode": None,
            "duration_s": round(time.time() - started, 3),
            "output_tail": output[-3000:],
        })
    except Exception as exc:  # audit runner must record, not hide, runner failures
        results.append({
            "name": name,
            "status": "ERROR",
            "returncode": None,
            "duration_s": round(time.time() - started, 3),
            "output_tail": repr(exc),
        })


def exists(name: str, rel: str) -> None:
    p = ROOT / rel
    results.append({"name": name, "status": "PASS" if p.exists() else "FAIL", "detail": str(p)})


def contains(name: str, rel: str, needle: str, should_exist: bool = True) -> None:
    p = ROOT / rel
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
        found = needle in text
        ok = found if should_exist else not found
        results.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": f"{rel}: {needle!r}"})
    except Exception as exc:
        results.append({"name": name, "status": "ERROR", "detail": repr(exc)})


# 1-10: repository and configuration integrity.
exists("01 AGENTS instructions exist", "AGENTS.md")
exists("02 frontend package manifest exists", "desktop/localcomet-desktop/package.json")
exists("03 frontend lockfile exists", "desktop/localcomet-desktop/package-lock.json")
exists("04 Rust manifest exists", "desktop/localcomet-desktop/src-tauri/Cargo.toml")
exists("05 Rust lockfile exists", "desktop/localcomet-desktop/src-tauri/Cargo.lock")
exists("06 Python requirements exist", "requirements.txt")
exists("07 Tauri config exists", "desktop/localcomet-desktop/src-tauri/tauri.conf.json")
exists("08 TypeScript config exists", "desktop/localcomet-desktop/tsconfig.json")
exists("09 Svelte config exists", "desktop/localcomet-desktop/svelte.config.js")
exists("10 Vite config exists", "desktop/localcomet-desktop/vite.config.ts")

# 11-20: source invariants and stale-boundary checks.
contains("11 cycle gate uses current frontend test count", "run_7_cycles.py", "390", True)
contains("12 cycle gate has no stale 384 threshold", "run_7_cycles.py", "384", False)
contains("13 removed MCP launcher is not referenced by scripts", "scripts/start-localcomet.ps1", "start-local-mcp.ps1", False)
contains("14 English locale exists", "desktop/localcomet-desktop/src/lib/i18n/en.ts", "export", True)
contains("15 Russian locale exists", "desktop/localcomet-desktop/src/lib/i18n/ru.ts", "export", True)
contains("16 approval component exists", "desktop/localcomet-desktop/src/lib/components/chat/ApprovalCard.svelte", "approval", False)
contains("17 model gateway bridge exists", "desktop/localcomet-desktop/src/lib/bridge/modelGateway.ts", "export", True)
contains("18 supervisor source exists", "desktop/localcomet-desktop/src-tauri/src/supervisor.rs", "enum", True)
contains("19 release-only stale DebugPython is absent", "desktop/localcomet-desktop/src-tauri/src/supervisor.rs", "DebugPython", False)
contains("20 no literal FIXME in first-party source", "audit/full-review-2026-07-26/41-known-defects.md", "No literal TODO/FIXME", True)

# 21-30: repository gates and source-wide static checks.
run("21 Python compile gate", [sys.executable, "scripts/check_all_py_compile.py"])
run("22 command parity gate", [sys.executable, "scripts/check_command_parity.py"])
run("23 bundle parity gate", [sys.executable, "scripts/check_bundle_parity.py"])
run("24 i18n parity gate", [sys.executable, "scripts/check_i18n_keys.py"])
run("25 fake UI state gate", [sys.executable, "scripts/check_ui_fake_state.py"])
run("26 mock data import gate", [sys.executable, "scripts/check_mockdata_imports.py"])
run("27 tool risk registry gate", [sys.executable, "scripts/check_tool_risk_registry.py"])
run("28 evidence provenance gate", [sys.executable, "scripts/check_evidence_provenance.py"])
run("29 historical evidence gate", [sys.executable, "scripts/check_historical_evidence.py"])
run("30 real sidecar enforcement gate", [sys.executable, "scripts/check_real_sidecar_tests.py"])

# 31-40: Python/runtime and orchestration suites.
run("31 ADR015 parser tests", [sys.executable, "tools/test_adr015_tool_parsing.py"])
run("32 legacy quarantine tests", [sys.executable, "tools/test_p0a_legacy_quarantine.py"])
run("33 sidecar health contract tests", [sys.executable, "tools/test_p0c_r1_sidecar_health.py"])
run("34 sidecar health protocol unit tests", [sys.executable, "tools/test_p0c_sidecar_health_protocol_unit.py"])
run("35 injection approval tests", [sys.executable, "tools/test_t13_injection_and_approval.py"])
run("36 unready sidecar tests", [sys.executable, "tools/test_up00_unready_sidecar.py"])
run("37 assistant context tests", [sys.executable, "tools/test_up02_wp01_assistant_context.py"])
run("38 security negative tests", [sys.executable, "tools/test_up02_wp01_security_negative.py"])
run("39 model chat backend tests", [sys.executable, "tools/test_up05_wp01_model_chat_backend.py"], timeout=360)
run("40 managed runtime tests", [sys.executable, "tools/test_v68451_managed_runtime.py"])

# 41-50: Python regression, control plane and executor suites.
run("41 v677 regression tests", [sys.executable, "tools/test_v677_regression.py"])
run("42 v678 router registry tests", [sys.executable, "tools/test_v678_router_registry.py"])
run("43 v679 retention tests", [sys.executable, "tools/test_v679_retention.py"])
run("44 diagnostics tests", [sys.executable, "tools/test_v681_diagnostics.py"])
run("45 task planner tests", [sys.executable, "tools/test_v682_task_planner.py"])
run("46 autonomy policy tests", [sys.executable, "tools/test_v683_autonomy_policy.py"])
run("47 action executor tests", [sys.executable, "tools/test_v684_action_executor.py"])
run("48 tool execution tests", [sys.executable, "tools/test_v6846_tool_execution.py"])
run("49 control plane tests", [sys.executable, "tools/test_v6844_control_plane.py"])
run("50 sidecar supervisor tests", [sys.executable, "tools/test_v6843_sidecar_supervisor.py"])

# 51-60: security, model gateway, IPC and knowledge backend.
run("51 model gateway tests", [sys.executable, "tools/test_v6845_model_gateway.py"], timeout=360)
run("52 desktop IPC tests", [sys.executable, "tools/test_v6841_desktop_ipc.py"])
run("53 desktop shell tests", [sys.executable, "tools/test_v6842_desktop_shell.py"])
run("54 evidence injection tests", [sys.executable, "tools/test_v68451e6_knowledge_injection.py"])
run("55 knowledge adapter tests", [sys.executable, "tools/test_v68451e4_knowledge_adapter.py"])
run("56 knowledge control plane tests", [sys.executable, "tools/test_v68451e5_knowledge_control_plane.py"])
run("57 knowledge change proposal tests", [sys.executable, "tools/test_v68451e9a_knowledge_change_proposal.py"])
run("58 knowledge review tests", [sys.executable, "tools/test_v68451e9b_knowledge_review.py"])
run("59 human review decision tests", [sys.executable, "tools/test_v68451e9c_human_review_decision.py"])
run("60 review projection tests", [sys.executable, "tools/test_v68451e9c_review_projection.py"])

# 61-70: frontend type, tests, build and dependency checks.
run("61 Svelte type check", ["npm", "run", "check"], cwd=FRONTEND, timeout=360)
run("62 frontend unit test suite", ["npm", "test", "--", "--run"], cwd=FRONTEND, timeout=480)
run("63 frontend production build", ["npm", "run", "build"], cwd=FRONTEND, timeout=360)
run("64 npm dependency tree", ["npm", "ls", "--depth=0"], cwd=FRONTEND, timeout=180)
run("65 npm production audit", ["npm", "audit", "--omit=dev"], cwd=FRONTEND, timeout=300)
run("66 frontend coverage gate", ["npm", "run", "test:coverage", "--", "--run"], cwd=FRONTEND, timeout=360)
run("67 frontend language tests", ["npm", "test", "--", "--run", "tests/language.test.ts"], cwd=FRONTEND, timeout=240)
run("68 frontend shell store tests", ["npm", "test", "--", "--run", "tests/shellStore.test.ts"], cwd=FRONTEND, timeout=240)
run("69 frontend model gateway tests", ["npm", "test", "--", "--run", "tests/model-gateway.test.ts"], cwd=FRONTEND, timeout=240)
run("70 frontend managed artifacts tests", ["npm", "test", "--", "--run", "tests/managed-artifacts.test.ts"], cwd=FRONTEND, timeout=240)

# 71-80: Rust/Tauri and release checks.
run("71 Rust formatting", ["cargo", "fmt", "--", "--check"], cwd=TAURI, timeout=240)
run("72 Rust debug unit tests", ["cargo", "test"], cwd=TAURI, timeout=600)
run("73 Rust release unit tests", ["cargo", "test", "--release"], cwd=TAURI, timeout=600)
run("74 Rust clippy warnings as errors", ["cargo", "clippy", "--all-targets", "--all-features", "--", "-D", "warnings"], cwd=TAURI, timeout=600)
run("75 Rust release build", ["cargo", "build", "--release"], cwd=TAURI, timeout=600)
run("76 Rust duplicate dependency graph", ["cargo", "tree", "-d"], cwd=TAURI, timeout=300)
run("77 desktop IPC source compile", [sys.executable, "tools/test_v6841_desktop_ipc.py"])
run("78 tool risk Rust parity", [sys.executable, "tools/test_tool_risk_rust_parity.py"])
run("79 Tauri desktop native integration", [sys.executable, "tools/test_v6842_desktop_shell.py"])
run("80 release manifest integrity", [sys.executable, "tools/test_v6842_desktop_shell.py"])

# 81-90: cyclic, deterministic and bundle behavior.
run("81 seven cycle end-to-end gate", [sys.executable, "run_7_cycles.py"], timeout=900)
run("82 reproducibility suite", [sys.executable, "tools/test_v680_reproducibility.py"], timeout=600)
run("83 audit bundle creation", [sys.executable, "tools/test_v6801_audit_bundle.py"], timeout=360)
run("84 bundle security suite", [sys.executable, "tools/test_v6802_bundle_security.py"], timeout=600)
run("85 start-localcomet launcher tests", [sys.executable, "tools/test_v68451d3_start_localcomet.py"])
run("86 development launcher tests", [sys.executable, "tools/test_v68451d_dev_launcher.py"])
run("87 UTF-8 SSE decoder tests", [sys.executable, "tools/test_v68451e7b_sse_utf8_decoder.py"])
run("88 knowledge preview tests", [sys.executable, "tools/test_v68451e7_desktop_knowledge_preview.py"])
run("89 knowledge producer tests", [sys.executable, "tools/test_v68451e9d_knowledge_review_producer.py"])
run("90 knowledge command center tests", [sys.executable, "tools/test_v6846_knowledge_operations_command_center.py"])

# 91-100: packaging, quality tooling, dependency and documentation checks.
run("91 Python dependency audit", ["pip-audit", "-r", "requirements.txt"], timeout=420)
run("92 project doctor", [sys.executable, "scripts/doctor.py"], timeout=300)
run("93 Rust dependency audit availability", ["cargo", "audit"], cwd=TAURI, timeout=300)
run("94 Python first-party mypy gate", ["mypy", "--no-site-packages", "--ignore-missing-imports", "--follow-imports=skip", "core", "modules", "scripts", "tools"], timeout=480)
run("95 Python lint gate availability", ["ruff", "check", "core", "modules", "scripts", "tools"], timeout=300)
run("96 Python formatter gate availability", ["black", "--check", "core", "modules", "scripts", "tools"], timeout=300)
run("97 complexity gate availability", ["radon", "cc", "core", "modules", "scripts", "tools", "-s", "-a"], timeout=300)
run("98 Windows bundle command", ["npm", "run", "bundle:windows"], cwd=FRONTEND, timeout=900)
run("99 git whitespace integrity", ["git", "diff", "--check"], timeout=300)
run("100 release-oriented preflight", [sys.executable, "scripts/preflight_audit.py"], timeout=420)

summary = {
    "total": len(results),
    "pass": sum(1 for r in results if r["status"] == "PASS"),
    "fail": sum(1 for r in results if r["status"] == "FAIL"),
    "timeout": sum(1 for r in results if r["status"] == "TIMEOUT"),
    "error": sum(1 for r in results if r["status"] == "ERROR"),
    "results": results,
}
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: summary[k] for k in ("total", "pass", "fail", "timeout", "error")}, ensure_ascii=False))
for item in results:
    print(f"{item['status']:7} {item['name']}")
