# LocalComet Security Model

## D4 — files.rollback disposition (T9, path A)

**Decision date:** 2026-08  
**Status:** CLOSED — implemented as GUARDED  

### Rationale

`files.rollback` restores a target file from a caller-supplied snapshot path.
It is classified `GUARDED` (not `dangerous`) because:

1. Both target and snapshot paths are confined to `Projects/` via `safe_path()`.
2. Restoration requires an approval token before execution (INV-APPROVAL-001).
3. The operation is reversible: before overwriting, the current content is
   captured in the in-memory `_rollback_journal` so a subsequent
   `files.rollback_undo` call can restore the displaced version.
4. The snapshot file is never deleted — it remains available for audit.

`files.rollback_undo` is also `GUARDED` for the same reasons.

### Registry entries

Both functions are registered in
`security/invariants/tool_risk_levels.toml`:

```
files.rollback      guarded  requires_approval=true
files.rollback_undo guarded  requires_approval=true
```

### What is NOT provided at this stage

- No approval dialog / diff UI in the desktop frontend (requires separate task).
- No TTL on the in-memory journal (journal is bounded by process lifetime).
- No chunked transfer for large files (bounded by MAX_TOOL_FILE_BYTES = 1 MB).

### References

- ADR-013 (tool-execution-path)
- `modules/files.py::rollback`, `modules/files.py::rollback_undo`
- `scripts/check_tool_risk_registry.py` (gate)
