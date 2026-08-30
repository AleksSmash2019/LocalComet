import { writable } from 'svelte/store';
import { requestApproval, runToolCall } from '$lib/bridge/approval';
import { invoke } from '@tauri-apps/api/core';
import { errorDisplayText } from '$lib/errors/normalizedError';

export interface Skill {
  id: string;
  name: string;
  version: string;
  state: 'installed' | 'enabled' | 'disabled';
  permissions: string[];
  builtin?: boolean;
  description?: string;
  /** Contract version string, e.g. `localcomet.skill/2.0`. */
  contract?: string;
  /** Declarative workflow filename; empty for legacy v1 entrypoint skills. */
  workflow?: string;
  capabilities?: string[];
  trustTier?: string;
}

/**
 * A skill can only be executed by the host when it carries a declarative v2
 * workflow. Legacy v1 skills expose a Python entrypoint that the host never
 * invokes, so offering a run action for them would be a lie.
 */
export function isRunnableSkill(skill: Skill | null | undefined): boolean {
  if (!skill) return false;
  if (skill.state !== 'enabled') return false;
  if (skill.contract !== 'localcomet.skill/2.0') return false;
  return typeof skill.workflow === 'string' && skill.workflow.length > 0;
}

/**
 * The Python registry writes the skill state in upper case (`ENABLED`), while
 * this store and every UI comparison use lower case. Without normalisation the
 * enable/disable toggle compared `"ENABLED" === "enabled"`, always took the
 * "not enabled" branch and therefore always issued `enable` — a user could
 * never actually switch a skill off.
 */
function normalizeSkills(raw: unknown): Skill[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((entry: any) => {
    const state = typeof entry?.state === 'string' ? entry.state.toLowerCase() : 'installed';
    const known = state === 'enabled' || state === 'disabled' ? state : 'installed';
    return { ...entry, state: known } as Skill;
  });
}

export interface SkillsStore {
  skills: Skill[];
  loading: boolean;
  error: string | null;
}

