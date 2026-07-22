import { render } from 'svelte/server';
import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import FilesPanel from '../src/lib/components/files/FilesPanel.svelte';
import SettingsPanel from '../src/lib/components/shell/SettingsPanel.svelte';
import { previewSelectedFile } from '../src/lib/bridge/files';
import {
  addFiles,
  filesStore,
  forgetFile,
  includedFilesTotals,
  initializeFilesCapability,
  openFilePreview,
  reportFilesContextInclusion,
  resetFilesStore,
  setFileIncluded
} from '../src/lib/stores/files';
import { setLocale } from '../src/lib/i18n';
import type { FilesCapabilityStatus, SelectedFileSummary } from '../src/lib/types/files';

const FILE_ID = 'a'.repeat(64);
const SECOND_FILE_ID = 'b'.repeat(64);
const CAPABILITY: FilesCapabilityStatus = {
  available: true,
  read_only: true,
  selection: 'native_system_file_picker_only',
  persistence: 'current_process_memory_only',
  supported_extensions: ['txt', 'md', 'json', 'yaml', 'yml', 'csv', 'log'],
  maximum_file_bytes: 2 * 1024 * 1024,
  maximum_active_context_bytes: 5 * 1024 * 1024,
  maximum_selected_files: 32,
  preview_maximum_characters: 16_000
};
const FILE: SelectedFileSummary = {
  file_id: FILE_ID,
  filename: 'notes.md',
  extension: 'md',
  media_type: 'Markdown',
  byte_size: 10,
  character_count: 10,
  readable: true,
  status: 'ready',
  added_at_unix_ms: 1_750_000_000_000,
  display_location: '…\\Temp\\notes.md'
};
const SECOND_FILE: SelectedFileSummary = {
  ...FILE,
  file_id: SECOND_FILE_ID,
  filename: 'data.json',
  extension: 'json',
  media_type: 'JSON',
  byte_size: 12,
  character_count: 12,
  display_location: '…\\Temp\\data.json'
};

let commands: Array<{ command: string; args?: Record<string, unknown> }> = [];
let selectedFiles: readonly SelectedFileSummary[] = [];
let selectionError: unknown = null;

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(async (command: string, args?: Record<string, unknown>): Promise<unknown> => {
    commands.push({ command, args });
    if (command === 'files_capability_status') return CAPABILITY;
    if (command === 'list_selected_files') return selectedFiles;
    if (command === 'select_files') {
      if (selectionError) throw selectionError;
      return { cancelled: false, files: selectedFiles };
    }
    if (command === 'preview_selected_file') {
      return {
        file_id: args?.fileId,
        filename: 'notes.md',
        content: '# Preview\n',
        original_bytes: 10,
        original_characters: 10,
        displayed_bytes: 10,
        displayed_characters: 10,
        truncated: false
      };
    }
    if (command === 'forget_selected_file') {
      selectedFiles = selectedFiles.filter((file) => file.file_id !== args?.fileId);
      return selectedFiles;
    }
    throw { code: 'unexpected_command', message: command };
  })
}));

const sourceModules = import.meta.glob('../src/lib/components/files/*.svelte', {
  eager: true,
  query: '?raw',
  import: 'default'
}) as Record<string, string>;
const modelGatewayStoreSource = import.meta.glob('../src/lib/stores/modelGateway.ts', {
  eager: true,
  query: '?raw',
  import: 'default'
})['../src/lib/stores/modelGateway.ts'] as string;

beforeEach(() => {
  commands = [];
  selectedFiles = [];
  selectionError = null;
  resetFilesStore();
  setLocale('ru');
});

