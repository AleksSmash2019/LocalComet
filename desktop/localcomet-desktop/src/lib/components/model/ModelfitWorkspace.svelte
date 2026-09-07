<script lang="ts">
  import { onMount } from 'svelte';
  import { installModelFitBridge, mountModelFitBundle } from '$lib/bridge/modelfit';
  import { t } from '$lib/i18n';

  let host: HTMLElement;
  let teardownBundle: (() => void) | null = null;
  let bundleError: string | null = null;

  onMount(() => {
    const uninstallBridge = installModelFitBridge();
    void mountModelFitBundle(host)
      .then((teardown) => {
        teardownBundle = teardown;
      })
      .catch((error: unknown) => {
        bundleError = error instanceof Error ? error.message : String(error);
      });
    return () => {
      teardownBundle?.();
      uninstallBridge();
    };
  });
</script>

<div class="modelfit-shell">
  <p class="modelfit-note">{$t('modelfit.title')}</p>
  {#if bundleError}
    <p class="modelfit-error" role="alert">{bundleError}</p>
  {:else}
    <div class="modelfit-host" bind:this={host}></div>
  {/if}
</div>

<style>
  .modelfit-shell {
    width: 100%;
    height: 100%;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px 16px 16px;
    overflow: hidden;
  }

  .modelfit-note {
    color: var(--lc-muted);
    font-size: 12px;
  }

  .modelfit-error {
    color: var(--lc-danger);
    font-size: 12px;
  }

  .modelfit-host {
    flex: 1;
    min-height: 0;
    overflow: auto;
    border-radius: 12px;
    border: 1px solid color-mix(in srgb, var(--lc-border, #2a2a2a) 70%, transparent);
    background: var(--lc-bg);
  }
</style>
