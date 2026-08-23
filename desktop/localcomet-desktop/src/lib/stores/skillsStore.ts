import { writable } from 'svelte/store';
import { requestApproval } from '$lib/bridge/approval';
import { invoke } from '@tauri-apps/api/core';

export interface Skill {
  id: string;
  name: string;
  version: string;
  state: 'installed' | 'enabled' | 'disabled';
  permissions: string[];
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
        update(s => ({ ...s, skills: res.result || [], loading: false }));
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
