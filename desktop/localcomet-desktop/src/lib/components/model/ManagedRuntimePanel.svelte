<script lang="ts">
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import TelemetryRow from '$lib/components/common/TelemetryRow.svelte';
  import {
    confirmManagedBinding,
    inferenceBusy,
    managedRuntimeStore,
    refreshManagedRuntimeStatus,
    setManagedHarness,
    setManagedSelectedModel,
    startSelectedManagedRuntime,
    stopSelectedManagedRuntime
  } from '$lib/stores/modelGateway';
  import type { HarnessId } from '$lib/types/modelGateway';
  import { t } from '$lib/i18n';

  type Translate = (key: string) => string;

  function translateRuntimeState(value: string | undefined, translate: Translate): string {
    switch (value) {
      case 'NotInstalled': return translate('model.not_installed');
      case 'Starting': return translate('model.runtime_starting');
      case 'Validating': return translate('model.runtime_validating');
      case 'Ready': return translate('model.ready');
      case 'Stopping': return translate('model.runtime_stopping');
      case 'Stopped': return translate('model.runtime_stopped');
      case 'Failed': return translate('model.runtime_failed');
      default: return translate('model.status_unknown');
    }
  }

  function translateInstalledState(value: string | undefined, translate: Translate): string {
    if (!value) return translate('model.not_installed');
    return value === 'Installed' ? translate('model.installed') : translate('model.status_unknown');
  }

  function translateModelState(value: string | undefined, translate: Translate): string {
    if (value === 'Ready') return translate('model.ready');
    if (!value) return translate('model.unavailable');
    return translate('model.status_unknown');
  }

  $: status = $managedRuntimeStore.status;
  $: state = status?.state ?? 'NotInstalled';
  $: selectedModel = $managedRuntimeStore.catalog.find((model) => model.model_id === $managedRuntimeStore.selectedModelId);
  $: modelLaunchable = $managedRuntimeStore.readiness?.model_id === selectedModel?.model_id && $managedRuntimeStore.readiness?.launchable === true;
  // A different loaded model does not block start any more: the store unloads
  // it first (one-click switch). Only the same-model start keeps the literal
  // "Start Runtime" label; everything else offers the switch wording.
  $: startLabelKey = state === 'Stopped' || state === 'Failed' || status?.model_id !== $managedRuntimeStore.selectedModelId
    ? 'model.switch_model'
    : 'model.start_runtime';
  $: canStart = !$inferenceBusy && Boolean(selectedModel) && modelLaunchable && (state === 'Stopped' || state === 'Failed' || ((state === 'Ready' || state === 'Starting' || state === 'Validating') && status?.model_id !== $managedRuntimeStore.selectedModelId));
  $: canStop = !$inferenceBusy && (state === 'Ready' || state === 'Starting' || state === 'Validating' || state === 'Failed');
  $: canBind = !$inferenceBusy && state === 'Ready' && status?.model_state === 'Ready' && status?.inference_ready === true && status?.model_id === $managedRuntimeStore.selectedModelId && modelLaunchable && Boolean(status?.runtime_instance_id) && Boolean($managedRuntimeStore.selectedModelId);
  $: tone = state === 'Ready' ? 'ready' : state === 'Failed' ? 'danger' : state === 'Starting' || state === 'Validating' || state === 'Stopping' ? 'info' : 'disabled';

  function onHarnessChange(event: Event) {
    setManagedHarness((event.currentTarget as HTMLSelectElement).value as HarnessId);
  }
