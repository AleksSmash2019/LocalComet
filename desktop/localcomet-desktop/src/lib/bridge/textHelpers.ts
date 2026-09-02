//! Shared bridge-level text helpers. Only semantics-identical copies are
//! centralised here; validators with file-specific behaviour (different
//! error payloads, throw styles, or redaction chains) intentionally stay
//! in their own bridge modules.

/** Truncate a string to `limit` characters without any sanitisation. */
export function bounded(value: string, limit: number): string {
  return value.slice(0, limit);
}

/** Redact tracebacks and API-key-looking tokens from error text. */
export function sanitizeErrorText(value: string): string {
  return value
    .replace(/Traceback[\s\S]*/g, '<redacted>')
    .replace(/sk-[A-Za-z0-9_-]{8,}/g, '<redacted>');
}
