export type VoiceInputSessionState = 'listening' | 'finalizing' | 'submitted' | 'terminal';

export interface VoiceInputSubmission {
  readonly sessionId: number;
  readonly transcript: string;
}

interface ActiveSession {
  readonly sessionId: number;
  state: VoiceInputSessionState;
}

/**
 * Small synchronous gate for browser SpeechRecognition callbacks.
 *
 * SpeechRecognition can deliver multiple final events, an `error`/`end` pair,
 * or a late callback after the component started another session. The model
 * request path must see at most one finalized transcript for one recognition
 * session. This helper deliberately contains no timers, I/O, or model state.
 */
export function createVoiceInputSubmissionGate() {
  let nextSessionId = 0;
  let active: ActiveSession | null = null;

  return {
    begin(): number | null {
      if (active && active.state !== 'terminal') return null;
      const sessionId = ++nextSessionId;
      active = { sessionId, state: 'listening' };
      return sessionId;
    },

    finalize(sessionId: number, rawTranscript: string): VoiceInputSubmission | null {
      if (!active || active.sessionId !== sessionId || active.state !== 'listening') return null;
      const transcript = String(rawTranscript || '').trim();
      if (!transcript) return null;
      active.state = 'finalizing';
      return { sessionId, transcript };
    },

    claimSubmit(sessionId: number): boolean {
      if (!active || active.sessionId !== sessionId || active.state !== 'finalizing') return false;
      active.state = 'submitted';
      return true;
    },

    finish(sessionId: number): boolean {
      if (!active || active.sessionId !== sessionId) return false;
      active.state = 'terminal';
      active = null;
      return true;
    },

    abort(sessionId: number): boolean {
      if (!active || active.sessionId !== sessionId) return false;
      if (active.state === 'submitted') return false;
      active.state = 'terminal';
      active = null;
      return true;
    },

    isCurrent(sessionId: number): boolean {
      return active?.sessionId === sessionId;
    },

    isSubmitting(sessionId: number): boolean {
      return active?.sessionId === sessionId && (active.state === 'finalizing' || active.state === 'submitted');
    },

    state(sessionId: number): VoiceInputSessionState | null {
      return active?.sessionId === sessionId ? active.state : null;
    }
  };
}

export type VoiceInputSubmissionGate = ReturnType<typeof createVoiceInputSubmissionGate>;

export default createVoiceInputSubmissionGate;

// Keep the type referenced in generated declaration output for strict TS builds.
export type _VoiceInputSubmissionType = VoiceInputSubmission;

// No runtime side effects: this module is safe to import from UI tests and native WebView.
void (0 as never);
