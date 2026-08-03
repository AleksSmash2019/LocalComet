# MVP-P0-C — HEALTH PROTOCOL CONTRACT (FROZEN)

Status: FROZEN before RED
Cycle: MVP-P0-C
Date: 2026-07-30

## Identifiers

### generation_id
- Type: u64, monotonically increasing within desktop process lifetime
- Never reused; incremented before every new sidecar launch attempt
- Old generations can never become READY again

### startup_nonce
- Format: scn_ + 64 lowercase hex characters (32 CSPRNG bytes)
- Generated fresh for every launch attempt via getrandom/BCryptGenRandom
- Never derived from PID, timestamp, generation ID, runtime ID, or request ID
- Never logged in full; never exposed to renderer
- Compared by exact equality (not prefix); no partial comparison

### runtime_instance_id
- Format: rti_ + 32 lowercase hex characters (16 CSPRNG bytes)
- Stable for one process generation; changes on restart
- Not inferred from PID alone

### request_id (health)
- Format: hreq_ + 32 lowercase hex characters (16 CSPRNG bytes)
- Independent per health challenge

## Health Check Request (Rust → Python)

```json
{
  "type": "health.check",
  "protocolVersion": 1,
  "requestId": "hreq_<32 hex>",
  "generationId": 1,
  "startupNonce": "scn_<64 hex>",
  "runtimeInstanceId": "rti_<32 hex>",
  "sentAtUnixMs": 0
}
```

Sent as IPC payload inside the existing localcomet.ipc/1.0 envelope:
```json
{
  "protocol": "localcomet.ipc",
  "version": "1.0",
  "type": "request",
  "id": "deskcp-<counter>",
  "method": "app.health",
  "payload": { <health.check fields above> }
}
```

## Health Status Response (Python → Rust)

```json
{
  "type": "health.status",
  "protocolVersion": 1,
  "requestId": "hreq_<32 hex>",
  "generationId": 1,
  "startupNonce": "scn_<64 hex>",
  "runtimeInstanceId": "rti_<32 hex>",
  "status": "ready",
  "receivedAtUnixMs": 0,
  "capabilities": {
    "toolExecution": false
  }
}
```

## Required Values

- protocolVersion = 1 (integer, not string)
- status ∈ {"starting", "ready", "degraded", "stopping"}
- capabilities.toolExecution = false (boolean, required)

## Capability Invariant

Rust rejects READY when:
- capabilities object missing
- toolExecution missing
- toolExecution = true
- toolExecution is non-boolean

This does NOT activate tools. It proves the running Python sidecar agrees with the current disabled execution policy.
