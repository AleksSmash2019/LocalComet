<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import { skillsStore, isRunnableSkill } from '$lib/stores/skillsStore';
  import { errorDisplayText } from '$lib/errors/normalizedError';
  import { t } from '$lib/i18n';
  import { open } from '@tauri-apps/plugin-dialog';

  let isInstalling = false;
  let runningSkillId: string | null = null;
  let runArguments: Record<string, string> = {};
  let runOutcomes: Record<string, { success: boolean; detail: string }> = {};

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

  function handleArgumentInput(skillId: string, value: string) {
    runArguments = { ...runArguments, [skillId]: value };
  }

  async function handleRun(skillId: string) {
    const raw = (runArguments[skillId] ?? '').trim();
    let parsed: Record<string, unknown> = {};
    if (raw.length > 0) {
      try {
        const value = JSON.parse(raw);
        if (!value || typeof value !== 'object' || Array.isArray(value)) {
          runOutcomes = { ...runOutcomes, [skillId]: { success: false, detail: $t('skills.run_arguments_invalid') } };
          return;
        }
        parsed = value as Record<string, unknown>;
      } catch {
        // Reporting the parse failure here keeps the declared workflow from
        // being compiled and approved with arguments the user cannot see were
        // rejected. No backend call happens, so nothing is misrepresented.
        runOutcomes = { ...runOutcomes, [skillId]: { success: false, detail: $t('skills.run_arguments_invalid') } };
        return;
      }
    }
    runningSkillId = skillId;
    try {
      const outcome = await skillsStore.runSkillWorkflow(skillId, parsed);
      runOutcomes = {
        ...runOutcomes,
        [skillId]: {
          success: Boolean(outcome?.success),
          detail: outcome?.success
            ? $t('skills.run_success')
            : (outcome?.error ? errorDisplayText(outcome.error) : $t('skills.run_failed')),
        },
      };
    } finally {
      runningSkillId = null;
    }
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

          {#if isRunnableSkill(skill)}
            <div class="skill-run">
              <label class="run-label" for="skill-args-{skill.id}">{$t('skills.run_arguments')}</label>
              <input
                id="skill-args-{skill.id}"
                class="run-input"
                type="text"
                autocomplete="off"
                spellcheck="false"
                placeholder={$t('skills.run_arguments_placeholder')}
                value={runArguments[skill.id] ?? ''}
                disabled={$skillsStore.loading || runningSkillId === skill.id}
                on:input={(event) => handleArgumentInput(skill.id, event.currentTarget.value)}
              />
            </div>
          {/if}

          {#if runOutcomes[skill.id]}
            <div class="run-outcome" class:failed={!runOutcomes[skill.id].success}>
              <Icon name={runOutcomes[skill.id].success ? 'check' : 'error'} size={14} />
              <span>{runOutcomes[skill.id].detail}</span>
            </div>
          {/if}

          <div class="skill-actions">
            {#if isRunnableSkill(skill)}
              <button
                class="primary-button compact"
                disabled={$skillsStore.loading || runningSkillId !== null}
                on:click={() => handleRun(skill.id)}
              >
                <Icon name="run" size={14} />
                <span>{runningSkillId === skill.id ? $t('skills.running') : $t('skills.run')}</span>
              </button>
            {/if}
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
  
  .skill-run {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 12px;
  }

  .run-label {
    font-size: 12px;
    color: var(--lc-muted);
  }

  .run-input {
    width: 100%;
    box-sizing: border-box;
    background: var(--lc-bg-soft, var(--lc-panel));
    color: var(--lc-text);
    border: 1px solid var(--lc-line);
    border-radius: 6px;
    padding: 8px 10px;
    font-size: 13px;
    font-family: var(--lc-mono, monospace);
  }

  .run-input:disabled {
    opacity: 0.6;
  }

  .run-outcome {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--lc-green, var(--lc-accent));
    margin-bottom: 12px;
  }

  .run-outcome.failed {
    color: var(--lc-red);
  }

  .skill-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }
</style>
