/**
 * Unified typed error envelope normalization (localcomet.error.v1).
 *
 * Every Tauri rejection — string, Error, legacy {code,message} object, nested
 * payload, null/undefined or even a circular structure — is normalized into
 * ONE NormalizedError. Nothing here may call String(object): an unknown shape
 * degrades to a stable code plus a human-readable fallback, never to
 * `[object Object]`. Details are bounded and secret-like keys are redacted.
 */

export const ERROR_ENVELOPE_SCHEMA = 'localcomet.error.v1';

export interface NormalizedError {
  readonly schema: typeof ERROR_ENVELOPE_SCHEMA;
  readonly code: string;
  readonly message: string;
  readonly retryable: boolean;
  readonly phase: string | null;
  readonly correlationId: string | null;
}

const MAX_DUMP_LENGTH = 512;
const FALLBACK_MESSAGE = 'Operation failed without a diagnostic message.';
const SECRET_KEY_PATTERN = /(token|secret|password|authorization|api[_-]?key|credential)/i;

/** Codes the backend marks as transient; UI retry stays user-driven. */
const RETRYABLE_CODES: ReadonlySet<string> = new Set([
  'sidecar_unavailable',
  'bridge_unavailable',
  'stream_timeout',
  'readiness_timeout',
  'model_stream_timeout',
  // Managed-runtime launch is now self-diagnosing: the envelope carries the
  // OS error and, for an early death, the process exit code. A user-driven
  // retry is therefore a real recovery path instead of a blind second
  // attempt. These three were the most common terminal dead-ends that never
  // offered a retry at all.
  'launch_failed',
  'runtime_exited',
  'model_does_not_fit'
]);

function safeStringify(value: unknown, maxLength = MAX_DUMP_LENGTH): string | null {
  const seen = new WeakSet<object>();
  try {
    const json = JSON.stringify(value, (key, val) => {
      if (typeof val === 'object' && val !== null) {
        if (seen.has(val)) return '[circular]';
        seen.add(val);
      }
      if (typeof val === 'string' && SECRET_KEY_PATTERN.test(key)) return '<redacted>';
      return val;
    });
    if (json === undefined || json === '') return null;
    return json.length > maxLength ? `${json.slice(0, maxLength)}…[truncated]` : json;
  } catch {
    return null;
  }
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() !== '' ? value : null;
}

function pickCorrelationId(candidate: Record<string, unknown>): string | null {
  const keys = ['correlation_id', 'correlationId', 'request_id', 'requestId'];
  for (const key of keys) {
    const value = asString(candidate[key]);
    if (value) return value.slice(0, 128);
  }
  return null;
}

function envelope(
  code: string,
  message: string,
  extra?: Partial<Omit<NormalizedError, 'schema' | 'code' | 'message'>>
): NormalizedError {
  return {
    schema: ERROR_ENVELOPE_SCHEMA,
    code: code.trim() !== '' ? code : 'unknown_error',
    message: message.trim() !== '' ? message : FALLBACK_MESSAGE,
    retryable: extra?.retryable ?? false,
    phase: extra?.phase ?? null,
    correlationId: extra?.correlationId ?? null
  };
}

/** Normalize ANY rejection value into the versioned envelope. Total function. */
export function normalizeUnknownError(error: unknown): NormalizedError {
  if (error === null || error === undefined) {
    return envelope('unknown_error', 'unknown error (no diagnostics)');
  }
  if (typeof error === 'string') {
    return envelope('unknown_error', error);
  }
  if (typeof error === 'number' || typeof error === 'boolean' || typeof error === 'bigint') {
    return envelope('unknown_error', `unknown error (${String(error)})`);
  }
  if (error instanceof Error) {
    return envelope('unknown_error', error.message || error.name || 'unknown error (Error)');
  }
  if (typeof error === 'object') {
    const candidate = error as Record<string, unknown>;
    // Versioned envelope from the Rust boundary — pass structured fields through.
    if ((candidate as { schema?: unknown }).schema === ERROR_ENVELOPE_SCHEMA) {
      return envelope(asString(candidate.code) ?? 'unknown_error', asString(candidate.message) ?? '', {
        retryable: candidate.retryable === true,
        phase: asString(candidate.phase),
        correlationId: pickCorrelationId(candidate)
      });
    }
    // Legacy typed pair {code, message}.
    const code = asString(candidate.code);
    const message = asString(candidate.message);
    if (code || message) {
      return envelope(code ?? 'unknown_error', message ?? code ?? '', {
        phase: asString(candidate.phase),
        correlationId: pickCorrelationId(candidate)
      });
    }
    // Unknown object shape: bounded structural dump instead of String(object).
    const dumped = safeStringify(error);
    return dumped
      ? envelope('unrecognized_error_shape', dumped)
      : envelope('unserializable_error_shape', 'unknown error (unserializable object)');
  }
  return envelope('unknown_error', FALLBACK_MESSAGE);
}

/** Human-readable message only — never contains `[object Object]`. */
export function describeUnknownError(error: unknown): string {
  return normalizeUnknownError(error).message;
}

/**
 * Display text for UI surfaces that previously embedded raw rejection values:
 * backend diagnostic message wins; a typed code without a message keeps the
 * code as an honest marker; everything else gets the human fallback.
 */
export function errorDisplayText(error: unknown): string {
  const normalized = normalizeUnknownError(error);
  if (
    normalized.code === 'unknown_error' ||
    normalized.code === 'unrecognized_error_shape' ||
    normalized.code === 'unserializable_error_shape'
  ) {
    return normalized.message;
  }
  return normalized.message === FALLBACK_MESSAGE ? normalized.code : normalized.message;
}

/** Retry affordance flag; callers own policy so no loop can form here. */
export function isRetryableError(error: NormalizedError): boolean {
  return error.retryable || RETRYABLE_CODES.has(error.code);
}
