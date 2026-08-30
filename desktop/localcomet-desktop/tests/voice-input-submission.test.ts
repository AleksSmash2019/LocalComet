import { describe, expect, it } from 'vitest';
import { createVoiceInputSubmissionGate } from '$lib/tools/voiceInputSubmission';

describe('voice input exactly-once submission gate', () => {
  it('accepts one finalized transcript and rejects duplicate final events', () => {
    const gate = createVoiceInputSubmissionGate();
    const session = gate.begin();
    expect(session).not.toBeNull();
    const first = gate.finalize(session!, '  Привет  ');
    expect(first).toEqual({ sessionId: session, transcript: 'Привет' });
    expect(gate.claimSubmit(session!)).toBe(true);
    expect(gate.finalize(session!, 'Привет ещё раз')).toBeNull();
    expect(gate.claimSubmit(session!)).toBe(false);
  });

  it('does not let a late callback from an old session affect a new session', () => {
    const gate = createVoiceInputSubmissionGate();
    const first = gate.begin()!;
    expect(gate.abort(first)).toBe(true);
    const second = gate.begin()!;
    expect(gate.finalize(first, 'stale')).toBeNull();
    expect(gate.finalize(second, 'fresh')).toEqual({ sessionId: second, transcript: 'fresh' });
    expect(gate.claimSubmit(second)).toBe(true);
  });

  it('keeps a submitted session alive across recognition end/error callbacks', () => {
    const gate = createVoiceInputSubmissionGate();
    const session = gate.begin()!;
    expect(gate.finalize(session, 'one request')).not.toBeNull();
    expect(gate.claimSubmit(session)).toBe(true);
    expect(gate.abort(session)).toBe(false);
    expect(gate.isSubmitting(session)).toBe(true);
    expect(gate.finish(session)).toBe(true);
    expect(gate.isCurrent(session)).toBe(false);
  });

  it('requires an explicit finish before a new recognition session can start', () => {
    const gate = createVoiceInputSubmissionGate();
    const session = gate.begin()!;
    expect(gate.begin()).toBeNull();
    expect(gate.finalize(session, '')).toBeNull();
    expect(gate.abort(session)).toBe(true);
    expect(gate.begin()).not.toBeNull();
  });
});
