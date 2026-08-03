# MVP-P0-C — REACHABILITY

## Correlation Matrix

| Scenario | Expected state | Pending consumed | Public error | Test |
|----------|---------------|-----------------|--------------|------|
| Valid startup ready | READY | Yes | — | p0c_ready_requires_correlated_response |
| Wrong generation | CHALLENGE_SENT | No | sidecar_health_generation_mismatch | p0c_wrong_generation_rejected |
| Wrong nonce | CHALLENGE_SENT | No | sidecar_health_nonce_mismatch | p0c_wrong_nonce_rejected |
| Wrong runtime | CHALLENGE_SENT | No | sidecar_health_runtime_mismatch | p0c_wrong_runtime_instance_rejected |
| Unknown request | — | No | sidecar_health_request_unknown | p0c_unknown_request_rejected |
| Duplicate | — | No | sidecar_health_response_duplicate | p0c_duplicate_response_distinguished |
| Expired | — | No | sidecar_health_request_unknown | p0c_expired_request_rejected |
| Process exit | STOPPED | All cancelled | sidecar_process_exited | p0c_process_exit_clears_ready |
| Restart stale response | STARTING | No | sidecar_health_generation_mismatch | p0c_restart_rejects_old_response |
| Capability true | CHALLENGE_SENT | No | sidecar_health_capability_mismatch | p0c_tool_execution_true_rejected |
| Malformed frame | — | No | sidecar_health_frame_invalid | p0c_duplicate_request_id_key_rejected |

## Lifecycle Matrix

| Event | Before | After | READY visible | Old response accepted |
|-------|--------|-------|---------------|----------------------|
| spawn | STOPPED | STARTING | No | No |
| challenge | STARTING | CHALLENGE_SENT | No | No |
| ready | CHALLENGE_SENT | READY | Yes | No |
| degraded | READY | DEGRADED | No | No |
| stop | READY | STOPPING | No | No |
| exit | READY | STOPPED | No | No |
| restart | STOPPED | STARTING | No | No (new generation) |
| concurrent start | STARTING | STARTING (busy) | No | No |
| start/stop race | STARTING | STOPPING | No | No (cancelled) |
