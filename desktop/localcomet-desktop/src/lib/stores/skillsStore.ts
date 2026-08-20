import { writable } from 'svelte/store';
import { requestApproval } from '$lib/bridge/approval';
import { invoke } from '@tauri-apps/api/core';

export type SkillState = 'installed' | 'enabled' | 'disabled' | 'failed';

export interface Skill {
  id: string;
  name: string;
  version: string;
  state: SkillState;
  permissions: string[];
  description?: string;
  capabilities?: string[];
  builtin?: boolean;
}

function normalizeSkillState(value: unknown): SkillState {
  const normalized = String(value ?? '').toLowerCase();
  if (normalized === 'enabled' || normalized === 'disabled' || normalized === 'failed') return normalized;
  return 'installed';
}

function normalizeSkill(value: any): Skill {
  return {
    id: String(value?.id ?? ''),
    name: String(value?.name ?? ''),
    version: String(value?.version ?? ''),
    state: normalizeSkillState(value?.state),
    permissions: Array.isArray(value?.permissions) ? value.permissions.map(String) : [],
    description: typeof value?.description === 'string' ? value.description : '',
    capabilities: Array.isArray(value?.capabilities) ? value.capabilities.map(String) : [],
    builtin: value?.builtin === true
  };
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
        const rawSkills = Array.isArray(res.result) ? res.result : [];
        update(s => ({ ...s, skills: rawSkills.map(normalizeSkill), loading: false }));
      } else {

        update(s => ({ ...s, error: res.error?.message || 'Failed to load skills', loading: false }));
      }
    } catch (err: any) {
      update(s => ({ ...s, error: err.toString(), loading: false }));
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
      update(s => ({ ...s, error: err.toString(), loading: false }));
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
      update(s => ({ ...s, error: err.toString(), loading: false }));
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
      update(s => ({ ...s, error: err.toString(), loading: false }));
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
      update(s => ({ ...s, error: err.toString(), loading: false }));
      return false;
    }
  }

  return {
    subscribe,
    loadSkills,
    installSkill,
    enableSkill,
    disableSkill,
    uninstallSkill
  };
}

export const skillsStore = createSkillsStore();
