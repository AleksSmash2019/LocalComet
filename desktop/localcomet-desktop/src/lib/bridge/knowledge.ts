import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { CONTROL_PLANE_EVENT_CHANNEL } from './controlPlane';
import type {
  KnowledgeAction,
  KnowledgeDecisionResponse,
  KnowledgeIntent,
  KnowledgePreview,
  KnowledgePreviewFailure,
  KnowledgePreviewSection,
  KnowledgePreviewSource
} from '$lib/knowledge/knowledgePreview';

type InvokeArgs = Readonly<Record<string, string | number>>;
const HASH_RE = /^sha256:[0-9a-f]{64}$/;
const TURN_RE = /^[0-9a-f]{24}$/;
const REQUEST_RE = /^kreq:\S{1,123}$/;
const INJECTION_RE = /^kinj:\S{1,123}$/;
const BUNDLE_RE = /^kb:[0-9a-f]{64}$/;
const ABSOLUTE_PATH_RE = /(?:[A-Za-z]:[\\/]|\\\\[^\\/\s]+[\\/]|\/(?:home|Users)\/)/i;

export async function requestKnowledgePreview(args: {
  turnId: string;
  intent: KnowledgeIntent;
  maxContextChars: number;
  maxResults: number;
}): Promise<KnowledgePreview | KnowledgePreviewFailure> {
  const payload = await invokeExact('knowledge_turn_preview', {
    turnId: validateTurnId(args.turnId),
    intent: validateIntent(args.intent),
    maxContextChars: boundedInteger(args.maxContextChars, 1, 12_000),
    maxResults: boundedInteger(args.maxResults, 1, 8)
  });
  return validatePreviewResponse(payload);
}

export async function decideKnowledgeTurn(args: {
  turnId: string;
  injectionId: string;
  expectedPreviewHash: string;
  action: KnowledgeAction;
}): Promise<KnowledgeDecisionResponse> {
  return validateDecisionResponse(
    await invokeExact('knowledge_turn_decide', {
      turnId: validateTurnId(args.turnId),
      injectionId: validateInjectionId(args.injectionId),
      expectedPreviewHash: validateHash(args.expectedPreviewHash),
      action: validateAction(args.action)
    })
  );
}

export async function subscribeKnowledgeInjectionEvents(
  callback: (injectionId: string) => void
): Promise<() => void> {
  const cleanup = await listen<unknown>(CONTROL_PLANE_EVENT_CHANNEL, (event) => {
    if (!isRecord(event.payload) || event.payload.method !== 'model.turn.started') return;
    const metadata = isRecord(event.payload.metadata) ? event.payload.metadata : {};
    const injectionId = metadata.knowledge_injection_id;
    if (typeof injectionId === 'string' && INJECTION_RE.test(injectionId)) callback(injectionId);
  });
  return () => cleanup();
}

async function invokeExact(command: string, args: InvokeArgs): Promise<unknown> {
  try {
    return await invoke(command, args);
  } catch (error) {
    throw normalizeKnowledgeError(error);
  }
}

function validatePreviewResponse(value: unknown): KnowledgePreview | KnowledgePreviewFailure {
  const object = expectRecord(value);
  rejectForbiddenFields(object);
  if (object.state === 'FAILED') {
    const error = expectRecord(object.error);
    if (typeof object.turn_id !== 'string' || typeof error.code !== 'string' || typeof error.safe_message !== 'string') throw invalid();
    return object as unknown as KnowledgePreviewFailure;
  }
  if (object.state !== 'PREVIEW_READY') throw invalid();
  validateTurnId(String(object.turn_id));
  if (!REQUEST_RE.test(String(object.request_id))) throw invalid();
  validateInjectionId(String(object.injection_id));
  if (!BUNDLE_RE.test(String(object.bundle_id))) throw invalid();
  validateHash(String(object.preview_hash));
  validateHash(String(object.vault_revision));
  validateIntent(String(object.resolved_intent) as KnowledgeIntent);
  if (!Array.isArray(object.sources)) throw invalid();
  const sources = object.sources.map(validateSource);
  const sourceCount = boundedInteger(Number(object.source_count), 0, 8);
  const totalChars = boundedInteger(Number(object.total_chars), 0, 12_000);
  if (sourceCount !== sources.length || object.truncated !== Boolean(object.truncated)) throw invalid();
  const measured = sources.reduce(
    (total, source) => total + source.selected_sections.reduce((sum, section) => sum + [...section.content].length, 0),
    0
  );
  if (measured !== totalChars || object.model_dispatched !== false || object.tools_executed !== 0) throw invalid();
  return { ...(object as unknown as KnowledgePreview), sources };
}

