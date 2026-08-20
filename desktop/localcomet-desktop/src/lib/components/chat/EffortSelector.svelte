<script lang="ts">
  import { onMount } from 'svelte';
  import { t } from '$lib/i18n';
  import { effortLevel, setEffortLevel } from '$lib/stores/shellStore';
  import { inferenceRequestStore, managedRuntimeStore, modelGatewayStore } from '$lib/stores/modelGateway';
  import { EFFORT_LEVELS, isEffortLevel, modelMaySupportThinking, type EffortLevel } from '$lib/types/effort';

  const effortLabels: Record<EffortLevel, string> = {
    off: 'effort.off',
    low: 'effort.low',
    medium: 'effort.medium',
    high: 'effort.high'
  };

  const effortDescriptions: Record<EffortLevel, string> = {
    off: 'effort.off_description',
    low: 'effort.low_description',
    medium: 'effort.medium_description',
    high: 'effort.high_description'
  };

  let menuOpen = false;
  let highlightedIndex = 0;
  let root: HTMLDivElement | undefined;

  $: currentModelId = $modelGatewayStore.binding?.model_id ?? $modelGatewayStore.selectedModelId;
  $: selectedManagedModel = $managedRuntimeStore.catalog.find((model) => model.model_id === currentModelId);
  $: modelCapabilityText = [
    currentModelId,
    selectedManagedModel?.display_name,
    selectedManagedModel?.asset_filename
  ].filter(Boolean).join(' ');
  $: supportsThinking = modelMaySupportThinking(modelCapabilityText);
  $: isGenerating = ['submitted', 'accepted', 'streaming', 'cancelling'].includes($inferenceRequestStore.lifecycle);
  $: disabled = isGenerating || !supportsThinking;
  $: selectedIndex = Math.max(0, EFFORT_LEVELS.indexOf($effortLevel));

  onMount(() => {
    const closeWhenOutside = (event: PointerEvent): void => {
      if (menuOpen && root && event.target instanceof Node && !root.contains(event.target)) {
        menuOpen = false;
      }
    };
    document.addEventListener('pointerdown', closeWhenOutside);
    return () => document.removeEventListener('pointerdown', closeWhenOutside);
  });

  function openMenu(): void {
    if (disabled) return;
    highlightedIndex = selectedIndex;
    menuOpen = true;
  }

  function toggleMenu(): void {
    if (menuOpen) menuOpen = false;
    else openMenu();
  }

  function choose(level: EffortLevel): void {
    if (disabled) return;
    setEffortLevel(level);
    menuOpen = false;
  }

  function handleTriggerKeydown(event: KeyboardEvent): void {
    if (disabled) return;
    if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      openMenu();
    } else if (event.key === 'Escape') {
      menuOpen = false;
    }
  }

  function handleMenuKeydown(event: KeyboardEvent): void {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      highlightedIndex = (highlightedIndex + 1) % EFFORT_LEVELS.length;
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      highlightedIndex = (highlightedIndex - 1 + EFFORT_LEVELS.length) % EFFORT_LEVELS.length;
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      choose(EFFORT_LEVELS[highlightedIndex]);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      menuOpen = false;
    }
  }
</script>

<svelte:window onkeydown={(event) => { if (event.key === 'Escape') menuOpen = false; }} />

<div
  class="effort-control"
  class:unsupported={!supportsThinking}
  class:menu-open={menuOpen}
  bind:this={root}
  title={supportsThinking ? $t(effortDescriptions[$effortLevel]) : $t('effort.unsupported')}
