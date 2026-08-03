#!/usr/bin/env python3
"""LocalComet smoke test — verifies the REAL desktop sidecar product path.

Drives the actual DesktopSidecarRuntime in-process via localcomet_test_harness
(the same handle_message() entry point the runner uses). Each step prints only
the observed result. Expected rejections (duplicate id, blocked filesystem
methods) are part of success.

Scope: the desktop sidecar is a model-gateway/knowledge/session manager.
Filesystem tool execution is available via the tool.call method (ADR-013),
confined to the confirmed workspace; approval authorization is enforced in the
Rust control plane (execute_approved) and covered by `cargo test`, reported as
RUST-COVERED here rather than re-driven through the sidecar.

Exit: 0 = all steps gave the expected outcome
      1 = at least one step failed
      2 = environment/import unavailable
"""

import argparse
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

PASSED: list[int] = []
FAILED: list[int] = []


def ok(step: int, desc: str, detail: str = "") -> None:
    print(f"[{step:02d}] OK   {desc}" + (f" - {detail}" if detail else ""))
    PASSED.append(step)


def fail(step: int, desc: str, detail: str = "") -> None:
    print(f"[{step:02d}] FAIL {desc}" + (f" - {detail}" if detail else ""))
    FAILED.append(step)


def info(step: int, desc: str, detail: str = "") -> None:
    print(f"[{step:02d}] INFO {desc}" + (f" - {detail}" if detail else ""))


