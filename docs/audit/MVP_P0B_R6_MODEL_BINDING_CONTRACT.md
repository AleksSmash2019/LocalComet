# MVP-P0-B-R6 — MODEL BINDING CONTRACT (FROZEN)

Status: FROZEN before GREEN implementation
Cycle: MVP-P0-B-R6
Date: 2026-07-30

## Semantic Fields (approval input == execution input == digest input)

Exactly five fields. No renderer-controlled authorization boolean.

| Field | Type | Required |
|---|---|---|
| provider_id | string | yes |
| harness_id | string | yes |
| port | u16 / null | conditional (required for openai-compatible-local) |
| model_id | string | yes |
| runtime_instance_id | string / null | conditional (required for managed-llama-cpp) |

## Rust Tauri Command Signature (post-R6)

```rust
pub async fn model_binding_set(
    state: State<'_, Arc<ControlPlaneBridge>>,
    artifacts: State<'_, Arc<ArtifactTrustService>>,
    approval: State<'_, crate::approval_commands::ApprovalState>,
    provider_id: String,
    harness_id: String,
    port: Option<u16>,
    model_id: String,
    runtime_instance_id: Option<String>,
    token: String,
    approval_id: String,
    call_id: String,
) -> Result<Value, BridgeError>
```

No parameter named: confirmed, approved, userDecision, user_decision, force.

## TypeScript Invoke Shape

```ts
invoke('model_binding_set', {
  providerId: string,
  harnessId: string,
  modelId: string,
  token: string,
  approvalId: string,
  callId: string,
  port?: number,
  runtimeInstanceId?: string
})
```

No confirmed, approved, userDecision, or force field.

## Canonical Digest Object

SHA-256 over canonicalized JSON of exactly:

```json
{
  "provider_id": "<string>",
  "harness_id": "<string>",
  "port": <number|null>,
  "model_id": "<string>",
  "runtime_instance_id": "<string|null>"
}
```

Five keys. No confirmed key.

## Internal Python Compatibility Value

After validate_approval_token succeeds (approval validated, token atomically consumed),
Rust adds `"confirmed": true` to the payload forwarded to the Python sidecar.

This value:
- is NOT renderer-controlled
- is NOT in the approval input
- is NOT in the canonical digest
- is NOT a second authorization gate
- is constructed ONLY after approval consumption succeeds

## Semantic Equality Invariant

approval semantic input == protected Tauri semantic input == Rust canonical digest input

The Rust-to-Python compatibility field is outside this semantic contract.