describe('Files capability frontend', () => {
  it('renders a truthful empty state without scanning or path controls', () => {
    installState([]);
    const html = render(FilesPanel).body;
    expect(html).toContain('Файлы не выбраны');
    expect(html).toContain('не сканирует диски и каталоги');
    expect(html).not.toMatch(/type="(?:text|file)"/);
  });

  it('selects through the fixed picker command and renders exact safe metadata', async () => {
    selectedFiles = [FILE];
    await initializeFilesCapability();
    await addFiles();
    const html = render(FilesPanel).body;
    expect(commands.map((entry) => entry.command)).toEqual(['files_capability_status', 'list_selected_files', 'select_files']);
    expect(commands.at(-1)?.args).toBeUndefined();
    expect(html).toContain('notes.md');
    expect(html).toContain('10 байт');
    expect(html).toContain('…\\Temp\\notes.md');
    expect(html).toContain('Читается');
  });

  it('shows the stable unsupported-type error without exposing backend detail', async () => {
    await initializeFilesCapability();
    selectionError = { code: 'LC_FILE_UNSUPPORTED_TYPE', message: 'backend detail' };
    await addFiles();
    expect(get(filesStore).lastError?.code).toBe('LC_FILE_UNSUPPORTED_TYPE');
    const html = render(FilesPanel).body;
    expect(html).toContain('Неподдерживаемый тип');
    expect(html).not.toContain('backend detail');
  });

  it('opens and renders a bounded preview with exact counters', async () => {
    selectedFiles = [FILE];
    await initializeFilesCapability();
    await openFilePreview(FILE_ID);
    expect(commands.at(-1)).toEqual({ command: 'preview_selected_file', args: { fileId: FILE_ID } });
    const html = render(FilesPanel).body;
    expect(html).toContain('# Preview');
    expect(html).toContain('10 / 10 байт');
    expect(html).toContain('role="dialog"');
  });

  it('requires explicit include and supports include/exclude toggling', () => {
    installState([FILE]);
    expect(get(filesStore).includedIds).toEqual([]);
    setFileIncluded(FILE_ID, true);
    expect(get(filesStore).includedIds).toEqual([FILE_ID]);
    setFileIncluded(FILE_ID, false);
    expect(get(filesStore).includedIds).toEqual([]);
  });

  it('shows exact aggregate source bytes and characters before send', () => {
    installState([FILE, SECOND_FILE]);
    setFileIncluded(FILE_ID, true);
    setFileIncluded(SECOND_FILE_ID, true);
    expect(get(includedFilesTotals)).toEqual({ bytes: 22, characters: 22, count: 2 });
    expect(render(FilesPanel).body).toContain('2 · 22 байт · 22 символов');
  });

  it('reports full versus bounded inclusion with visible exact counts', () => {
    installState([FILE]);
    reportFilesContextInclusion({
      source_bytes: 10,
      source_characters: 10,
      included_bytes: 5,
      included_characters: 5,
      truncated: true,
      files: [{
        file_id: FILE_ID,
        filename: 'notes.md',
        original_bytes: 10,
        original_characters: 10,
        included_bytes: 5,
        included_characters: 5,
        inclusion: 'bounded_excerpt'
      }]
    });
    const html = render(FilesPanel).body;
    expect(html).toContain('В последний запрос включён ограниченный фрагмент');
    expect(html).toContain('5 / 10 байт');
    expect(html).toContain('5 / 10 символов');
  });

  it('forget revokes inclusion, clears preview, and removes the file', async () => {
    selectedFiles = [FILE];
    await initializeFilesCapability();
    setFileIncluded(FILE_ID, true);
    await openFilePreview(FILE_ID);
    await forgetFile(FILE_ID);
    expect(commands.at(-1)).toEqual({ command: 'forget_selected_file', args: { fileId: FILE_ID } });
    expect(get(filesStore)).toMatchObject({ files: [], includedIds: [], preview: null });
  });

  it('derives Settings availability from backend capability status', () => {
    installState([]);
    const html = render(SettingsPanel).body;
    const available = html.slice(html.indexOf('Доступно'), html.indexOf('Недоступно'));
    const unavailable = html.slice(html.indexOf('Недоступно'));
    expect(available).toContain('Файлы');
    expect(unavailable).not.toContain('>Файлы<');
  });

  it('has labelled keyboard-operable controls and Escape preview handling', () => {
    const panel = sourceModules['../src/lib/components/files/FilesPanel.svelte'];
    const dialog = sourceModules['../src/lib/components/files/FilePreviewDialog.svelte'];
    expect(panel).toContain("aria-label={$t('files.add')}");
    expect(panel).toContain('type="checkbox"');
    expect(dialog).toContain("event.key === 'Escape'");
    expect(dialog).toContain('aria-modal="true"');
    expect(dialog).toContain("event.key !== 'Tab'");
  });

  it('rejects arbitrary path-like identities before invoking Tauri', async () => {
    await expect(previewSelectedFile('C:\\temp\\notes.md')).rejects.toMatchObject({ code: 'invalid_payload' });
    expect(commands).toHaveLength(0);
  });

  it('never adds backend file context to the visible user chat transcript', () => {
    expect(modelGatewayStoreSource).toContain('appendAcceptedChatTurn(requestId, cleanPrompt)');
    expect(modelGatewayStoreSource).not.toContain('appendAcceptedChatTurn(requestId, acceptance.file_context');
    expect(modelGatewayStoreSource).not.toContain('appendAcceptedChatTurn(requestId, fileIds');
  });
});

function installState(files: readonly SelectedFileSummary[]): void {
  filesStore.set({
    initialized: true,
    capability: CAPABILITY,
    files,
    includedIds: [],
    preview: null,
    selecting: false,
    previewingId: null,
    forgettingId: null,
    lastError: null,
    lastContextReport: null
  });
}
