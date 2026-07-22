<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import { t } from '$lib/i18n';
  import type { SelectedFilePreview } from '$lib/types/files';

  export let preview: SelectedFilePreview;
  export let triggerElement: HTMLElement | null = null;
  export let onClose: () => void = () => undefined;

  let dialogElement: HTMLDivElement;
  let previousFocus: HTMLElement | null = null;

  onMount(() => {
    previousFocus = triggerElement ?? (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    void tick().then(() => dialogElement?.querySelector<HTMLButtonElement>('.preview-close')?.focus());
  });

  onDestroy(() => {
    (triggerElement ?? previousFocus)?.focus();
  });

  function handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== 'Tab') return;
    const focusable = Array.from(dialogElement.querySelectorAll<HTMLElement>('button:not([disabled]), [tabindex]:not([tabindex="-1"])'));
    if (focusable.length === 0) {
      event.preventDefault();
      dialogElement.focus();
      return;
    }
    const current = focusable.indexOf(document.activeElement as HTMLElement);
    const next = event.shiftKey
      ? (current <= 0 ? focusable.length - 1 : current - 1)
      : (current >= focusable.length - 1 ? 0 : current + 1);
    event.preventDefault();
    focusable[next]?.focus();
  }

  function handleBackdropClick(event: MouseEvent): void {
    if (event.target === event.currentTarget) onClose();
  }
</script>

<div class="preview-backdrop" role="presentation" onclick={handleBackdropClick} onkeydown={handleKeydown}>
  <div
    bind:this={dialogElement}
    class="preview-dialog"
    role="dialog"
    aria-modal="true"
    aria-labelledby="file-preview-title"
    aria-describedby="file-preview-counts"
    tabindex="-1"
  >
    <header>
      <div>
        <span>{$t('files.preview_eyebrow')}</span>
        <h2 id="file-preview-title">{preview.filename}</h2>
      </div>
      <button type="button" class="preview-close" aria-label={$t('files.close_preview')} onclick={onClose}>
        <Icon name="cancel" size={16} />
      </button>
    </header>
    <p id="file-preview-counts" class="counts">
      {preview.displayed_bytes.toLocaleString()} / {preview.original_bytes.toLocaleString()} {$t('files.bytes')}
      · {preview.displayed_characters.toLocaleString()} / {preview.original_characters.toLocaleString()} {$t('files.characters')}
      {#if preview.truncated} · {$t('files.preview_truncated')}{/if}
    </p>
    <pre>{preview.content}</pre>
  </div>
</div>

<style>
  .preview-backdrop {
    position: fixed;
    inset: 0;
    z-index: 90;
    display: grid;
    place-items: center;
    padding: var(--lc-space-4);
    background: color-mix(in srgb, #000 72%, transparent);
  }

  .preview-dialog {
    width: min(780px, 100%);
    max-height: min(760px, calc(100vh - 32px));
    display: grid;
    grid-template-rows: auto auto minmax(0, 1fr);
    overflow: hidden;
    border: var(--border-thin);
    border-radius: var(--lc-radius);
    background: var(--lc-panel-solid);
    box-shadow: var(--lc-shadow);
    color: var(--lc-text);
  }

  header {
    display: flex;
    justify-content: space-between;
    gap: var(--lc-space-3);
    align-items: flex-start;
    border-bottom: var(--border-thin);
    padding: var(--lc-space-4);
  }

  header span {
    color: var(--lc-muted);
    font-size: 11px;
    font-weight: 760;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  h2 {
    margin: var(--lc-space-1) 0 0;
    overflow-wrap: anywhere;
    font-size: 17px;
  }

  .preview-close {
    min-width: 36px;
    min-height: 36px;
    display: grid;
    place-items: center;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-soft);
    color: var(--lc-text);
    cursor: pointer;
  }

  .counts {
    margin: 0;
    border-bottom: var(--border-thin);
    padding: var(--lc-space-2) var(--lc-space-4);
    color: var(--lc-muted);
    font-size: 11px;
  }

  pre {
    min-width: 0;
    margin: 0;
    overflow: auto;
    padding: var(--lc-space-4);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    color: var(--lc-text);
    font-family: var(--lc-mono);
    font-size: 12px;
    line-height: 1.55;
    tab-size: 2;
  }

  @media (max-width: 560px) {
    .preview-backdrop {
      padding: var(--lc-space-2);
    }

    .preview-dialog {
      max-height: calc(100vh - 16px);
    }
  }
</style>
