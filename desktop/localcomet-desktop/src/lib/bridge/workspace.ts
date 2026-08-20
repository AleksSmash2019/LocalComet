import { invoke } from '@tauri-apps/api/core';

export interface WorkspaceIdentity {
  readonly status: 'ok';
  readonly canonical_path: string;
  readonly workspace_digest: string;
}

export async function setWorkspace(path: string): Promise<WorkspaceIdentity> {
  if (!path.trim() || path.length > 520 || /[\0\r\n]/.test(path)) {
    throw { code: 'workspace_invalid_path', message: 'Invalid workspace path' };
  }
  const raw = await invoke<unknown>('set_workspace', { path });
  if (!isRecord(raw) || raw.status !== 'ok' || typeof raw.canonical_path !== 'string' || !/^[0-9a-f]{64}$/.test(String(raw.workspace_digest))) {
    throw { code: 'workspace_invalid_response', message: 'Invalid workspace identity' };
  }
  return {
    status: 'ok',
    canonical_path: raw.canonical_path,
    workspace_digest: String(raw.workspace_digest)
  };
}

export function normalizeWorkspaceError(error: unknown): string {
  if (isRecord(error) && typeof error.message === 'string') {
    return error.message.replace(/[\0\r\n]/g, ' ').trim().slice(0, 240) || 'Workspace selection failed';
  }
  return 'Workspace selection failed';
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
