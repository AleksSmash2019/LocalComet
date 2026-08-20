<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import { skillsStore } from '$lib/stores/skillsStore';
  import { t } from '$lib/i18n';
  import { open } from '@tauri-apps/plugin-dialog';

  let isInstalling = false;

  onMount(() => {
    skillsStore.loadSkills();
  });

  async function handleInstall() {
    const selected = await open({
      multiple: false,
      filters: [{ name: 'Skill package', extensions: ['zip', 'tar.gz', 'tgz'] }]
    });
    if (typeof selected !== 'string') return;
    isInstalling = true;
    try {
      await skillsStore.installSkill(selected);
    } finally {
      isInstalling = false;
    }
  }

  async function handleToggle(skillId: string, currentState: string) {
    if (currentState === 'enabled') {
      await skillsStore.disableSkill(skillId);
    } else {
      await skillsStore.enableSkill(skillId);
    }
  }

  async function handleUninstall(skillId: string) {
    await skillsStore.uninstallSkill(skillId);
  }
</script>

<section class="settings-section" aria-labelledby="skills-title">
  <div class="section-header">
    <h3 id="skills-title">{$t('skills.title_extended')}</h3>
    <button class="primary-button compact" disabled={$skillsStore.loading || isInstalling} on:click={handleInstall}>
      <Icon name="add" size={16} />
      <span>{$t('skills.install_skill')}</span>
    </button>
  </div>

  {#if $skillsStore.error}
    <div class="error-banner">
      <Icon name="error" size={16} />
      <span>{$skillsStore.error}</span>
    </div>
  {/if}

  {#if $skillsStore.skills.length === 0}
    <div class="empty-state">
      <p class="empty-desc">{$t('skills.empty') || 'No skills installed.'}</p>
    </div>
  {:else}
    <div class="skills-list">
      {#each $skillsStore.skills as skill (skill.id)}
        <div class="skill-card">
          <div class="skill-header">
            <div class="skill-title">
              <h4>{skill.name}</h4>
              <span class="skill-version">v{skill.version}</span>
              {#if skill.builtin}
                <span class="skill-builtin">{$t('skills.builtin')}</span>
              {/if}
            </div>
            <StatusBadge 
              label={skill.state} 
              tone={skill.state === 'enabled' ? 'ready' : (skill.state === 'disabled' ? 'disabled' : 'info')} 
            />
          </div>
          
          <div class="skill-meta">
            <code>{skill.id}</code>
          </div>

          {#if skill.description}
            <div class="skill-description">
              <strong>{$t('skills.description')}</strong>
              <span>{skill.description}</span>
            </div>
          {/if}

          <div class="skill-permissions">
            <strong>{$t('skills.permissions')}</strong>
            {#if skill.permissions && skill.permissions.length > 0}
              <span>{skill.permissions.join(', ')}</span>
            {:else}
              <span class="muted">{$t('skills.no_permissions')}</span>
            {/if}
          </div>

          <div class="skill-actions">
            <button 
              class="secondary-button compact" 
              disabled={$skillsStore.loading}
              on:click={() => handleToggle(skill.id, skill.state)}
            >
              {#if skill.state === 'enabled'}
                <Icon name="stop" size={14} />
                <span>{$t('skills.disable')}</span>
              {:else}
                <Icon name="play" size={14} />
                <span>{$t('skills.enable')}</span>
              {/if}
            </button>
            <button 
              class="danger-button compact outline" 
              disabled={$skillsStore.loading}
              on:click={() => handleUninstall(skill.id)}
            >
              <Icon name="delete" size={14} />
              <span>{$t('skills.uninstall')}</span>
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</section>

<style>
  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }
  
  .error-banner {
    background: var(--lc-red-alpha);
    color: var(--lc-red);
    padding: 12px;
    border-radius: 8px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
  }
  
  .skills-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  
  .skill-card {
    background: var(--lc-panel-soft);
    border: 1px solid var(--lc-line);
    border-radius: 8px;
    padding: 16px;
  }
  
  .skill-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 8px;
  }
  
  .skill-title {
    display: flex;
    align-items: baseline;
    gap: 8px;
  }
  
  .skill-title h4 {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
  }
  
  .skill-version {
    font-size: 12px;
    color: var(--lc-muted);
  }

  .skill-builtin {
    font-size: 11px;
    color: var(--lc-accent);
    border: 1px solid var(--lc-accent-alpha);
    border-radius: 999px;
    padding: 2px 6px;
  }
  
  .skill-meta {
    font-size: 12px;
    color: var(--lc-muted);
    margin-bottom: 8px;
  }

  .skill-description {
    display: flex;
    gap: 6px;
    font-size: 12px;
    color: var(--lc-text-secondary);
    margin-bottom: 8px;
  }
  
  .skill-permissions {
    font-size: 12px;
    color: var(--lc-text);
    margin-bottom: 16px;
  }
  
  .skill-permissions strong {
    color: var(--lc-muted);
    margin-right: 4px;
  }
  
  .skill-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }
</style>
