import { invoke } from '@tauri-apps/api/core';

export type ApprovalRiskLevel = 'read_only' | 'guarded' | 'dangerous';
export type ApprovalCommandFamily = 'artifact_download' | 'artifact_remove' | 'runtime_start' | 'runtime_stop' | 'model_binding_set' | 'tool_filesystem_read' | 'tool_filesystem_write' | 'tool_filesystem_delete';

export interface ApprovalEnvelope {
  token: string;
  approvalId: string;
  callId: string;
  tool: string;
  riskLevel: ApprovalRiskLevel;
  commandFamily: ApprovalCommandFamily;
  expiresAtUnixMs: number;
}

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

export interface ToolCallResult {
  tool: string;
  [key: string]: unknown;
}

const TOKEN_RE = /^lcap_[0-9a-f]{64}$/;
const APPROVAL_ID_RE = /^appr_[0-9a-f]{32}$/;
const CALL_ID_RE = /^call_[0-9a-f]{32}$/;
const RISK_LEVELS: readonly string[] = ['read_only', 'guarded', 'dangerous'];
const COMMAND_FAMILIES: readonly string[] = ['artifact_download', 'artifact_remove', 'runtime_start', 'runtime_stop', 'model_binding_set', 'tool_filesystem_read', 'tool_filesystem_write', 'tool_filesystem_delete'];

export function validateApprovalEnvelope(raw: unknown, expectedTool: string): ApprovalEnvelope {
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) {
    throw { code: 'invalid_payload', message: 'Approval envelope must be an object' };
  }
  const record = raw as Record<string, unknown>;
  const keys = Object.keys(record);
  if (keys.includes('approval_id') || keys.includes('call_id') || keys.includes('risk_level') || keys.includes('command_family') || keys.includes('expires_at_unix_ms')) {
    throw { code: 'invalid_payload', message: 'Approval envelope uses snake_case aliases' };
  }
  if (typeof record.token !== 'string' || !TOKEN_RE.test(record.token)) {
    throw { code: 'invalid_payload', message: 'Invalid approval token' };
  }
  if (typeof record.approvalId !== 'string' || !APPROVAL_ID_RE.test(record.approvalId)) {
    throw { code: 'invalid_payload', message: 'Invalid approval ID' };
  }
  if (typeof record.callId !== 'string' || !CALL_ID_RE.test(record.callId)) {
    throw { code: 'invalid_payload', message: 'Invalid call ID' };
  }
  if (typeof record.tool !== 'string' || record.tool !== expectedTool) {
    throw { code: 'invalid_payload', message: 'Unexpected tool in approval envelope' };
  }
  if (typeof record.riskLevel !== 'string' || !RISK_LEVELS.includes(record.riskLevel)) {
    throw { code: 'invalid_payload', message: 'Unknown risk level' };
  }
  if (typeof record.commandFamily !== 'string' || !COMMAND_FAMILIES.includes(record.commandFamily)) {
    throw { code: 'invalid_payload', message: 'Unknown command family' };
  }
  if (typeof record.expiresAtUnixMs !== 'number' || !Number.isFinite(record.expiresAtUnixMs) || record.expiresAtUnixMs < 0) {
    throw { code: 'invalid_payload', message: 'Invalid expiry timestamp' };
  }
  if (record.expiresAtUnixMs <= Date.now()) {
    throw { code: 'invalid_payload', message: 'Approval envelope expired' };
  }
  return {
    token: record.token,
    approvalId: record.approvalId,
    callId: record.callId,
    tool: record.tool,
    riskLevel: record.riskLevel as ApprovalRiskLevel,
    commandFamily: record.commandFamily as ApprovalCommandFamily,
    expiresAtUnixMs: record.expiresAtUnixMs
  };
}

export async function requestApproval(tool: string, input: unknown): Promise<ApprovalEnvelope> {
  const raw = await invoke<ApprovalEnvelope>('request_approval', { tool, input });
  return validateApprovalEnvelope(raw, tool);
}

export async function executeApproved(
  token: string,
  approvalId: string,
  callId: string,
  tool: string,
  input: unknown
): Promise<ExecutionGrant> {
  const grant = await invoke<ExecutionGrant>('execute_approved', {
    token,
    approvalId,
    callId,
    tool,
    input
  });
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

export async function runToolCall(
  tool: string,
  input: unknown,
  envelope?: Pick<ApprovalEnvelope, 'token' | 'approvalId' | 'callId'>
): Promise<ToolCallResult> {
  const result = await invoke<ToolCallResult>('run_tool_call', {
    tool,
    input,
    token: envelope?.token ?? null,
    approvalId: envelope?.approvalId ?? null,
    callId: envelope?.callId ?? null
  });
  if (typeof result !== 'object' || result === null || result.tool !== tool) {
    throw { code: 'invalid_payload', message: 'Invalid tool call result' };
  }
  return result;
}
