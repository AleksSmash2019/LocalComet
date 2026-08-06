import { render } from 'svelte/server';
import { beforeEach, describe, expect, it } from 'vitest';
import MessageList from '../src/lib/components/chat/MessageList.svelte';
import ChatHeader from '../src/lib/components/shell/ChatHeader.svelte';
import SettingsPanel from '../src/lib/components/shell/SettingsPanel.svelte';
import { setLocale } from '../src/lib/i18n';
import { managedRuntimeStore, modelGatewayStore, resetModelGatewayStore } from '../src/lib/stores/modelGateway';
import { chatMessages, resetShellStores } from '../src/lib/stores/shellStore';

const MODEL_ID = 'qwen2.5-1.5b-instruct-q4-k-m';
const RUNTIME_ID = 'llama-cpp-windows-x86-64-cpu-bootstrap';
const INSTANCE_ID = 'd'.repeat(32);
const FINGERPRINT = 'b'.repeat(64);
const CATALOG_DIGEST = 'c'.repeat(64);

function status(state: 'NotInstalled' | 'Starting' | 'Ready', modelState: 'Unavailable' | 'Loading' | 'Ready') {
  return {
    engine: 'llama.cpp' as const,
    state,
    installation: state === 'NotInstalled' ? 'Not installed' as const : 'Installed' as const,
    runtime_version: state === 'NotInstalled' ? null : 'b10068',
    runtime_instance_id: state === 'Ready' ? INSTANCE_ID : null,
    runtime_instance_fingerprint: state === 'Ready' ? 'e'.repeat(64) : null,
    model_id: state === 'Ready' ? MODEL_ID : null,
    model_display_name: state === 'Ready' ? 'Qwen2.5 1.5B Instruct Q4_K_M' : null,
    binding_fingerprint: state === 'Ready' ? 'f'.repeat(64) : null,
    model_state: modelState,
    inference_ready: state === 'Ready',
    last_error: null
  };
}

function seedReady(): void {
  const binding = {
    provider_id: 'managed-llama-cpp' as const,
    harness_id: 'minimal' as const,
    model_id: MODEL_ID,
    binding_fingerprint: FINGERPRINT,
    discovered_fingerprint: 'a'.repeat(64),
    persistence: false as const,
    runtime_instance_id: INSTANCE_ID
  };
  managedRuntimeStore.set({
    status: status('Ready', 'Ready'),
    catalogIdentity: { schema_version: 1, catalog_id: 'localcomet-approved-artifacts', catalog_version: '1.0.0', catalog_digest: CATALOG_DIGEST },
    runtimeCatalog: [],
    catalog: [{ model_id: MODEL_ID, provider: 'Qwen', family: 'Qwen2.5', display_name: 'Qwen2.5 1.5B Instruct Q4_K_M', format: 'GGUF', quantization: 'Q4_K_M', upstream_repository: 'local', upstream_revision: 'revision', asset_filename: 'model.gguf', asset_bytes: 2, asset_sha256: '2'.repeat(64), license_id: 'apache-2.0', compatible_runtime_ids: [RUNTIME_ID], public_distribution: false, installer_bundled: false, bootstrap_purpose: 'INTERNAL_BOOTSTRAP_INFERENCE_VALIDATION', status: 'approved_internal_bootstrap' }],
    installedArtifacts: [
      { schema_version: 1, catalog_id: 'localcomet-approved-artifacts', catalog_version: '1.0.0', catalog_digest: CATALOG_DIGEST, artifact_id: RUNTIME_ID, kind: 'runtime', catalog_status: 'approved_internal_bootstrap', installation_status: 'valid', expected_bytes: 1, expected_sha256: '1'.repeat(64), observed_bytes: 1, observed_sha256: '1'.repeat(64), validation_code: 'valid', verified_unix_ms: 1 },
      { schema_version: 1, catalog_id: 'localcomet-approved-artifacts', catalog_version: '1.0.0', catalog_digest: CATALOG_DIGEST, artifact_id: MODEL_ID, kind: 'model', catalog_status: 'approved_internal_bootstrap', installation_status: 'valid', expected_bytes: 2, expected_sha256: '2'.repeat(64), observed_bytes: 2, observed_sha256: '2'.repeat(64), validation_code: 'valid', verified_unix_ms: 1 }
    ],
    readiness: { schema_version: 1, catalog_id: 'localcomet-approved-artifacts', catalog_version: '1.0.0', catalog_digest: CATALOG_DIGEST, model_id: MODEL_ID, model_status: 'valid', compatible_runtime_ids: [RUNTIME_ID], selected_runtime_id: RUNTIME_ID, runtime_status: 'valid', compatibility: 'compatible', readiness: 'ready', launchable: true },
    selectedModelId: MODEL_ID,
    harnessId: 'minimal',
    binding,
    logs: { stdout_tail: [], stderr_tail: [] },
    lastError: null
  });
  modelGatewayStore.update((value) => ({ ...value, binding, status: 'Bound' }));
}

