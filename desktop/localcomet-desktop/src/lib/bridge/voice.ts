import { invoke } from '@tauri-apps/api/core';
import type { Language } from '$lib/i18n/locales';
import type { VoiceGender } from '$lib/stores/uiPreferences';

/**
 * Monotonic client-side generation for the current speech session. Turning
 * voice output off invalidates every in-flight request, including one whose
 * Tauri invoke has not resolved yet. Re-enabling does not replay the last
 * completed response because the shared voice bridge owns its request-id guard.
 */
let speechGeneration = 0;
let lastClaimedSpeechRequestId: string | null = null;

/** Claim a completed assistant request exactly once across component remounts. */
export function claimSpeechRequest(requestId: string): boolean {
  if (!requestId || requestId === lastClaimedSpeechRequestId) return false;
  lastClaimedSpeechRequestId = requestId;
  return true;
}

function ttsLanguageTag(language: Language): 'ru-RU' | null {
  if (language === 'ru') return 'ru-RU';
  return null;
}

export async function speakLocalText(
  text: string,
  voiceGender: VoiceGender = 'female',
  language: Language = 'ru'
): Promise<void> {
  const languageTag = ttsLanguageTag(language);
  if (!languageTag) return;
  const generation = speechGeneration;
  try {
    await invoke('speak_local_text', {
      text,
      language: languageTag,
      voice_profile: voiceGender
    });
  } catch {
    // Local-only speech must never fall back to browser or remote synthesis.
  }
  // Keep the generation read here as an explicit lifecycle checkpoint. The
  // backend stop command is authoritative for interrupting audio; this guard
  // prevents a stale promise from being treated as a current speech session.
  if (generation !== speechGeneration) return;
}

/** Stop current local playback and invalidate all in-flight speech calls. */
export async function stopLocalText(): Promise<boolean> {
  speechGeneration += 1;
  try {
    await invoke('stop_local_text');
    return true;
  } catch {
    return false;
  }
}
