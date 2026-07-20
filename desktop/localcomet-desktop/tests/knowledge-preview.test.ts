import { render } from 'svelte/server';
import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import KnowledgePreviewPanel from '../src/lib/components/knowledge/KnowledgePreviewPanel.svelte';
import KnowledgeSourceCard from '../src/lib/components/knowledge/KnowledgeSourceCard.svelte';
import KnowledgeToggle from '../src/lib/components/knowledge/KnowledgeToggle.svelte';
import { requestKnowledgePreview } from '../src/lib/bridge/knowledge';
import { locale, setLocale } from '../src/lib/i18n';
import type { KnowledgePreview, KnowledgePreviewSource } from '../src/lib/knowledge/knowledgePreview';
import {
  cancelProjectKnowledge,
  decideProjectKnowledge,
  knowledgePreviewStore,
  prepareProjectKnowledge,
  resetKnowledgePreviewStore,
  retryProjectKnowledgePreview,
  setProjectKnowledgeEnabled,
  toggleKnowledgeSource
} from '../src/lib/stores/knowledgePreview';

const TURN_ID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const CONTENT = 'Exact control plane section.';
const SOURCE: KnowledgePreviewSource = {
  note_id: 'architecture.control-plane',
  title: 'Control Plane boundary',
  relative_path: '01 Architecture/Control Plane.md',
  knowledge_layer: 'current_source_truth',
  evidence_class: 'A',
  authority: 'source',
  status: 'current',
  canonical: true,
  selected_sections: [{ heading: 'Boundary', line_start: 10, line_end: 12, content: CONTENT }]
};
const PREVIEW: KnowledgePreview = {
  state: 'PREVIEW_READY',
  turn_id: TURN_ID,
  request_id: 'kreq:00000000-0000-4000-8000-000000000001',
  injection_id: 'kinj:00000000-0000-4000-8000-000000000001',
  bundle_id: `kb:${'b'.repeat(64)}`,
  preview_hash: `sha256:${'c'.repeat(64)}`,
  vault_revision: `sha256:${'4'.repeat(64)}`,
  resolved_intent: 'AUTO',
  source_count: 1,
  total_chars: [...CONTENT].length,
  truncated: false,
  sources: [SOURCE],
  model_dispatched: false,
  tools_executed: 0
};

let commands: Array<{ command: string; args: Record<string, unknown> }> = [];
let response: unknown = PREVIEW;

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(async (command: string, args: Record<string, unknown>): Promise<unknown> => {
    commands.push({ command, args });
    if (command === 'knowledge_turn_decide') {
      return {
        state: args.action === 'CANCEL' || args.action === 'REJECT_AND_SEND_WITHOUT_KNOWLEDGE' ? 'REJECTED' : 'DISPATCHING',
        turn_id: TURN_ID,
        injection_id: PREVIEW.injection_id,
        decision_source: 'USER_APPROVAL',
        model_dispatched: args.action !== 'CANCEL'
      };
    }
    if (command === 'control_plane_cancel_turn') return { turn_id: TURN_ID, state: 'CANCELLED' };
    return response;
  })
}));

vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn(async () => () => undefined)
}));

beforeEach(() => {
  commands = [];
  response = PREVIEW;
  resetKnowledgePreviewStore();
  locale.set('ru');
});