function createSkillsStore() {
  const { subscribe, set, update } = writable<SkillsStore>({
    skills: [],
    loading: false,
    error: null
  });

  async function loadSkills() {
    update(s => ({ ...s, loading: true, error: null }));
    try {
      const res: any = await invoke('skills_list');
      if (res.success) {
        update(s => ({ ...s, skills: normalizeSkills(res.result), loading: false }));
      } else {
        update(s => ({ ...s, error: res.error?.message || 'Failed to load skills', loading: false }));
      }
    } catch (err: any) {
      update(s => ({ ...s, error: errorDisplayText(err), loading: false }));
    }
  }

  async function compileSkill(skillId: string, arguments_: Record<string, unknown> = {}) {
    update(s => ({ ...s, loading: true, error: null }));
    try {
      const input = { action: 'compile', skill_id: skillId, arguments: arguments_ };
      const envelope = await requestApproval('skills.invoke', input);
      const res: any = await invoke('skills_compile', {
        skillId,
        arguments: arguments_,
        token: envelope.token,
        approvalId: envelope.approvalId,
        callId: envelope.callId,
      });
      if (res.success) {
        update(s => ({ ...s, loading: false }));
        return res.result;
      }
      update(s => ({ ...s, error: res.error?.message || 'Failed to compile skill workflow', loading: false }));
      return null;
    } catch (err: any) {
      update(s => ({ ...s, error: errorDisplayText(err), loading: false }));
      return null;
    }
  }

  function workflowCorrelation(skillId: string, stepId: string, index: number): { requestId: string; actionId: string } {
    if (!globalThis.crypto?.getRandomValues) {
      throw { code: 'runtime_unavailable', message: 'Secure skill workflow correlation generation is unavailable' };
    }
    const bytes = new Uint8Array(12);
    globalThis.crypto.getRandomValues(bytes);
    const requestId = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
    return {
      requestId,
      actionId: `skill_${skillId}_${stepId}_${index}`.slice(0, 128),
    };
  }

  function verifiedComputerUseResult(result: any): boolean {
    return result?.schema_version === 'computer_use.result.v1'
      && result?.status === 'completed'
      && result?.terminal === true
      && result?.succeeded === true
      && (result?.verification === 'verified' || result?.verification === 'not_applicable');
  }

  function workflowActionName(action: unknown): string {
    if (typeof action !== 'string' || !action.startsWith('computer_use.')) {
      throw { code: 'invalid_payload', message: 'Skill workflow contains an unsupported tool family' };
    }
    const name = action.slice('computer_use.'.length);
    if (!['open_app', 'wait_for_window', 'observe', 'type_element', 'close_owned'].includes(name)) {
      throw { code: 'unsupported_action', message: `Skill workflow action is not host-supported: ${name}` };
    }
    return name;
  }

  function workflowPreconditionSatisfied(condition: any, verifiedStepIds: Set<string>, ownershipRequestId: string | null): boolean {
    if (!condition) return true;
    if (condition.kind === 'owned_session_ready') return true;
    if (condition.kind === 'owned_process_started') return Boolean(ownershipRequestId);
    if (condition.kind === 'launch_pending') return Boolean(ownershipRequestId);
    if (condition.kind === 'window_ready') return typeof condition.step === 'string' && verifiedStepIds.has(condition.step);
    if (condition.kind === 'wait_complete' || condition.kind === 'fresh_uia_observation') {
      return typeof condition.step === 'string' && verifiedStepIds.has(condition.step);
    }
    return false;
  }

  function workflowPostconditionSatisfied(condition: any, result: any, action: string): boolean {
    if (!condition) return true;
    if (!verifiedComputerUseResult(result)) return false;
    if (condition.kind === 'owned_process_window') return action === 'open_app' && result?.execution?.mode === 'cu_broker_spawn';
    if (condition.kind === 'wait_complete') return action === 'wait_for_window' && result?.verification === 'not_applicable';
    if (condition.kind === 'fresh_uia_observation') return action === 'observe' && result?.verification === 'verified';
    if (condition.kind === 'fresh_uia_text_contains') return action === 'type_element' && result?.verification === 'verified';
    if (condition.kind === 'owned_process_terminated') return action === 'close_owned' && result?.verification === 'verified';
    return false;
  }

  function workflowResultVerified(action: string, result: any, condition: any): boolean {
    if (!verifiedComputerUseResult(result)) return false;
    if (action === 'observe' || action === 'type_element' || action === 'close_owned') {
      return result?.verification === 'verified' && workflowPostconditionSatisfied(condition, result, action);
    }
    return workflowPostconditionSatisfied(condition, result, action);
  }

  async function runSkillWorkflow(skillId: string, arguments_: Record<string, unknown> = {}) {
    update(s => ({ ...s, loading: true, error: null }));
    const results: any[] = [];
    let ownershipRequestId: string | null = null;
    const verifiedStepIds = new Set<string>();
    let plan: any;
    let currentIndex = -1;
    let cleanupAttempted = false;
    const performDeclaredCleanup = async (afterIndex: number) => {
      if (cleanupAttempted || !ownershipRequestId || !plan || !Array.isArray(plan.steps)) return;
      const cleanupStep = plan.steps.slice(afterIndex + 1).find((candidate: any) => candidate?.action === 'computer_use.close_owned');
      if (!cleanupStep) return;
      cleanupAttempted = true;
      const cleanupAction = 'close_owned';
      const cleanupInput: Record<string, unknown> = {
        action: cleanupAction,
        ...(cleanupStep.arguments || {}),
        ownership_request_id: ownershipRequestId,
      };
      const cleanupCorrelation = workflowCorrelation(skillId, String(cleanupStep.id || cleanupAction), afterIndex + 1);
      const cleanupApproval = cleanupStep?.requires_approval === false
        ? undefined
        : await requestApproval('computer_use', cleanupInput);
      const cleanupResult = await runToolCall('computer_use', cleanupInput, cleanupApproval, undefined, cleanupCorrelation.requestId, cleanupCorrelation.actionId);
      const cleanupStepId = String(cleanupStep.id || cleanupAction);
      results.push({ stepId: cleanupStepId, action: cleanupAction, requestId: cleanupCorrelation.requestId, actionId: cleanupCorrelation.actionId, result: cleanupResult, cleanup: true });
      if (workflowResultVerified(cleanupAction, cleanupResult, cleanupStep.postcondition)) verifiedStepIds.add(cleanupStepId);
    };
    try {
      plan = await compileSkill(skillId, arguments_);
      if (!plan || !Array.isArray(plan.steps)) {
        throw { code: 'invalid_payload', message: 'Skill compiler returned an invalid plan' };
      }
      for (let index = 0; index < plan.steps.length; index += 1) {
        currentIndex = index;
        const step = plan.steps[index];
        const action = workflowActionName(step?.action);
        const stepId = String(step?.id || action);
        if (!workflowPreconditionSatisfied(step?.precondition, verifiedStepIds, ownershipRequestId)) {
          throw { code: 'workflow_precondition_failed', message: `Skill precondition failed for ${stepId}` };
        }
        const input: Record<string, unknown> = { action, ...(step?.arguments || {}) };
        if (action === 'close_owned') {
          if (!ownershipRequestId) {
            throw { code: 'ownership_missing', message: 'Skill cleanup has no broker-owned launch to close' };
          }
          input.ownership_request_id = ownershipRequestId;
        }
        const correlation = workflowCorrelation(skillId, String(step.id || action), index);
        const approval = step?.requires_approval === false
          ? undefined
          : await requestApproval('computer_use', input);
        const result = await runToolCall('computer_use', input, approval, undefined, correlation.requestId, correlation.actionId);
        results.push({ stepId, action, requestId: correlation.requestId, actionId: correlation.actionId, result });
        const executionMode = (result as { execution?: { mode?: unknown } } | null)?.execution?.mode;
        if (action === 'open_app' && executionMode === 'cu_broker_spawn') {
          // The Rust broker registers ownership even for launch_pending. This
          // lets the declared cleanup step close a process whose readiness
          // postcondition did not arrive, without accepting arbitrary PIDs.
          ownershipRequestId = correlation.requestId;
        }
        const stepVerified = workflowResultVerified(action, result, step?.postcondition);
        const launchPending = action === 'open_app' && executionMode === 'cu_broker_spawn' && result?.status === 'launch_pending';
        if (stepVerified) verifiedStepIds.add(stepId);
        if (action === 'observe' && stepVerified && ownershipRequestId) {
          const openStep = plan.steps.find((candidate: any) => candidate?.action === 'computer_use.open_app');
          if (openStep?.id) verifiedStepIds.add(String(openStep.id));
        }
        if (!stepVerified && !launchPending) {
          // Cleanup is part of the declared workflow, but it must itself pass
          // through a fresh approval and the broker ownership check.
          await performDeclaredCleanup(index);
          break;
        }
      }
      const expectedStepIds = new Set<string>(plan.steps.map((step: any) => String(step?.id || step?.action)));
      const success = expectedStepIds.size === verifiedStepIds.size
        && [...expectedStepIds].every((stepId) => verifiedStepIds.has(stepId));
      update(s => ({ ...s, loading: false }));
      return { skillId, plan, results, success };
    } catch (err: any) {
      try {
        await performDeclaredCleanup(currentIndex);
      } catch (cleanupError: any) {
        err = {
          code: 'workflow_cleanup_failed',
          message: 'Skill workflow failed and declared cleanup could not be completed',
          cause: err,
          cleanup_error: cleanupError,
        };
      }
      update(s => ({ ...s, error: errorDisplayText(err), loading: false }));
      return { skillId, plan: plan || null, results, success: false, error: err };
    }
  }

  async function installSkill(archivePath: string) {
    update(s => ({ ...s, loading: true, error: null }));
    try {
      const input = { action: 'install', archive: archivePath };
      const envelope = await requestApproval('skills.invoke', input);
      const res: any = await invoke('skills_install', {
        archive: archivePath,
        token: envelope.token,
        approvalId: envelope.approvalId,
        callId: envelope.callId,
      });
      if (res.success) {
        await loadSkills();
        return true;
      } else {
        update(s => ({ ...s, error: res.error?.message || 'Failed to install skill', loading: false }));
        return false;
      }
    } catch (err: any) {
      update(s => ({ ...s, error: errorDisplayText(err), loading: false }));
      return false;
    }
  }

  async function enableSkill(skillId: string) {
    update(s => ({ ...s, loading: true, error: null }));
    try {
      const input = { action: 'enable', skill_id: skillId };
      const envelope = await requestApproval('skills.invoke', input);
      const res: any = await invoke('skills_enable', { skillId, token: envelope.token, approvalId: envelope.approvalId, callId: envelope.callId });
      if (res.success) {
        await loadSkills();
        return true;
      } else {
        update(s => ({ ...s, error: res.error?.message || 'Failed to enable skill', loading: false }));
        return false;
      }
    } catch (err: any) {
      update(s => ({ ...s, error: errorDisplayText(err), loading: false }));
      return false;
    }
  }

  async function disableSkill(skillId: string) {
    update(s => ({ ...s, loading: true, error: null }));
    try {
      const input = { action: 'disable', skill_id: skillId };
      const envelope = await requestApproval('skills.invoke', input);
      const res: any = await invoke('skills_disable', { skillId, token: envelope.token, approvalId: envelope.approvalId, callId: envelope.callId });
      if (res.success) {
        await loadSkills();
        return true;
      } else {
        update(s => ({ ...s, error: res.error?.message || 'Failed to disable skill', loading: false }));
        return false;
      }
    } catch (err: any) {
      update(s => ({ ...s, error: errorDisplayText(err), loading: false }));
      return false;
    }
  }

  async function uninstallSkill(skillId: string) {
    update(s => ({ ...s, loading: true, error: null }));
    try {
      const input = { action: 'uninstall', skill_id: skillId };
      const envelope = await requestApproval('skills.invoke', input);
      const res: any = await invoke('skills_uninstall', { skillId, token: envelope.token, approvalId: envelope.approvalId, callId: envelope.callId });
      if (res.success) {
        await loadSkills();
        return true;
      } else {
        update(s => ({ ...s, error: res.error?.message || 'Failed to uninstall skill', loading: false }));
        return false;
      }
    } catch (err: any) {
      update(s => ({ ...s, error: errorDisplayText(err), loading: false }));
      return false;
    }
  }

  return {
    subscribe,
    loadSkills,
    compileSkill,
    runSkillWorkflow,
    installSkill,
    enableSkill,
    disableSkill,
    uninstallSkill
  };
}

export const skillsStore = createSkillsStore();