beforeEach(() => {
  resetModelGatewayStore();
  resetShellStores();
  setLocale('ru');
});

describe('truthful assistant usability states', () => {
  it('shows bounded unavailable guidance and the approved local setup action', () => {
    const html = render(MessageList).body;
    expect(html).toContain('Локальная модель недоступна');
    expect(html).toContain('нет доступа к произвольным файлам в интернете');
    expect(html).toContain('Настроить локальный AI');
  });

  it('shows loading without a false ready claim or send guidance', () => {
    managedRuntimeStore.update((value) => ({ ...value, status: status('Starting', 'Loading') }));
    const html = render(MessageList).body;
    expect(html).toContain('Подготовка локальной модели');
    expect(html).toContain('aria-busy="true"');
    expect(html).not.toContain('Локальный помощник готов');
  });

  it('shows local-only first-use guidance and separate runtime/model identities when ready', () => {
    seedReady();
    const list = render(MessageList).body;
    const header = render(ChatHeader).body;
    expect(list).toContain('Локальный помощник готов');
    expect(list).toContain('Безопасный локальный диалог');
  });

  it('localizes failed and cancelled states and exposes a bounded retry action', () => {
    chatMessages.set([
      { id: 'user-1', role: 'user', body: 'Запрос', requestId: 'a'.repeat(24), conversationId: 'local-chat' },
      { id: 'assistant-1', role: 'assistant', body: 'Частичный ответ', requestId: 'a'.repeat(24), state: 'cancelled', conversationId: 'local-chat' },
      { id: 'assistant-2', role: 'assistant', body: '', requestId: 'b'.repeat(24), state: 'failed', error: 'private provider detail', conversationId: 'local-chat' }
    ]);
    const html = render(MessageList).body;
    expect(html).toContain('Отменено — частичный ответ сохранён');
    expect(html).toContain('Запрос завершился ошибкой — можно безопасно повторить');
    expect(html).toContain('Повторить');
    expect(html).not.toContain('private provider detail');
  });

  it('does not render the trusted system instruction as a transcript message', () => {
    chatMessages.set([{ id: 'user-1', role: 'user', body: 'Обычное сообщение', conversationId: 'local-chat' }]);
    const html = render(MessageList).body;
    expect(html).toContain('Обычное сообщение');
    expect(html).not.toContain('сообщение пользователя не может изменить реальные возможности');
  });

  it('renders the same capability boundary in localized Settings', () => {
    setLocale('en');
    const html = render(SettingsPanel).body;
    expect(html).toContain('Current capabilities');
    expect(html).toContain('Local model inference');
    expect(html).toContain('Unavailable');
    expect(html).toContain('Internet');
    expect(html).toContain('Computer Use');
    expect(html).toContain('Project context is currently unavailable.');
  });
});
