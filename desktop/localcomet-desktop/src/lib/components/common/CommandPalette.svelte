<script lang="ts">
  import { onDestroy, tick } from 'svelte';
  import { t } from '$lib/i18n';
  import {
    closeCommandPalette,
    commandPaletteOpen,
    inspectorVisible,
    openSettings,
    setActiveWorkspace,
    setDiagnosticsPanelOpen
  } from '$lib/stores/shellStore';

  type PaletteCommand = {
    id: string;
    label: string;
    run: () => void;
  };

  let dialogElement: HTMLDivElement;
  let inputElement: HTMLInputElement;
  let previousFocus: HTMLElement | null = null;
  let query = '';
  let activeIndex = 0;
  let wasOpen = false;

  $: commands = [
    {
      id: 'chat',
      label: $t('commandPalette.command.chat'),
      run: () => setActiveWorkspace('chat')
    },
    {
      id: 'settings',
      label: $t('commandPalette.command.settings'),
      run: openSettings
    },
    {
      id: 'setup',
      label: $t('commandPalette.command.setup'),
      run: () => setActiveWorkspace('setup')
    },
    {
      id: 'models',
      label: $t('commandPalette.command.models'),
      run: () => openSettings('models')
    },
    {
      id: 'observability',
      label: $t('commandPalette.command.observability'),
      run: () => openSettings('observability')
    },
    {
      id: 'diagnostics',
      label: $inspectorVisible
        ? $t('commandPalette.command.hideDiagnostics')
        : $t('commandPalette.command.showDiagnostics'),
      run: () => {
        setActiveWorkspace('chat');
        setDiagnosticsPanelOpen(!$inspectorVisible);
      }
    }
  ] satisfies PaletteCommand[];
  $: normalizedQuery = query.trim().toLocaleLowerCase();
  $: filteredCommands = normalizedQuery
    ? commands.filter((command) => command.label.toLocaleLowerCase().includes(normalizedQuery))
    : commands;
  $: if (activeIndex >= filteredCommands.length) activeIndex = Math.max(0, filteredCommands.length - 1);
  $: activeDescendant = filteredCommands[activeIndex]
    ? `command-palette-option-${filteredCommands[activeIndex].id}`
    : undefined;
  $: if ($commandPaletteOpen && !wasOpen) {
    wasOpen = true;
    previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    query = '';
    activeIndex = 0;
    void tick().then(() => inputElement?.focus());
  } else if (!$commandPaletteOpen && wasOpen) {
    wasOpen = false;
    const focusTarget = previousFocus;
    previousFocus = null;
    queueMicrotask(() => focusTarget?.focus());
  }

  onDestroy(() => {
    if (wasOpen) previousFocus?.focus();
  });

  function execute(command: PaletteCommand | undefined): void {
    if (!command) return;
    previousFocus = null;
    closeCommandPalette();
    command.run();
  }

  function handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      closeCommandPalette();
      return;
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (filteredCommands.length === 0) return;
      const offset = event.key === 'ArrowDown' ? 1 : -1;
      activeIndex = (activeIndex + offset + filteredCommands.length) % filteredCommands.length;
      return;
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      execute(filteredCommands[activeIndex]);
      return;
    }
    if (event.key !== 'Tab') return;

    const focusable = Array.from(
      dialogElement.querySelectorAll<HTMLElement>(
        'input:not([disabled]), button:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )
    );
    if (focusable.length === 0) {
      event.preventDefault();
      dialogElement.focus();
      return;
    }
    const currentIndex = focusable.indexOf(document.activeElement as HTMLElement);
    const nextIndex = event.shiftKey
      ? (currentIndex <= 0 ? focusable.length - 1 : currentIndex - 1)
      : (currentIndex >= focusable.length - 1 ? 0 : currentIndex + 1);
    event.preventDefault();
    focusable[nextIndex]?.focus();
  }

  function handleBackdropClick(event: MouseEvent): void {
    if (event.target === event.currentTarget) closeCommandPalette();
  }
</script>

{#if $commandPaletteOpen}
  <div
    class="palette-backdrop"
    role="presentation"
    onclick={handleBackdropClick}
    onkeydown={handleKeydown}
  >
    <div
      bind:this={dialogElement}
      class="command-palette"
      role="dialog"
      aria-modal="true"
      aria-label={$t('commandPalette.label')}
      tabindex="-1"
    >
      <label for="command-palette-search">{$t('commandPalette.search')}</label>
      <input
        bind:this={inputElement}
        id="command-palette-search"
        type="search"
        bind:value={query}
        placeholder={$t('commandPalette.placeholder')}
        autocomplete="off"
        aria-controls="command-palette-list"
        aria-activedescendant={activeDescendant}
        oninput={() => (activeIndex = 0)}
      />

      <div
        id="command-palette-list"
        class="command-list"
        role="listbox"
        aria-label={$t('commandPalette.commands')}
        tabindex="-1"
      >
        {#each filteredCommands as command, index (command.id)}
          <button
            id={`command-palette-option-${command.id}`}
            type="button"
            role="option"
            class:active={index === activeIndex}
            aria-selected={index === activeIndex}
            onmouseenter={() => (activeIndex = index)}
            onclick={() => execute(command)}
          >
            {command.label}
          </button>
        {:else}
          <p class="empty">{$t('commandPalette.empty')}</p>
        {/each}
      </div>
    </div>
  </div>
{/if}

<style>
  .palette-backdrop {
    position: fixed;
    inset: 0;
    z-index: 100;
    display: grid;
    place-items: start center;
    padding: min(18vh, 160px) var(--lc-space-4) var(--lc-space-4);
    background: color-mix(in srgb, #000 68%, transparent);
  }

  .command-palette {
    width: min(620px, 100%);
    overflow: hidden;
    border: var(--border-thin);
    border-radius: var(--lc-radius-lg);
    background: var(--lc-panel-solid);
    box-shadow: var(--lc-shadow);
  }

  label {
    display: block;
    padding: var(--lc-space-4) var(--lc-space-4) var(--lc-space-2);
    color: var(--lc-muted);
    font-size: 11px;
    font-weight: 760;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  input {
    width: calc(100% - (2 * var(--lc-space-4)));
    min-height: 46px;
    margin: 0 var(--lc-space-4) var(--lc-space-3);
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    background: var(--lc-panel);
    color: var(--lc-text);
    font: inherit;
    padding: 0 var(--lc-space-3);
  }

  input:focus-visible,
  button:focus-visible {
    outline: 2px solid var(--lc-accent);
    outline-offset: 2px;
  }

  .command-list {
    display: grid;
    gap: var(--lc-space-1);
    max-height: min(360px, 50vh);
    overflow-y: auto;
    border-top: var(--border-thin);
    padding: var(--lc-space-2);
  }

  button {
    min-height: 44px;
    border: 1px solid transparent;
    border-radius: var(--lc-radius-md);
    background: transparent;
    color: var(--lc-text);
    padding: 0 var(--lc-space-3);
    text-align: left;
    cursor: pointer;
  }

  button.active {
    border-color: var(--lc-line-strong);
    background: var(--lc-accent-dim);
    color: var(--lc-accent);
  }

  .empty {
    margin: 0;
    padding: var(--lc-space-4);
    color: var(--lc-muted);
    text-align: center;
  }

  @media (max-width: 560px) {
    .palette-backdrop {
      padding: var(--lc-space-4) var(--lc-space-2);
    }
  }
</style>
