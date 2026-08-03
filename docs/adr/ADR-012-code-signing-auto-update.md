# ADR-012: Code Signing and Auto-Update Decision

Date: 2026-07-27
Status: ACCEPTED
Context: Level-up audit item 3 (code signing + auto-update)

## Decision

Target audience: **narrow circle** (непубличная раздача).

### Code Signing
- Status: NOT signed. NSIS installer is unsigned.
- Risk: Windows SmartScreen will show "Windows protected your PC" warning.
- Mitigation: document in README that this is expected for unsigned builds.
- Cost: EV code signing certificate $300-500/year.
- Decision: **accepted risk** for narrow-circle distribution.
  Revisit if audience expands to public.

### Auto-Update (Tauri Updater)
- Status: NOT configured. No updater section in tauri.conf.json.
- Decision: **not implemented** for narrow-circle distribution.
  Manual update via new installer is acceptable.
- If needed later: add `plugins.updater` to tauri.conf.json with
  endpoint URL + signing key. Requires hosting for update manifest.

### Implementation Plan (if audience changes to public)
1. Purchase EV code signing certificate ($300-500/yr)
2. Configure `signingIdentity` in tauri.conf.json bundle.windows
3. Add `plugins.updater` with endpoint + pubkey
4. Host update manifest (GitHub Releases or S3)
5. Add update check on app startup

## Consequences
- Users will see SmartScreen warning on first install
- README must document this expected behavior
- No automatic updates; users download new installer manually