describe('desktop knowledge preview and approval', () => {
  it('01 defaults OFF', () => expect(get(knowledgePreviewStore).enabled).toBe(false));
  it('02 starts in OFF lifecycle', () => expect(get(knowledgePreviewStore).lifecycle).toBe('OFF'));
  it('03 production control is truthfully unavailable and non-interactive', () => {
    const html = render(KnowledgeToggle).body;
    expect(html).toContain('Контекст проекта пока недоступен');
    expect(html).toContain('Это не долговременная память');
    expect(html).not.toContain('role="switch"');
    expect(html).not.toContain('<button');
  });
  it('04 enabling is session state', () => { setProjectKnowledgeEnabled(true); expect(get(knowledgePreviewStore).enabled).toBe(true); });
  it('05 disabling clears preview identity', () => { setProjectKnowledgeEnabled(true); setProjectKnowledgeEnabled(false); expect(get(knowledgePreviewStore).turnId).toBeNull(); });
  it('06 OFF prepare performs no invoke', async () => { await prepareProjectKnowledge(TURN_ID, 'prompt'); expect(commands).toHaveLength(0); });
  it('07 ON prepare invokes preview once', async () => { setProjectKnowledgeEnabled(true); await prepareProjectKnowledge(TURN_ID, 'prompt'); expect(commands).toHaveLength(1); });
  it('08 preview uses exact bounded command', async () => { setProjectKnowledgeEnabled(true); await prepareProjectKnowledge(TURN_ID, 'prompt'); expect(commands[0].command).toBe('knowledge_turn_preview'); });
  it('09 frontend payload has no query', async () => { setProjectKnowledgeEnabled(true); await prepareProjectKnowledge(TURN_ID, 'prompt'); expect(commands[0].args).not.toHaveProperty('query'); });
  it('10 frontend payload has no vault path', async () => { setProjectKnowledgeEnabled(true); await prepareProjectKnowledge(TURN_ID, 'prompt'); expect(commands[0].args).not.toHaveProperty('vaultRoot'); });
  it('11 preview reaches PREVIEW_READY', async () => { setProjectKnowledgeEnabled(true); await prepareProjectKnowledge(TURN_ID, 'prompt'); expect(get(knowledgePreviewStore).lifecycle).toBe('PREVIEW_READY'); });
  it('12 preview preserves injection identity', async () => { setProjectKnowledgeEnabled(true); await prepareProjectKnowledge(TURN_ID, 'prompt'); expect(get(knowledgePreviewStore).preview?.injection_id).toBe(PREVIEW.injection_id); });
  it('13 preview preserves source ordering', async () => { setProjectKnowledgeEnabled(true); await prepareProjectKnowledge(TURN_ID, 'prompt'); expect(get(knowledgePreviewStore).preview?.sources[0].note_id).toBe(SOURCE.note_id); });
  it('14 source card exposes provenance', () => { const html = render(KnowledgeSourceCard, { props: { source: SOURCE, expanded: false, onToggle: () => undefined } }).body; expect(html).toContain(SOURCE.relative_path); });
  it('15 collapsed source hides exact content', () => { const html = render(KnowledgeSourceCard, { props: { source: SOURCE, expanded: false, onToggle: () => undefined } }).body; expect(html).not.toContain(CONTENT); });
  it('16 expanded source shows exact content', () => { const html = render(KnowledgeSourceCard, { props: { source: SOURCE, expanded: true, onToggle: () => undefined } }).body; expect(html).toContain(CONTENT); });
  it('17 expansion is local and causes no invoke', () => { knowledgePreviewStore.set({ enabled: true, lifecycle: 'PREVIEW_READY', turnId: TURN_ID, pendingPrompt: 'prompt', preview: PREVIEW, expandedSourceIds: [], lastError: null }); toggleKnowledgeSource(SOURCE.note_id); expect(commands).toHaveLength(0); });
  it('18 expansion preserves injection identity', () => { knowledgePreviewStore.set({ enabled: true, lifecycle: 'PREVIEW_READY', turnId: TURN_ID, pendingPrompt: 'prompt', preview: PREVIEW, expandedSourceIds: [], lastError: null }); toggleKnowledgeSource(SOURCE.note_id); expect(get(knowledgePreviewStore).preview?.injection_id).toBe(PREVIEW.injection_id); });
  it('19 locale switch causes no invoke', () => { setLocale('en'); expect(commands).toHaveLength(0); });
  it('20 locale switch preserves preview', () => { knowledgePreviewStore.set({ enabled: true, lifecycle: 'PREVIEW_READY', turnId: TURN_ID, pendingPrompt: 'prompt', preview: PREVIEW, expandedSourceIds: [SOURCE.note_id], lastError: null }); setLocale('en'); expect(get(knowledgePreviewStore).preview?.injection_id).toBe(PREVIEW.injection_id); });
  it('21 RU approval button complete', () => { knowledgePreviewStore.set({ enabled: true, lifecycle: 'PREVIEW_READY', turnId: TURN_ID, pendingPrompt: 'prompt', preview: PREVIEW, expandedSourceIds: [], lastError: null }); expect(render(KnowledgePreviewPanel).body).toContain('Включить знания и отправить'); });
  it('22 EN approval button complete', () => { setLocale('en'); knowledgePreviewStore.set({ enabled: true, lifecycle: 'PREVIEW_READY', turnId: TURN_ID, pendingPrompt: 'prompt', preview: PREVIEW, expandedSourceIds: [], lastError: null }); expect(render(KnowledgePreviewPanel).body).toContain('Include knowledge and send'); });
  it('23 include supplies no decision_source', async () => { knowledgePreviewStore.set({ enabled: true, lifecycle: 'PREVIEW_READY', turnId: TURN_ID, pendingPrompt: 'prompt', preview: PREVIEW, expandedSourceIds: [], lastError: null }); await decideProjectKnowledge('INCLUDE_AND_SEND'); expect(commands[0].args).not.toHaveProperty('decisionSource'); });
  it('24 include uses exact preview hash', async () => { knowledgePreviewStore.set({ enabled: true, lifecycle: 'PREVIEW_READY', turnId: TURN_ID, pendingPrompt: 'prompt', preview: PREVIEW, expandedSourceIds: [], lastError: null }); await decideProjectKnowledge('INCLUDE_AND_SEND'); expect(commands[0].args.expectedPreviewHash).toBe(PREVIEW.preview_hash); });
  it('25 include locks lifecycle while deciding', async () => { knowledgePreviewStore.set({ enabled: true, lifecycle: 'PREVIEW_READY', turnId: TURN_ID, pendingPrompt: 'prompt', preview: PREVIEW, expandedSourceIds: [], lastError: null }); await decideProjectKnowledge('INCLUDE_AND_SEND'); expect(get(knowledgePreviewStore).lifecycle).toBe('DISPATCHING'); });
  it('26 cancel uses bounded decide command and remains truthful', async () => { knowledgePreviewStore.set({ enabled: true, lifecycle: 'PREVIEW_READY', turnId: TURN_ID, pendingPrompt: 'prompt', preview: PREVIEW, expandedSourceIds: [], lastError: null }); await cancelProjectKnowledge(); expect(commands[0].args.action).toBe('CANCEL'); expect(get(knowledgePreviewStore).lifecycle).toBe('CANCELLED'); });
  it('27 retrieval failure never starts model', async () => { response = { state: 'FAILED', turn_id: TURN_ID, injection_id: null, error: { code: 'offline', safe_message: 'Unavailable' }, model_dispatched: false, tools_executed: 0 }; setProjectKnowledgeEnabled(true); await prepareProjectKnowledge(TURN_ID, 'prompt'); expect(commands.map((call) => call.command)).not.toContain('model_turn_start'); });
  it('28 retrieval failure is explicit FAILED', async () => { response = { state: 'FAILED', turn_id: TURN_ID, injection_id: null, error: { code: 'offline', safe_message: 'Unavailable' }, model_dispatched: false, tools_executed: 0 }; setProjectKnowledgeEnabled(true); await prepareProjectKnowledge(TURN_ID, 'prompt'); expect(get(knowledgePreviewStore).lifecycle).toBe('FAILED'); });
  it('29 retry is explicit second preview call', async () => { response = { state: 'FAILED', turn_id: TURN_ID, injection_id: null, error: { code: 'offline', safe_message: 'Unavailable' }, model_dispatched: false, tools_executed: 0 }; setProjectKnowledgeEnabled(true); await prepareProjectKnowledge(TURN_ID, 'prompt'); response = PREVIEW; await retryProjectKnowledgePreview(); expect(commands.filter((call) => call.command === 'knowledge_turn_preview')).toHaveLength(2); });
  it('30 malformed absolute path response fails closed', async () => { response = { ...PREVIEW, sources: [{ ...SOURCE, relative_path: 'C:/Vault/secret.md' }] }; await expect(requestKnowledgePreview({ turnId: TURN_ID, intent: 'AUTO', maxContextChars: 12000, maxResults: 8 })).rejects.toMatchObject({ code: 'invalid_payload' }); });
  it('31 malformed serialized wrapper response fails closed', async () => { response = { ...PREVIEW, serialized_context: 'secret' }; await expect(requestKnowledgePreview({ turnId: TURN_ID, intent: 'AUTO', maxContextChars: 12000, maxResults: 8 })).rejects.toMatchObject({ code: 'invalid_payload' }); });
  it('32 source cards are keyboard buttons', () => expect(render(KnowledgeSourceCard, { props: { source: SOURCE, expanded: false, onToggle: () => undefined } }).body).toContain('<button'));
});
