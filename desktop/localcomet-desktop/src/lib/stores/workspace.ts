import { get, writable } from 'svelte/store';
import { open } from '@tauri-apps/plugin-dialog';
import { normalizeWorkspaceError, setWorkspace } from '$lib/bridge/workspace';

export type WorkspaceStatus = 'unconfirmed' | 'confirming' | 'confirmed' | 'error';

export interface WorkspaceState {
  readonly status: WorkspaceStatus;
  readonly path: string | null;
  readonly digest: string | null;
  readonly error: string | null;
}

export const WORKSPACE_PREFERENCE_KEY = 'localcomet.workspace.v1';

function readPersistedWorkspace(): Pick<WorkspaceState, 'path' | 'digest'> {
  if (typeof localStorage === 'undefined') return { path: null, digest: null };
  try {
    const raw = localStorage.getItem(WORKSPACE_PREFERENCE_KEY);
    if (!raw) return { path: null, digest: null };
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      return { path: null, digest: null };
    }
    const record = parsed as Record<string, unknown>;
    return {
      path: typeof record.path === 'string' && record.path.trim() ? record.path : null,
      digest: typeof record.digest === 'string' && /^[0-9a-f]{64}$/.test(record.digest) ? record.digest : null
    };
  } catch {
    return { path: null, digest: null };
  }
}

function persistWorkspace(path: string, digest: string): void {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(WORKSPACE_PREFERENCE_KEY, JSON.stringify({ path, digest }));
}

const persisted = readPersistedWorkspace();
const initialState: WorkspaceState = {
  status: 'unconfirmed',
  path: persisted.path,
  digest: persisted.digest,
  error: null
};

export const workspaceStore = writable<WorkspaceState>(initialState);

export async function restoreWorkspace(): Promise<boolean> {
  const current = get(workspaceStore);
  if (!current.path || current.status === 'confirming') return false;
  workspaceStore.update((state) => ({ ...state, status: 'confirming', error: null }));
  try {
    const identity = await setWorkspace(current.path);
    workspaceStore.set({
      status: 'confirmed',
      path: identity.canonical_path,
      digest: identity.workspace_digest,
      error: null
    });
    persistWorkspace(identity.canonical_path, identity.workspace_digest);
    return true;
  } catch (error) {
    workspaceStore.update((state) => ({ ...state, status: 'error', error: normalizeWorkspaceError(error) }));
    return false;
  }
}

export async function chooseWorkspace(): Promise<boolean> {
  if (get(workspaceStore).status === 'confirming') return false;
  workspaceStore.update((state) => ({ ...state, status: 'confirming', error: null }));
  try {
    const selected = await open({ directory: true, multiple: false, title: 'Choose LocalComet workspace' });
    if (typeof selected !== 'string' || !selected.trim()) {
      workspaceStore.update((state) => ({ ...state, status: state.path ? 'unconfirmed' : 'unconfirmed' }));
      return false;
    }
    const identity = await setWorkspace(selected);
    workspaceStore.set({
      status: 'confirmed',
      path: identity.canonical_path,
      digest: identity.workspace_digest,
      error: null
    });
    persistWorkspace(identity.canonical_path, identity.workspace_digest);
    return true;
  } catch (error) {
    workspaceStore.update((state) => ({
      ...state,
      status: state.path ? 'unconfirmed' : 'error',
      error: normalizeWorkspaceError(error)
    }));
    return false;
  }
}

export function resetWorkspaceState(): void {
  if (typeof localStorage !== 'undefined') localStorage.removeItem(WORKSPACE_PREFERENCE_KEY);
  workspaceStore.set({ status: 'unconfirmed', path: null, digest: null, error: null });
}