function validateSource(value: unknown): KnowledgePreviewSource {
  const object = expectRecord(value);
  const textFields = ['note_id', 'title', 'relative_path', 'knowledge_layer', 'evidence_class', 'authority', 'status'] as const;
  for (const field of textFields) {
    if (typeof object[field] !== 'string' || String(object[field]).length > 512) throw invalid();
  }
  const path = String(object.relative_path);
  if (!path || ABSOLUTE_PATH_RE.test(path) || path.split(/[\\/]/).includes('..')) throw invalid();
  if (typeof object.canonical !== 'boolean' || !Array.isArray(object.selected_sections)) throw invalid();
  const sections = object.selected_sections.map(validateSection);
  return { ...(object as unknown as KnowledgePreviewSource), selected_sections: sections };
}

function validateSection(value: unknown): KnowledgePreviewSection {
  const object = expectRecord(value);
  if (typeof object.heading !== 'string' || typeof object.content !== 'string') throw invalid();
  const lineStart = boundedInteger(Number(object.line_start), 1, 1_000_000);
  const lineEnd = boundedInteger(Number(object.line_end), lineStart, 1_000_000);
  if ([...object.content].length > 12_000 || ABSOLUTE_PATH_RE.test(object.content)) throw invalid();
  return object as unknown as KnowledgePreviewSection;
}

function validateDecisionResponse(value: unknown): KnowledgeDecisionResponse {
  const object = expectRecord(value);
  if (!['DECIDING', 'DISPATCHING', 'INJECTED', 'REJECTED', 'STALE'].includes(String(object.state))) throw invalid();
  validateTurnId(String(object.turn_id));
  validateInjectionId(String(object.injection_id));
  if (object.decision_source !== undefined && object.decision_source !== 'USER_APPROVAL') throw invalid();
  if (typeof object.model_dispatched !== 'boolean') throw invalid();
  return object as unknown as KnowledgeDecisionResponse;
}

function rejectForbiddenFields(value: Readonly<Record<string, unknown>>): void {
  const text = JSON.stringify(value);
  if (/serialized_context|vault_root|project_root|credential|api_key|binding_fingerprint/i.test(text)) throw invalid();
  if (ABSOLUTE_PATH_RE.test(text)) throw invalid();
}

function validateTurnId(value: string): string {
  if (!TURN_RE.test(value)) throw invalid();
  return value;
}

function validateInjectionId(value: string): string {
  if (!INJECTION_RE.test(value)) throw invalid();
  return value;
}

function validateHash(value: string): string {
  if (!HASH_RE.test(value)) throw invalid();
  return value;
}

function validateIntent(value: KnowledgeIntent): KnowledgeIntent {
  const allowed: readonly KnowledgeIntent[] = ['AUTO', 'CURRENT_STATE', 'ARCHITECTURE', 'SECURITY', 'HISTORY', 'FOUNDER_INTENT', 'ROADMAP', 'RESEARCH', 'OPERATIONAL', 'INCIDENT'];
  if (!allowed.includes(value)) throw invalid();
  return value;
}

function validateAction(value: KnowledgeAction): KnowledgeAction {
  if (!['INCLUDE_AND_SEND', 'REJECT_AND_SEND_WITHOUT_KNOWLEDGE', 'CANCEL'].includes(value)) throw invalid();
  return value;
}

function boundedInteger(value: number, minimum: number, maximum: number): number {
  if (!Number.isInteger(value) || value < minimum || value > maximum) throw invalid();
  return value;
}

function expectRecord(value: unknown): Readonly<Record<string, unknown>> {
  if (!isRecord(value)) throw invalid();
  return value;
}

function isRecord(value: unknown): value is Readonly<Record<string, unknown>> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function normalizeKnowledgeError(error: unknown): { code: string; message: string } {
  if (isRecord(error)) {
    return {
      code: String(error.code ?? 'knowledge_error').slice(0, 64),
      message: String(error.message ?? 'Project knowledge request failed').replace(/Traceback[\s\S]*/g, '<redacted>').slice(0, 240)
    };
  }
  return { code: 'knowledge_error', message: 'Project knowledge request failed' };
}

function invalid(): { code: 'invalid_payload'; message: string } {
  return { code: 'invalid_payload', message: 'Invalid Project Knowledge payload' };
}
