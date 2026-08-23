import { describe, expect, it } from 'vitest';
import {
  COMPUTER_USE_RESULT_SCHEMA,
  parseToolCallResult
} from '../src/lib/tools/computerUseEnvelope';

function envelope(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    schema_version: COMPUTER_USE_RESULT_SCHEMA,
    tool: 'computer_use',
    action: 'open_app',
    status: 'completed',
    terminal: true,
    succeeded: true,
    verification: 'verified',
    ...overrides
  };
}

describe('computerUseEnvelope shared classifier', () => {
  it('full verified contract is the only verified success', () => {
    expect(parseToolCallResult('computer_use', envelope()).kind).toBe('verified_success');
  });

  it('not_applicable verification is a terminal success for self-evident actions', () => {
    // wait/screenshot/paste primitives: the action's own execution report is
    // the result; the Python normalizer stamps not_applicable (never a bare
    // auto-"verified" for legacy ok=true).
    const outcome = parseToolCallResult('computer_use', envelope({ verification: 'not_applicable' }));
    expect(outcome.kind).toBe('verified_success');
  });

  it('missing or unknown verification is never a success', () => {
    const noVerification = envelope();
    delete (noVerification as Record<string, unknown>).verification;
    expect(parseToolCallResult('computer_use', noVerification).kind).toBe('failed');
    expect(parseToolCallResult('computer_use', envelope({ verification: 'banana' })).kind).toBe('failed');
  });

  it('launch_pending is never a success', () => {
    const pending = envelope({ status: 'launch_pending', terminal: false, succeeded: false, verification: 'pending' });
    expect(parseToolCallResult('computer_use', pending).kind).toBe('pending');
  });

  it('terminal=false alone keeps the result pending', () => {
    expect(parseToolCallResult('computer_use', envelope({ terminal: false })).kind).toBe('pending');
  });

  it('verification=pending keeps the result pending', () => {
    expect(parseToolCallResult('computer_use', envelope({ verification: 'pending' })).kind).toBe('pending');
  });

  it('completed without the full contract is not a success', () => {
    expect(parseToolCallResult('computer_use', envelope({ succeeded: false })).kind).toBe('failed');
    expect(parseToolCallResult('computer_use', envelope({ verification: 'failed' })).kind).toBe('failed');
    expect(parseToolCallResult('computer_use', envelope({ terminal: false, verification: 'verified' })).kind).toBe('pending');
  });

  it('blocked stays blocked, with reason', () => {
    const blocked = envelope({ status: 'blocked', succeeded: false, verification: 'failed', reason: 'policy' });
    const outcome = parseToolCallResult('computer_use', blocked);
    expect(outcome.kind).toBe('blocked');
    expect(outcome.reason).toBe('policy');
  });

  it('legacy ok=true is only an unverified success', () => {
    expect(parseToolCallResult('computer_use', { ok: true }).kind).toBe('unverified_success');
    expect(parseToolCallResult('computer_use', { ok: true }).kind).not.toBe('verified_success');
  });

  it('malformed shapes never pass', () => {
    expect(parseToolCallResult('computer_use', null).kind).toBe('malformed');
    expect(parseToolCallResult('computer_use', 'ok').kind).toBe('malformed');
    expect(parseToolCallResult('computer_use', [envelope()]).kind).toBe('malformed');
    expect(parseToolCallResult('computer_use', { schema_version: COMPUTER_USE_RESULT_SCHEMA, status: 'completed', ok: true }).kind).toBe('failed');
  });

  it('non-computer_use payloads without blocked/failed markers succeed', () => {
    expect(parseToolCallResult('files.read', { tool: 'files.read', content: 'x' }).kind).toBe('unverified_success');
    expect(parseToolCallResult('files.list', { tool: 'files.list', entries: [] }).kind).toBe('unverified_success');
  });

  it('non-computer_use blocked/failed markers are honored', () => {
    expect(parseToolCallResult('files.read', { blocked: true, reason: 'policy' }).kind).toBe('blocked');
    expect(parseToolCallResult('files.read', { ok: false, error: 'io' }).kind).toBe('failed');
  });
});
