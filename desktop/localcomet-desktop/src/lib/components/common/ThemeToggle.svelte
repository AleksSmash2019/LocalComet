<script lang="ts">
  import Icon from './Icon.svelte';
  import { setThemeMode, themeMode } from '$lib/stores/shellStore';
  import { t } from '$lib/i18n';
  import type { ThemeMode } from '$lib/data/mockData';

  const themeItems: Array<[ThemeMode, string]> = [
    ['system', 'system'],
    ['light', 'sun'],
    ['dark', 'moon']
  ];
</script>

<div class="theme-toggle" aria-label={$t('theme.manage')}>
  {#each themeItems as [mode, icon]}
    {@const label = $t(mode === 'system' ? 'theme.system' : mode === 'light' ? 'theme.light' : 'theme.dark')}
    <button
      type="button"
      class:selected={$themeMode === mode}
      aria-label={label}
      aria-pressed={$themeMode === mode}
      title={label}
      onclick={() => setThemeMode(mode)}
    >
      <Icon name={icon} size={16} />
    </button>
  {/each}
</div>

<style>
  .theme-toggle {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--lc-space-1);
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-solid);
    padding: var(--lc-space-1);
  }

  button {
    min-width: 0;
    min-height: 32px;
    border: 1px solid transparent;
    border-radius: var(--lc-radius-sm);
    background: transparent;
    color: var(--lc-muted);
    cursor: pointer;
  }

  button.selected {
    border-color: var(--lc-line-strong);
    background: var(--lc-accent-dim);
    color: var(--lc-accent);
  }
</style>