def run_smoke() -> int:
    try:
        from localcomet_test_harness import LocalCometHarness
    except ImportError as exc:
        print(f"ABORT: cannot import harness: {exc}", file=sys.stderr)
        return 2

    harness = LocalCometHarness(project_root=str(REPO_ROOT))

    # [01] Start sidecar (desktop hello handshake)
    try:
        pid, proto_version = harness.start_sidecar()
        ok(1, "sidecar start (hello handshake)", f"pid={pid} runtime={proto_version}")
    except Exception as exc:  # noqa: BLE001
        fail(1, "sidecar start", str(exc))
        return 1

    # [02] Readiness probe (active health request/response)
    try:
        status, ms = harness.readiness_probe(timeout_ms=5000)
        if status == "ready":
            ok(2, "readiness probe", f"status={status} time={ms}ms")
        else:
            fail(2, "readiness probe", f"status={status}")
    except Exception as exc:  # noqa: BLE001
        fail(2, "readiness probe", str(exc))

    # [03] runtime health
    try:
        health = harness.runtime_health()
        if (
            health.get("type") == "health.status"
            and health.get("protocolVersion") == 1
            and health.get("status") == "ready"
            and health.get("capabilities", {}).get("toolExecution") is False
        ):
            ok(3, "app.health", "typed health.status ready")
        else:
            fail(3, "app.health", f"unexpected: {health}")
    except Exception as exc:  # noqa: BLE001
        fail(3, "app.health", str(exc))

    # [04] capabilities advertised
    # NOTE: app.health is a lifecycle endpoint handled before the capability
    # check; it is NOT part of the advertised capability set. The hello payload
    # advertises the "lifecycle" marker plus control-plane / model-gateway /
    # knowledge methods. So we assert on real advertised capabilities here.
    try:
        caps = harness.capabilities()
        needed = {"lifecycle", "model.catalog.get"}
        if needed.issubset(set(caps)):
            ok(4, "capabilities advertised", f"{len(caps)} methods incl. lifecycle+model.catalog.get")
        else:
            fail(4, "capabilities advertised", f"missing {needed - set(caps)}")
    except Exception as exc:  # noqa: BLE001
        fail(4, "capabilities advertised", str(exc))

    # [05] duplicate message id is rejected
    try:
        req = harness.health_request("hreq_" + "d" * 32)
        first = harness.runtime.handle_message(req)
        dup = harness.runtime.handle_message(req)
        first_ok = any(
            r.get("payload", {}).get("type") == "health.status"
            and r.get("payload", {}).get("status") == "ready"
            for r in first
        )
        dup_rejected = any(
            r.get("payload", {}).get("code") == "duplicate_message_id" for r in dup
        )
        if first_ok and dup_rejected:
            ok(5, "duplicate message id rejected", "duplicate_message_id")
        else:
            fail(5, "duplicate message id rejected", f"first_ok={first_ok} dup_rejected={dup_rejected}")
    except Exception as exc:  # noqa: BLE001
        fail(5, "duplicate message id rejected", str(exc))

    # [06] tool.call executes a confined read-only files.read (ADR-013)
    try:
        import tempfile

        from modules.workspace_policy import workspace_digest

        with tempfile.TemporaryDirectory(prefix="lc_smoke_ws_") as ws:
            workspace = str(pathlib.Path(ws).resolve())
            (pathlib.Path(workspace) / "smoke.txt").write_text("smoke-ok", encoding="utf-8")
            base_payload = {
                "tool": "files.read",
                "input": {"path": "smoke.txt"},
                "workspace": workspace,
                "workspace_digest": workspace_digest(workspace),
                "session": "s" * 64,
            }
            reply = harness.request("tool.call", base_payload)
            payload = reply.get("payload", {})
            read_ok = (
                reply.get("type") == "response"
                and payload.get("tool") == "files.read"
                and payload.get("content") == "smoke-ok"
            )
            outside = dict(base_payload, input={"path": "../escape.txt"})
            blocked = harness.request("tool.call", outside)
            blocked_ok = (
                blocked.get("type") == "error"
                and blocked.get("payload", {}).get("code") == "policy_blocked"
            )
            if read_ok and blocked_ok:
                ok(6, "tool.call files.read confined (ADR-013)", "read ok + outside policy_blocked")
            else:
                fail(6, "tool.call files.read confined", f"read_ok={read_ok} blocked_ok={blocked_ok}")
    except Exception as exc:  # noqa: BLE001
        fail(6, "tool.call files.read confined", str(exc))

    # [07] model gateway catalog is reachable
    try:
        reply = harness.request("model.catalog.get", {})
        payload = reply.get("payload", {})
        if reply.get("type") == "response" and "providers" in payload:
            ok(7, "model.catalog.get", f"{len(payload.get('providers', []))} providers")
        else:
            fail(7, "model.catalog.get", f"unexpected: {reply.get('type')}")
    except Exception as exc:  # noqa: BLE001
        fail(7, "model.catalog.get", str(exc))

    # [08] shutdown produces goodbye
    try:
        replies = harness.runtime.handle_message(
            __import__("modules.desktop_ipc_contract_ru", fromlist=["make_request"]).make_request(
                "smoke-shutdown-000001", "app.shutdown", {}
            )
        )
        saw_goodbye = any(r.get("type") == "goodbye" for r in replies)
        if saw_goodbye:
            ok(8, "shutdown produces goodbye", "goodbye observed")
        else:
            fail(8, "shutdown produces goodbye", f"types={[r.get('type') for r in replies]}")
    except Exception as exc:  # noqa: BLE001
        fail(8, "shutdown produces goodbye", str(exc))

    # [09-12] Approval / workspace enforcement outside the read-only smoke path.
    info(9, "approval token scope/replay/digest", "RUST-COVERED: cargo test approval")
    info(10, "workspace confinement + token invalidation", "RUST-COVERED: cargo test workspace")
    info(11, "guarded tool without approval rejected", "RUST-COVERED: run_tool_call approval boundary")
    info(12, "workspace escape rejected", "SMOKE-COVERED: tool.call rejects ../escape.txt")

    print()
    print(f"Results: {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print(f"Failed steps: {FAILED}")
        return 1
    print("SMOKE PASSED: real sidecar product path behaves as expected.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["cli", "full"], default="full")
    parser.parse_args()
    sys.exit(run_smoke())
