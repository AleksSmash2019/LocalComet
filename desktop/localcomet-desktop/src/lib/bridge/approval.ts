import { invoke } from '@tauri-apps/api/core';

export interface ExecutionGrant {
  grant_id: string;
  tool: string;
  workspace: string;
  session: string;
}

export interface WorkspaceIdentity {
  status: string;
  canonical_path: string;
  workspace_digest: string;
}

export async function requestApproval(tool: string, input: unknown): Promise<string> {
  const token = await invoke<string>('request_approval', { tool, input });
  if (typeof token !== 'string' || !token.startsWith('lcap_') || token.length < 60) {
    throw { code: 'invalid_payload', message: 'Invalid approval token' };
  }
  return token;
}

export async function executeApproved(
  token: string,
  tool: string,
  input: unknown
): Promise<ExecutionGrant> {
  const grant = await invoke<ExecutionGrant>('execute_approved', { token, tool, input });
  if (
    typeof grant !== 'object' ||
    grant === null ||
    typeof grant.grant_id !== 'string' ||
    grant.tool !== tool
  ) {
    throw { code: 'invalid_payload', message: 'Invalid execution grant' };
  }
  return grant;
}

export async function setWorkspace(path: string): Promise<WorkspaceIdentity> {
  const identity = await invoke<WorkspaceIdentity>('set_workspace', { path });
  if (
    typeof identity !== 'object' ||
    identity === null ||
    identity.status !== 'ok' ||
    typeof identity.canonical_path !== 'string' ||
    !/^[0-9a-f]{64}$/.test(identity.workspace_digest)
  ) {
    throw { code: 'invalid_payload', message: 'Invalid workspace identity' };
  }
  return identity;
}
