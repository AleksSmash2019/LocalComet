import { describe, expect, it } from 'vitest';
import {
  ERROR_ENVELOPE_SCHEMA,
  describeUnknownError,
  errorDisplayText,
  isRetryableError,
  normalizeUnknownError,
  type NormalizedError
} from '$lib/errors/normalizedError';

/** The one string that must never reach a user or a log line. */
const FORBIDDEN = '[object Object]';

function assertNoObjectObject(error: NormalizedError): void {
  expect(error.message).not.toContain(FORBIDDEN);
  expect(error.code).not.toContain(FORBIDDEN);
}

describe('normalizeUnknownError — typed error envelope', () => {
  it('plain string rejection becomes unknown_error with the text preserved', () => {
    const normalized = normalizeUnknownError('sidecar is not responding');
    expect(normalized.schema).toBe(ERROR_ENVELOPE_SCHEMA);
    expect(normalized.code).toBe('unknown_error');
    expect(normalized.message).toBe('sidecar is not responding');
    expect(normalized.retryable).toBe(false);
    assertNoObjectObject(normalized);
  });

  it('empty string falls back to a human-readable message', () => {
    const normalized = normalizeUnknownError('');
    expect(normalized.message).not.toBe('');
    assertNoObjectObject(normalized);
  });

  it('JS Error instance keeps its message', () => {
    const normalized = normalizeUnknownError(new Error('boom'));
    expect(normalized.code).toBe('unknown_error');
    expect(normalized.message).toBe('boom');
    assertNoObjectObject(normalized);
  });

  it('legacy {code,message} pair maps onto the envelope', () => {
    const normalized = normalizeUnknownError({ code: 'invalid_patch_path', message: 'bad path' });
    expect(normalized.code).toBe('invalid_patch_path');
    expect(normalized.message).toBe('bad path');
    assertNoObjectObject(normalized);
  });

  it('code without message keeps the code as honest display marker', () => {
    expect(errorDisplayText({ code: 'permission_denied' })).toBe('permission_denied');
  });

  it('nested object never degrades into [object Object]', () => {
    const nested = { wrapper: { inner: { deep: { value: 42 } } } };
    const normalized = normalizeUnknownError(nested);
    assertNoObjectObject(normalized);
    expect(normalized.code).toBe('unrecognized_error_shape');
    expect(normalized.message).toContain('"deep"');
  });

  it('null and undefined get stable codes and human fallback', () => {
    for (const value of [null, undefined]) {
      const normalized = normalizeUnknownError(value);
      expect(normalized.code).toBe('unknown_error');
      expect(normalized.message.length).toBeGreaterThan(0);
      assertNoObjectObject(normalized);
    }
  });

  it('circular object is cycle-safe and bounded, never [object Object]', () => {
    const circular: Record<string, unknown> = { name: 'loop' };
    circular['self'] = circular;
    const normalized = normalizeUnknownError(circular);
    assertNoObjectObject(normalized);
    expect(normalized.code).toBe('unrecognized_error_shape');
    expect(normalized.message).toContain('[circular]');
  });

  it('JSON-unserializable object (BigInt) stays human-readable', () => {
    const normalized = normalizeUnknownError({ payload: 9007199254740993n });
    assertNoObjectObject(normalized);
    expect(normalized.message.length).toBeGreaterThan(0);
  });

  it('versioned envelope passes code/phase/correlation through (dispatch failure)', () => {
    const rejection = {
      schema: ERROR_ENVELOPE_SCHEMA,
      code: 'dispatch_failed',
      message: 'tool dispatch rejected',
      retryable: false,
      phase: 'tool_dispatch',
      correlation_id: 'req_abcdef123456'
    };
    const normalized = normalizeUnknownError(rejection);
    expect(normalized.code).toBe('dispatch_failed');
    expect(normalized.phase).toBe('tool_dispatch');
    expect(normalized.correlationId).toBe('req_abcdef123456');
    expect(normalized.retryable).toBe(false);
    assertNoObjectObject(normalized);
  });

  it('huge payloads are truncated in the structural dump', () => {
    const huge = { blob: 'x'.repeat(10_000) };
    const normalized = normalizeUnknownError(huge);
    expect(normalized.message.length).toBeLessThanOrEqual(530);
    expect(normalized.message).toContain('truncated');
    assertNoObjectObject(normalized);
  });

  it('secret-like keys are redacted before any detail reaches the UI', () => {
    const leaky = { authToken: 'super-secret-token-value', detail: 'disk full' };
    const normalized = normalizeUnknownError(leaky);
    expect(normalized.message).not.toContain('super-secret-token-value');
    assertNoObjectObject(normalized);
  });
});

describe('describeUnknownError / errorDisplayText', () => {
  it('describe returns message-only text without [object Object]', () => {
    expect(describeUnknownError({ a: { b: 1 } })).not.toContain(FORBIDDEN);
    expect(describeUnknownError(new Error('x'))).toBe('x');
  });

  it('backend diagnostic message wins over the code', () => {
    expect(errorDisplayText({ code: 'c', message: 'Путь вне workspace отклонён' })).toBe(
      'Путь вне workspace отклонён'
    );
  });

  it('cyrillic messages survive normalization unchanged', () => {
    const text = 'Ошибка выполнения: отказано в доступе';
    expect(describeUnknownError(text)).toBe(text);
    expect(text.includes('\u{fffd}')).toBe(false);
  });

  it('"Привет, LocalComet!" roundtrips byte-exact through every envelope path', () => {
    const greeting = 'Привет, LocalComet!';
    // As a raw rejection...
    expect(normalizeUnknownError(greeting).message).toBe(greeting);
    // ...as a backend {code,message} payload...
    expect(normalizeUnknownError({ code: 'tool_failed', message: greeting }).message).toBe(greeting);
    // ...and as display text — never degraded to replacement chars.
    expect(errorDisplayText({ code: 'c', message: greeting })).toBe(greeting);
    expect((JSON.stringify([greeting]).match(/\u{fffd}/gu) ?? []).length).toBe(0);
  });

  it('a long Russian sentence stays intact and bounded', () => {
    const sentence =
      'Проверка длинного русского сообщения для локального агента: каждый символ должен сохраняться без искажений в интерфейсе и журналах.';
    const normalized = normalizeUnknownError(sentence);
    expect(normalized.message).toBe(sentence);
    expect(normalized.message.includes('\u{fffd}')).toBe(false);
  });
});

describe('isRetryableError', () => {
  it('reflects the backend retryable flag', () => {
    const base = normalizeUnknownError({
      schema: ERROR_ENVELOPE_SCHEMA,
      code: 'sidecar_unavailable',
      message: 'sidecar stopped',
      retryable: true
    });
    expect(isRetryableError(base)).toBe(true);
  });

  it('known transient codes are retryable even from legacy pairs', () => {
    expect(isRetryableError(normalizeUnknownError({ code: 'bridge_unavailable' }))).toBe(true);
  });

  it('permanent failures are never retryable', () => {
    expect(isRetryableError(normalizeUnknownError({ code: 'permission_denied' }))).toBe(false);
    expect(isRetryableError(normalizeUnknownError('nope'))).toBe(false);
  });

  it('normalization is pure — repeated calls cannot form a retry loop', () => {
    const input = { code: 'grant_expired' };
    const first = normalizeUnknownError(input);
    const second = normalizeUnknownError(input);
    expect(first).toEqual(second);
    expect(first.retryable).toBe(false);
  });
});
