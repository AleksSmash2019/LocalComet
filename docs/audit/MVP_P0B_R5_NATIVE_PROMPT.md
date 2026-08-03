# MVP-P0-B-R5 — NATIVE PROMPT

Status: RETROACTIVE
Cycle: MVP-P0-B-R5
Date: 2026-07-30

## NativeWindowsApprovalPrompt

Implementation: src-tauri/src/approval.rs

- Uses MessageBoxW with MB_OKCANCEL | MB_ICONQUESTION
- Title: "LocalComet"
- Body: Tool, Risk, Target, Side-effect category
- Destructive operations show additional warning
- IDOK → ApprovalDecision::Approve
- IDCANCEL → ApprovalDecision::Reject
- Non-Windows platforms: ApprovalPromptError::Unavailable

## Trait Object Safety

ApprovalPrompt trait is object-safe (verified by p0b_r5_native_prompt_trait_object_safe).
ScriptedApprovalPrompt used in tests for deterministic behavior.

## Renderer Isolation

- No renderer parameter influences the prompt decision
- No IPC message carries a user decision boolean
- The prompt is entirely Rust-owned
