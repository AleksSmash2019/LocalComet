<script lang="ts">
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import TelemetryRow from '$lib/components/common/TelemetryRow.svelte';
  import {
    confirmManagedBinding,
    managedRuntimeStore,
    refreshManagedRuntimeStatus,
    setManagedHarness,
    setManagedSelectedModel,
    startSelectedManagedRuntime,
    stopSelectedManagedRuntime
  } from '$lib/stores/modelGateway';
  import type { HarnessId } from '$lib/types/modelGateway';

  $: status = $managedRuntimeStore.status;
  $: state = status?.state ?? 'NotInstalled';
  $: selectedModel = $managedRuntimeStore.catalog.find((model) => model.model_id === $managedRuntimeStore.selectedModelId);
  $: modelLaunchable = $managedRuntimeStore.readiness?.model_id === selectedModel?.model_id && $managedRuntimeStore.readiness?.launchable === true;
  $: canStart = Boolean(selectedModel) && modelLaunchable && (state === 'Stopped' || state === 'Failed');
  $: canStop = state === 'Ready' || state === 'Starting' || state === 'Validating' || state === 'Failed';
  $: canBind = state === 'Ready' && modelLaunchable && Boolean(status?.runtime_instance_id) && Boolean($managedRuntimeStore.selectedModelId);
  $: tone = state === 'Ready' ? 'ready' : state === 'Failed' ? 'danger' : state === 'Starting' || state === 'Validating' || state === 'Stopping' ? 'info' : 'disabled';

  function onHarnessChange(event: Event) {
    setManagedHarness((event.currentTarget as HTMLSelectElement).value as HarnessId);
  }
</script>

<section class="managed-panel card-surface" aria-label="LocalComet managed runtime">
  <header class="managed-header">
    <div>
      <p class="eyebrow">LocalComet managed runtime</p>
      <h2>Managed llama.cpp</h2>
    </div>
    <StatusBadge label={state === 'NotInstalled' ? 'Not installed' : state} tone={tone} />
  </header>

  <div class="managed-grid">
    <TelemetryRow label="Engine" value="llama.cpp" mono />
    <TelemetryRow label="Managed Runtime" value={status?.installation ?? 'Not installed'} tone={state === 'NotInstalled' ? 'disabled' : 'ready'} />
    <TelemetryRow label="Runtime Version" value={status?.runtime_version ?? 'Not validated'} tone="disabled" mono />
    <TelemetryRow label="Inference" value={$managedRuntimeStore.binding ? 'Bound' : 'Binding required'} tone={$managedRuntimeStore.binding ? 'ready' : 'disabled'} />
  </div>

  <div class="managed-controls">
    <button type="button" onclick={() => void refreshManagedRuntimeStatus()}>Refresh</button>
    <button type="button" disabled={!canStart} onclick={() => void startSelectedManagedRuntime()}>Start Runtime</button>
    <button type="button" disabled={!canStop} onclick={() => void stopSelectedManagedRuntime()}>Stop Runtime</button>
  </div>

  <div class="managed-controls" aria-label="Managed model binding controls">
    <label>
      <span>Managed Model</span>
      <select value={$managedRuntimeStore.selectedModelId} onchange={(event) => void setManagedSelectedModel((event.currentTarget as HTMLSelectElement).value)}>
        <option value="">Select managed model</option>
        {#each $managedRuntimeStore.catalog as model}
          <option value={model.model_id}>{model.display_name} ({Math.round(model.asset_bytes / 1024 / 1024)} MiB)</option>
        {/each}
      </select>
    </label>
    <label>
      <span>Harness</span>
      <select value={$managedRuntimeStore.harnessId} onchange={onHarnessChange}>
        <option value="minimal">minimal</option>
        <option value="native-localcomet">native-localcomet</option>
      </select>
    </label>
    <button type="button" disabled={!canBind} onclick={() => void confirmManagedBinding()}>Confirm Binding</button>
  </div>

  <div class="fingerprint" aria-label="Managed runtime fingerprint">
    <span>Runtime Instance</span>
    <code>{status?.runtime_instance_fingerprint ?? 'Runtime not ready'}</code>
  </div>

  {#if $managedRuntimeStore.logs.stdout_tail.length || $managedRuntimeStore.logs.stderr_tail.length}
    <pre class="runtime-logs" aria-label="Sanitized managed runtime logs">{[...$managedRuntimeStore.logs.stdout_tail, ...$managedRuntimeStore.logs.stderr_tail].join('\n')}</pre>
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