>
  <span class="sr-only" id="effort-label">{$t('effort.label')}</span>
  <button
    type="button"
    class="effort-trigger"
    aria-label={$t('effort.label')}
    aria-controls="effort-menu"
    aria-expanded={menuOpen}
    aria-haspopup="listbox"
    disabled={disabled}
    onclick={toggleMenu}
    onkeydown={handleTriggerKeydown}
  >
    <span class="effort-title">{$t('effort.label')}</span>
    <span class="effort-trigger-label">{$t(effortLabels[$effortLevel])}</span>
    <span class="effort-chevron" aria-hidden="true">▾</span>
  </button>

  {#if menuOpen}
    <div
      id="effort-menu"
      class="effort-menu"
      role="listbox"
      aria-labelledby="effort-label"
      tabindex="-1"
      onkeydown={handleMenuKeydown}
    >
      {#each EFFORT_LEVELS as level, index}
        <button
          type="button"
          role="option"
          class="effort-option"
          class:active={level === $effortLevel}
          class:highlighted={index === highlightedIndex}
          aria-selected={level === $effortLevel}
          onclick={(event) => { event.stopPropagation(); choose(level); }}
          onmouseenter={() => highlightedIndex = index}
        >
          <span>{$t(effortLabels[level])}</span>
          {#if level === $effortLevel}<span class="effort-check" aria-hidden="true">✓</span>{/if}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .effort-control {
    position: relative;
    z-index: 30;
    display: inline-flex;
    align-items: center;
    flex: 0 0 auto;
    min-height: 30px;
    white-space: nowrap;
  }

  .effort-control.unsupported {
    opacity: 0.56;
  }

  .effort-control.menu-open {
    z-index: 120;
  }

  .effort-trigger {
    display: inline-flex;
    align-items: center;
    justify-content: space-between;
    gap: 5px;
    width: 142px;
    height: 30px;
    min-height: 30px;
    padding: 0 9px;
    border: 1px solid transparent;
    border-radius: 8px;
    background: transparent;
    color: var(--lc-muted);
    font: inherit;
    font-size: 11px;
    font-weight: 650;
    cursor: pointer;
    transition: border-color 0.16s ease, background 0.16s ease, color 0.16s ease;
  }

  .effort-trigger:hover:not(:disabled),
  .effort-trigger:focus-visible,
  .effort-control.menu-open .effort-trigger {
    border-color: color-mix(in srgb, var(--lc-line) 78%, transparent);
    background: color-mix(in srgb, var(--lc-panel-soft) 70%, transparent);
    color: var(--lc-text);
  }

  .effort-trigger:focus-visible {
    outline: 2px solid color-mix(in srgb, var(--lc-accent) 65%, transparent);
    outline-offset: -2px;
  }

  .effort-trigger:disabled {
    cursor: not-allowed;
    color: var(--lc-muted);
  }

  .effort-trigger-label {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .effort-title {
    color: var(--lc-faint);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.01em;
  }

  .effort-chevron {
    flex: 0 0 auto;
    color: var(--lc-faint);
    font-size: 12px;
    line-height: 1;
  }

  .effort-menu {
    position: absolute;
    left: 0;
    bottom: calc(100% + 7px);
    z-index: 200;
    display: grid;
    width: 212px;
    gap: 2px;
    padding: 5px;
    border: 1px solid var(--lc-line);
    border-radius: 10px;
    background: var(--lc-panel-solid, var(--lc-panel));
    box-shadow: 0 14px 32px color-mix(in srgb, #000 42%, transparent);
  }

  .effort-option {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    min-height: 30px;
    padding: 6px 8px;
    border: 0;
    border-radius: 6px;
    background: transparent;
    color: var(--lc-text);
    font: inherit;
    font-size: 12px;
    text-align: left;
    cursor: pointer;
  }

  .effort-option:hover,
  .effort-option.highlighted {
    background: color-mix(in srgb, var(--lc-accent) 16%, transparent);
    color: var(--lc-text);
  }

  .effort-option.active {
    color: var(--lc-accent);
    font-weight: 750;
  }

  .effort-check {
    color: var(--lc-accent);
    font-weight: 800;
  }

  @media (max-width: 760px) {
    .effort-trigger { width: 78px; }
    .effort-title { display: none; }
  }
</style>
