import { derived, get, writable } from 'svelte/store';
import {
  forgetSelectedFile,
  getFilesCapabilityStatus,
  listSelectedFiles,
  normalizeFileError,
  previewSelectedFile,
  selectFiles
} from '$lib/bridge/files';
import type {
  FileCapabilityError,
  FilesContextReport,
  FilesCapabilityStatus,
  SelectedFilePreview,
  SelectedFileSummary
} from '$lib/types/files';

export interface FilesState {
  readonly initialized: boolean;
  readonly capability: FilesCapabilityStatus | null;
  readonly files: readonly SelectedFileSummary[];
  readonly includedIds: readonly string[];
  readonly preview: SelectedFilePreview | null;
  readonly selecting: boolean;
  readonly previewingId: string | null;
  readonly forgettingId: string | null;
  readonly lastError: FileCapabilityError | null;
  readonly lastContextReport: FilesContextReport | null;
}

const initialState: FilesState = {
  initialized: false,
  capability: null,
  files: [],
  includedIds: [],
  preview: null,
  selecting: false,
  previewingId: null,
  forgettingId: null,
  lastError: null,
  lastContextReport: null
};

let initializationPromise: Promise<void> | null = null;

export const filesStore = writable<FilesState>(initialState);
export const filesCapabilityAvailable = derived(
  filesStore,
  (state) => state.initialized && state.capability?.available === true
);
export const includedFileIds = derived(filesStore, (state) => state.includedIds);
export const includedFilesTotals = derived(filesStore, (state) => {
  const included = new Set(state.includedIds);
  return state.files.reduce(
    (totals, file) => included.has(file.file_id)
      ? {
          bytes: totals.bytes + file.byte_size,
          characters: totals.characters + file.character_count,
          count: totals.count + 1
        }
      : totals,
    { bytes: 0, characters: 0, count: 0 }
  );
});

export async function initializeFilesCapability(): Promise<void> {
  if (get(filesStore).initialized) return;
  if (initializationPromise) return initializationPromise;
  const pending = (async () => {
    try {
      const capability = await getFilesCapabilityStatus();
      const files = capability.available ? await listSelectedFiles() : [];
      filesStore.update((state) => ({
        ...state,
        initialized: true,
        capability,
        files,
        includedIds: retainReadableIds(state.includedIds, files),
        lastError: null
      }));
    } catch (error) {
      filesStore.update((state) => ({
        ...state,
        initialized: true,
        capability: null,
        files: [],
        includedIds: [],
        preview: null,
        lastError: normalizeFileError(error)
      }));
    }
  })();
  initializationPromise = pending;
  try {
    await pending;
  } finally {
    if (initializationPromise === pending) initializationPromise = null;
  }
}

export async function addFiles(): Promise<void> {
  if (!get(filesCapabilityAvailable) || get(filesStore).selecting) return;
  filesStore.update((state) => ({ ...state, selecting: true, lastError: null }));
  try {
    const response = await selectFiles();
    filesStore.update((state) => ({
      ...state,
      files: response.files,
      includedIds: retainReadableIds(state.includedIds, response.files),
      selecting: false,
      lastContextReport: null,
      lastError: null
    }));
  } catch (error) {
    filesStore.update((state) => ({ ...state, selecting: false, lastError: normalizeFileError(error) }));
  }
}

export async function openFilePreview(fileId: string): Promise<void> {
  const state = get(filesStore);
  if (state.previewingId || !state.files.some((file) => file.file_id === fileId && file.readable)) return;
  filesStore.update((current) => ({ ...current, previewingId: fileId, preview: null, lastError: null }));
  try {
    const preview = await previewSelectedFile(fileId);
    filesStore.update((current) => ({ ...current, previewingId: null, preview, lastError: null }));
  } catch (error) {
    filesStore.update((current) => ({ ...current, previewingId: null, preview: null, lastError: normalizeFileError(error) }));
    await refreshFilesAfterReadFailure();
  }
}

export function closeFilePreview(): void {
  filesStore.update((state) => ({ ...state, preview: null }));
}

export function setFileIncluded(fileId: string, included: boolean): void {
  filesStore.update((state) => {
    const file = state.files.find((candidate) => candidate.file_id === fileId);
    if (!file?.readable) return state;
    const ids = new Set(state.includedIds);
    if (included) ids.add(fileId);
    else ids.delete(fileId);
    const ordered = state.files.filter((candidate) => ids.has(candidate.file_id)).map((candidate) => candidate.file_id);
    const maximum = state.capability?.maximum_active_context_bytes ?? 0;
    const bytes = state.files.reduce((total, candidate) => ordered.includes(candidate.file_id) ? total + candidate.byte_size : total, 0);
    if (bytes > maximum) {
      return {
        ...state,
        lastError: { code: 'LC_FILE_CONTEXT_LIMIT', message: 'Selected files exceed the active context limit' }
      };
    }
    return { ...state, includedIds: ordered, lastError: null, lastContextReport: null };
  });
}

export async function forgetFile(fileId: string): Promise<void> {
  const state = get(filesStore);
  if (state.forgettingId || !state.files.some((file) => file.file_id === fileId)) return;
  filesStore.update((current) => ({ ...current, forgettingId: fileId, lastError: null }));
  try {
    const files = await forgetSelectedFile(fileId);
    filesStore.update((current) => ({
      ...current,
      files,
      includedIds: current.includedIds.filter((id) => id !== fileId),
      preview: current.preview?.file_id === fileId ? null : current.preview,
      forgettingId: null,
      lastContextReport: null,
      lastError: null
    }));
  } catch (error) {
    filesStore.update((current) => ({ ...current, forgettingId: null, lastError: normalizeFileError(error) }));
  }
}

export function reportFilesRequestError(error: FileCapabilityError): void {
  if (!error.code.startsWith('LC_FILE_')) return;
  filesStore.update((state) => ({ ...state, lastError: error }));
}

export function reportFilesContextInclusion(report: FilesContextReport | undefined): void {
  filesStore.update((state) => ({ ...state, lastContextReport: report ?? null }));
}

export function clearFilesError(): void {
  filesStore.update((state) => ({ ...state, lastError: null }));
}

export function resetFilesStore(): void {
  initializationPromise = null;
  filesStore.set(initialState);
}

async function refreshFilesAfterReadFailure(): Promise<void> {
  try {
    const files = await listSelectedFiles();
    filesStore.update((state) => ({
      ...state,
      files,
      includedIds: retainReadableIds(state.includedIds, files)
    }));
  } catch {
    // The original sanitized read error remains authoritative in the UI.
  }
}

function retainReadableIds(ids: readonly string[], files: readonly SelectedFileSummary[]): readonly string[] {
  const allowed = new Set(files.filter((file) => file.readable).map((file) => file.file_id));
  return files.filter((file) => allowed.has(file.file_id) && ids.includes(file.file_id)).map((file) => file.file_id);
}