</script>

  <section class="managed-panel card-surface" aria-label={$t('model.managed_runtime')}>

  <header class="managed-header">
    <div>
      <p class="eyebrow">{$t('model.managed_runtime')}</p>
      <h2>{$t('model.managed_runtime_title')}</h2>
    </div>
    <StatusBadge label={translateRuntimeState(state, $t)} tone={tone} />
  </header>

  <div class="managed-grid">
    <TelemetryRow label={$t('model.engine')} value="llama.cpp" mono />
    <TelemetryRow label={$t('model.managed_runtime_label')} value={translateInstalledState(status?.installation, $t)} tone={state === 'NotInstalled' ? 'disabled' : 'ready'} />
    <TelemetryRow label={$t('model.runtime_version')} value={status?.runtime_version ?? $t('model.not_validated')} tone="disabled" mono />
    <TelemetryRow label={$t('model.runtime_id')} value={status?.runtime_id ?? $t('model.not_selected')} tone={status?.runtime_id ? 'ready' : 'disabled'} mono />
    <TelemetryRow label={$t('model.model_state')} value={translateModelState(status?.model_state, $t)} tone={status?.model_state === 'Ready' ? 'ready' : 'disabled'} />
    <TelemetryRow label={$t('model.inference')} value={$t(status?.inference_ready ? 'model.ready' : 'model.unavailable')} tone={status?.inference_ready ? 'ready' : 'disabled'} />
  </div>

  <div class="managed-controls">
    <button type="button" aria-label={$t('model.refresh_runtime')} disabled={$inferenceBusy} onclick={() => void refreshManagedRuntimeStatus()}>{$t('model.refresh_runtime')}</button>
    <button type="button" aria-label={$t(startLabelKey)} disabled={!canStart} onclick={() => void startSelectedManagedRuntime()}>{$t(startLabelKey)}</button>
    <button type="button" aria-label={$t('model.stop_runtime')} disabled={!canStop} onclick={() => void stopSelectedManagedRuntime()}>{$t('model.stop_runtime')}</button>
  </div>

  <div class="managed-controls" aria-label={$t('model.binding_controls')}>
    <label>
      <span>{$t('model.managed_model')}</span>
      <select disabled={$inferenceBusy} value={$managedRuntimeStore.selectedModelId} onchange={(event) => void setManagedSelectedModel((event.currentTarget as HTMLSelectElement).value)}>
        <option value="">{$t('model.select_managed')}</option>
        {#each $managedRuntimeStore.catalog as model}
          <option value={model.model_id}>{model.display_name} ({Math.round(model.asset_bytes / 1024 / 1024)} MiB)</option>
        {/each}
      </select>
    </label>
    <label>
      <span>{$t('model.harness')}</span>
      <select disabled={$inferenceBusy} value={$managedRuntimeStore.harnessId} onchange={onHarnessChange}>
        <option value="minimal">{$t('model.harness_minimal')}</option>
        <option value="native-localcomet">{$t('model.harness_native')}</option>
      </select>
    </label>
    <button type="button" aria-label={$t('model.confirm_binding')} disabled={!canBind} onclick={() => void confirmManagedBinding()}>{$t('model.confirm_binding')}</button>
  </div>

  <div class="fingerprint" aria-label={$t('model.binding_fingerprint')}>
    <span>{$t('model.runtime_instance')}</span>
    <code>{status?.runtime_instance_fingerprint ?? $t('model.runtime_not_ready')}</code>
  </div>

  {#if $managedRuntimeStore.logs.stdout_tail.length || $managedRuntimeStore.logs.stderr_tail.length}
    <pre class="runtime-logs" aria-label={$t('diag.sanitized_runtime_logs')}>{[...$managedRuntimeStore.logs.stdout_tail, ...$managedRuntimeStore.logs.stderr_tail].join('\n')}</pre>
  {/if}
  {#if $managedRuntimeStore.lastError}
    <p class="managed-error" role="status">{$managedRuntimeStore.lastError.message}</p>
  {/if}
</section>

<style>
  .managed-panel {
    display: grid;
    gap: 14px;
    padding: 16px;
    border-color: var(--lc-border-strong);
  }

  .managed-header,
  .managed-controls {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .managed-header {
    justify-content: space-between;
  }

  .eyebrow {
    margin: 0 0 3px;
    color: var(--lc-muted);
    font-family: var(--lc-mono);
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
  }

  h2 {
    margin: 0;
    font-size: 16px;
  }

  .managed-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  label {
    display: grid;
    gap: 5px;
    min-width: 180px;
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 700;
  }

  select {
    min-height: 36px;
    border: 1px solid var(--lc-border);
    border-radius: 6px;
    background: var(--lc-panel-soft);
    color: var(--lc-text);
    font: inherit;
    padding: 8px 10px;
  }

  button {
    min-height: 36px;
  }

  .fingerprint {
    display: grid;
    gap: 5px;
    min-width: 0;
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 700;
  }

  code,
  .runtime-logs {
    overflow-wrap: anywhere;
    font-family: var(--lc-mono);
  }

  .runtime-logs {
    max-height: 140px;
    margin: 0;
    overflow: auto;
    white-space: pre-wrap;
    border: 1px solid var(--lc-border);
    border-radius: 6px;
    background: var(--lc-panel-soft);
    color: var(--lc-text);
    padding: 12px;
  }

  .managed-error {
    margin: 0;
    color: var(--lc-danger);
    font-weight: 700;
  }

  @media (max-width: 720px) {
    .managed-grid {
      grid-template-columns: 1fr;
    }

    label,
    .managed-controls button {
      width: 100%;
    }
  }
</style>
