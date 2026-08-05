<script lang="ts">
  import { availableLanguages, locale, setLocale, t } from '$lib/i18n';
  import type { Language } from '$lib/i18n';

  let open = false;
  let menu: HTMLDivElement;
  let button: HTMLButtonElement;

  const languages = availableLanguages;

  function toggle() {
    open = !open;
  }

  function select(code: Language) {
    setLocale(code);
    open = false;
    button?.focus();
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      open = false;
      button?.focus();
    }
  }

  function handleGlobalClick(event: MouseEvent) {
    if (open && menu && !menu.contains(event.target as Node) && !button.contains(event.target as Node)) {
      open = false;
    }
  }
</script>

<svelte:window on:click={handleGlobalClick} />

<div class="language-switcher">
  <button
    type="button"
    class="lang-button"
    bind:this={button}
    aria-label={$t('lang.select')}
    aria-expanded={open}
    aria-haspopup="listbox"
    onclick={toggle}
    onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } }}
  >
    <span class="lang-label">{$locale.split('-')[0].toUpperCase()}</span>
    <span class="lang-arrow" aria-hidden="true">{open ? '▲' : '▾'}</span>
  </button>

  {#if open}
    <div
      class="lang-menu"
      bind:this={menu}
      role="listbox"
      tabindex="0"
      aria-label={$t('lang.select')}
      onkeydown={handleKeydown}
    >
      {#each languages as lang}
        <button
          type="button"
          role="option"
          class="lang-option"
          class:selected={$locale === lang.code}
          aria-selected={$locale === lang.code}
          onclick={() => select(lang.code)}
        >
          <span>{lang.endonym}</span>
          {#if $locale === lang.code}
            <span class="check" aria-hidden="true">✓</span>
          {/if}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .language-switcher {
    position: relative;
  }

  .lang-button {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    min-height: 32px;
    padding: 0 var(--lc-space-2);
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-solid);
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 700;
    cursor: pointer;
    font-family: var(--lc-mono);
  }

  .lang-button:hover {
    border-color: var(--lc-line);
    color: var(--lc-text);
  }

  .lang-button[aria-expanded="true"] {
    border-color: var(--lc-accent);
    color: var(--lc-accent);
  }

  .lang-arrow {
    font-size: 8px;
    line-height: 1;
  }

  .lang-menu {
    position: absolute;
    bottom: calc(100% + 4px);
    left: 0;
    min-width: 140px;
    background: var(--lc-panel-solid);
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    box-shadow: var(--lc-shadow);
    z-index: 60;
    overflow: hidden;
  }

  .lang-option {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--lc-space-2);
    width: 100%;
    min-height: 34px;
    padding: 0 var(--lc-space-3);
    border: none;
    background: transparent;
    color: var(--lc-text);
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    text-align: left;
  }

  .lang-option:hover {
    background: var(--lc-panel-soft);
  }

  .lang-option.selected {
    background: var(--lc-accent-dim);
    color: var(--lc-accent);
  }

  .check {
    color: var(--lc-accent);
    font-weight: 800;
  }
</style>
