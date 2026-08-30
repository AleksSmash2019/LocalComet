import { describe, expect, it } from 'vitest';
import {
  containsGrantRef,
  extractBrokerContinuationAndScrub,
  redactGrantRefsInPlace,
  stringifyForPersistence
} from '$lib/security/redactContinuation';

const TOKEN = 'cgr_f803c88af8d0b92c21b3b1893187159e';

describe('continuation secret redaction (F-03)', () => {
  it('extracts the handle and scrubs the raw token from the envelope', () => {
    const envelope = {
      status: 'launch_pending',
      execution: {
        pid: 42,
        continuation: {
          schema_version: 'cu.broker.continuation.grant.v1',
          grant_ref: TOKEN,
          grant_state: 'issued',
          step_index: 0
        }
      }
    };
    const handle = extractBrokerContinuationAndScrub(envelope);
    expect(handle).toEqual({ grantRef: TOKEN, stepIndex: 0 });
    // The shared envelope must no longer carry the raw secret...
    expect(containsGrantRef(envelope)).toBe(false);
    // ...so any stringify into chat card state is clean.
    expect(JSON.stringify(envelope)).not.toContain(TOKEN);
    expect(
      ((envelope as { execution: { continuation: Record<string, unknown> } }).execution
        .continuation['grant_state'])
    ).toBe('issued');
  });

  it('returns null for envelopes without a well-formed grant', () => {
    expect(extractBrokerContinuationAndScrub({ execution: {} })).toBeNull();
    expect(extractBrokerContinuationAndScrub(null)).toBeNull();
    expect(extractBrokerContinuationAndScrub({ execution: { continuation: { grant_ref: 'nope' } } })).toBeNull();
  });

  it('redacts raw tokens nested anywhere in a payload in place', () => {
    const payload = {
      log: `issued ${TOKEN} ok`,
      nested: [{ deep: { grant_ref: TOKEN } }],
      plain: 'untouched'
    };
    const out = redactGrantRefsInPlace(payload) as typeof payload;
    expect(JSON.stringify(out)).not.toContain(TOKEN);
    expect(out.log).toBe('issued <redacted:cgr> ok');
    expect(out.nested[0].deep.grant_ref).toBe('<redacted:cgr>');
    expect(out.plain).toBe('untouched');
  });

  it('detects token presence without mutating', () => {
    expect(containsGrantRef({ a: [TOKEN] })).toBe(true);
    expect(containsGrantRef({ a: ['cgr_short'] })).toBe(false);
    expect(containsGrantRef('clean')).toBe(false);
  });

  it('detector is stateless across repeated calls (lastIndex bug)', () => {
    // Regression: a /g detector keeps lastIndex between test() calls and
    // would SKIP every second matching string.
    for (let round = 0; round < 5; round += 1) {
      expect(containsGrantRef(TOKEN)).toBe(true);
      expect(containsGrantRef('no token here')).toBe(false);
      expect(containsGrantRef(TOKEN)).toBe(true);
    }
  });

  it('matching/non-matching/matching sequence never drops a match', () => {
    const seq = [TOKEN, 'plain', TOKEN, 'plain', { nested: [TOKEN] }];
    expect(seq.map((v) => containsGrantRef(v))).toEqual([true, false, true, false, true]);
  });

  it('accepts upper and lowercase hex, rejects short/malformed refs', () => {
    expect(containsGrantRef(`cgr_${'ABCDEF0123456789'.toLowerCase()}`)).toBe(true);
    expect(containsGrantRef(`cgr_${'ABCDEF0123456789'}`)).toBe(true);
    expect(containsGrantRef(`cgr_${'a'.repeat(8)}`)).toBe(true);
    // Fewer than 8 hex chars is not a real token shape.
    expect(containsGrantRef('cgr_1234567')).toBe(false);
    expect(containsGrantRef('cgr_')).toBe(false);
    expect(containsGrantRef('not_aGrant')).toBe(false);
  });

  it('redaction normalizes case while preserving other content', () => {
    const mixed = `ok cgr_ABCDEF0123456789 end ${TOKEN}`;
    const out = redactGrantRefsInPlace(mixed) as unknown as string;
    expect(out).not.toMatch(/cgr_[0-9a-fA-F]{8,}/);
    expect(out).toContain('ok');
    expect(out).toContain('end');
    expect(out).toBe('ok <redacted:cgr> end <redacted:cgr>');
  });

  // --- Sink-level guarantees: raw secret must die at each persistence sink ---

  it('SINK frontend tool card: stringified card state carries no raw token', () => {
    const envelope = {
      status: 'launch_pending',
      execution: { continuation: { grant_ref: TOKEN, step_index: 0 } }
    };
    extractBrokerContinuationAndScrub(envelope);
    // Exactly what the pending branch stores into the chat card:
    const cardResult = JSON.stringify(envelope);
    expect(cardResult).not.toContain(TOKEN);
    expect(containsGrantRef(cardResult)).toBe(false);
  });

  it('SINK error envelope: typed continuation failures expose codes, never the ref', () => {
    // Rust BridgeError paths return typed codes (e.g. continuation_replayed)
    // with no capability material interpolated into message/details.
    const typedFailure = {
      code: 'continuation_replayed',
      message: 'continuation_replayed',
      details: null
    };
    expect(JSON.stringify(typedFailure)).not.toContain(TOKEN);
    expect(containsGrantRef(typedFailure)).toBe(false);
    // And even if a future caller pastes an envelope into an error detail,
    // redaction scrubs it before persistence.
    const leakyDetail = { code: 'dispatch_failed', message: `ctx ${TOKEN}` };
    expect(
      JSON.stringify(redactGrantRefsInPlace(leakyDetail))
    ).not.toContain(TOKEN);
  });

  it('stringifyForPersistence is the gated serializer for every card-state sink', () => {
    // Clean payloads serialize byte-identically to plain JSON.stringify.
    const clean = { status: 'ok', detail: 'no secrets here' };
    expect(stringifyForPersistence(clean)).toBe(JSON.stringify(clean));
    // A leaking payload is scrubbed at the boundary, never persisted raw.
    const leaky = { status: 'ok', nested: { grant_ref: TOKEN } };
    const out = stringifyForPersistence(leaky);
    expect(out).not.toContain(TOKEN);
    expect(out).toContain('<redacted:cgr>');
    // Repeated use stays stateless (detector has no /g flag).
    expect(stringifyForPersistence([TOKEN, 'plain', TOKEN])).not.toContain(TOKEN);
    expect(stringifyForPersistence('plain')).toBe(JSON.stringify('plain'));
  });
});
