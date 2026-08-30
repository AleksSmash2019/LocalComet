/**
 * Continuation-secret redaction (F-03).
 *
 * Contract: the Rust broker returns the raw `cgr_` token EXACTLY ONCE over
 * the typed Tauri response to the authorized caller. The consuming layer must
 * keep it only in bounded in-memory state for the one-time consume call and
 * must never let it reach chat cards, logs, or any persisted artifact. These
 * helpers are the single scrub site for that boundary.
 */

/**
 * Detector has NO /g flag: `RegExp.prototype.test` on a global regex is
 * stateful (`lastIndex`), so repeated calls could skip matching values.
 * Replacement keeps /g because `String.replace` with /g is stateless.
 */
const GRANT_REF_DETECTOR = /\bcgr_[0-9a-fA-F]{8,}\b/;
const GRANT_REF_REPLACER = /\bcgr_[0-9a-fA-F]{8,}\b/g;
const REDACTED = '<redacted:cgr>';

export interface BrokerContinuationHandle {
  readonly grantRef: string;
  readonly stepIndex: number;
}

/** True when a raw continuation token is still present anywhere in value. */
export function containsGrantRef(value: unknown): boolean {
  if (typeof value === 'string') return GRANT_REF_DETECTOR.test(value);
  if (Array.isArray(value)) return value.some(containsGrantRef);
  if (value && typeof value === 'object') {
    return Object.values(value).some(containsGrantRef);
  }
  return false;
}

/**
 * Persistence-boundary serializer for tool-card state and every other sink
 * that stringifies broker output into UI/durable state. The detector gates
 * the write: if a raw `cgr_…` token is still present anywhere in the value
 * (upstream bug or future regression), it is scrubbed before serialization,
 * so the returned string can never carry the secret.
 */
export function stringifyForPersistence(value: unknown): string {
  return JSON.stringify(containsGrantRef(value) ? redactGrantRefsInPlace(value) : value);
}

/**
 * Deeply replace every raw `cgr_…` token inside value with a typed marker.
 * Mutates containers in place AND returns them, so callers can redact the
 * exact object they are about to persist or stringify.
 */
export function redactGrantRefsInPlace<T>(value: T): T {
  if (typeof value === 'string') {
    return value.replace(GRANT_REF_REPLACER, REDACTED) as unknown as T;
  }
  if (Array.isArray(value)) {
    for (let index = 0; index < value.length; index += 1) {
      value[index] = redactGrantRefsInPlace(value[index]);
    }
    return value;
  }
  if (value && typeof value === 'object') {
    for (const key of Object.keys(value as Record<string, unknown>)) {
      const container = value as Record<string, unknown>;
      container[key] = redactGrantRefsInPlace(container[key]);
    }
    return value;
  }
  return value;
}

/**
 * Capture the opaque continuation capability out of a launch envelope and
 * scrub the raw secret from that envelope in the same step. Returns null when
 * the envelope carries no well-formed continuation grant.
 */
export function extractBrokerContinuationAndScrub(envelope: unknown): BrokerContinuationHandle | null {
  if (!envelope || typeof envelope !== 'object') return null;
  const execution = (envelope as { execution?: { continuation?: { grant_ref?: unknown; step_index?: unknown } } })
    .execution;
  const grantRef = execution?.continuation?.grant_ref;
  if (typeof grantRef !== 'string' || !grantRef.startsWith('cgr_')) return null;
  const stepIndexRaw = execution?.continuation?.step_index;
  const handle: BrokerContinuationHandle = {
    grantRef,
    stepIndex: typeof stepIndexRaw === 'number' ? stepIndexRaw : 0
  };
  // Remove the raw secret from the shared envelope before it can be
  // stringified into chat card state or any other persistence sink.
  delete execution?.continuation?.grant_ref;
  return handle;
}
