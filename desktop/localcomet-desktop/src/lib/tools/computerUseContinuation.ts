import type { ModelToolCall } from '$lib/types/modelGateway';

const MAX_CONTINUATION_TEXT = 240;
const NOTEPAD_TYPE_PROMPT_RE = /^(?:пожалуйста[,:]?\s+)?(?:открой|запусти|open|launch)\s+(?:приложение\s+)?(?:блокнот|notepad)(?:\.exe)?\s+(?:и|and)\s+(?<mode>напечатай|введи|набери|type|вставь|paste)\s*(?:(?:в\s+(?:нём|нем))|in\s+it)?\s*:?\s*(?<text>[^.!?\r\n]{1,240}(?:[.!?])?)$/iu;
const SECRET_MARKER_RE = /(?:lcap_[0-9a-f]{8,}|sk-[a-z0-9_-]{6,}|(?:api|access|refresh)[_-]?token\s*[=:]|(?:password|парол\w*|секрет\w*)\s*[=:])/iu;
const SECOND_ACTION_RE = /(?:^|[\s,;:])(?:затем|потом|после этого|then|after that|открой|запусти|open|launch|нажми|click|press)(?=[\s,;:]|$)/iu;
const BROWSER_SEARCH_PROMPT_RE = /^(?:открой|запусти|open|launch)\s+(?:браузер|browser|chrome|хром|edge|msedge|firefox|мозил\w*)(?:\s+и)?\s+(?:найди|поищи|ищи|find|search for|google)\s+(?<query>[^.!?\r\n]{1,180}?)(?:\.\s*(?<guard>ничего не отправляй и не заполняй формы|ничего не отправляй|ничего не заполняй(?: формы)?|do not submit|do not fill forms|without submitting|without filling forms))?[.!?]?$/iu;

function normalizedPrompt(prompt: string): string {
  return prompt.normalize('NFC').replace(/\s+/gu, ' ').trim();
}

/**
 * Derive one prevalidated continuation only for the explicit safe smoke shape:
 * open allowlisted Notepad, then type or paste one bounded non-secret marker. The helper
 * never derives a continuation for another app, an arbitrary plan, or a prompt
 * containing a second step. The returned object intentionally has no generated
 * id; the store creates a fresh correlated model action id at execution time.
 */
export function deriveBoundedNotepadTypeContinuation(
  prompt: string,
  firstCall: Pick<ModelToolCall, 'name' | 'arguments'>
): Omit<ModelToolCall, 'id'> | null {
  if (firstCall.name !== 'computer_use') return null;
  if (firstCall.arguments.action !== 'open_app' || String(firstCall.arguments.target).toLowerCase() !== 'notepad') {
    return null;
  }
  const match = NOTEPAD_TYPE_PROMPT_RE.exec(normalizedPrompt(prompt));
  if (!match?.groups?.text) return null;
  const text = match.groups.text.trim();
  if (!text || text.length > MAX_CONTINUATION_TEXT || SECRET_MARKER_RE.test(text) || SECOND_ACTION_RE.test(text)) return null;
  const action = /^(?:вставь|paste)$/iu.test(match.groups.mode ?? '') ? 'paste' : 'type';
  return {
    name: 'computer_use',
    arguments: { action, text }
  };
}

/**
 * Derive one interaction-only browser search after the Rust broker has verified
 * an explicit Chrome launch. The prompt grammar is intentionally narrow: it
 * accepts one bounded query plus the known read-only guard sentence, rejects
 * secret/URL-like content, and never derives a second host action.
 */
export function deriveBoundedBrowserSearchContinuation(
  prompt: string,
  firstCall: Pick<ModelToolCall, 'name' | 'arguments'>
): Omit<ModelToolCall, 'id'> | null {
  if (firstCall.name !== 'computer_use') return null;
  if (
    firstCall.arguments.action !== 'open_app' ||
    String(firstCall.arguments.target ?? '').toLowerCase() !== 'chrome'
  ) return null;
  const match = BROWSER_SEARCH_PROMPT_RE.exec(normalizedPrompt(prompt));
  const query = match?.groups?.query?.trim();
  if (!query || query.length > 180) return null;
  if (
    /[\u0000-\u001f\u007f]/u.test(query) ||
    SECRET_MARKER_RE.test(query) ||
    /(?:password|парол\w*|token|secret|https?:\/\/|file:|javascript:|скачай|download)/iu.test(query) ||
    SECOND_ACTION_RE.test(query)
  ) return null;
  return {
    name: 'computer_use',
    arguments: {
      action: 'open_url',
      target: 'chrome',
      url: `https://www.python.org/search/?q=${encodeURIComponent(query)}`
    }
  };
}
