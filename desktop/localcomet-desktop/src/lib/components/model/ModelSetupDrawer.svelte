<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import {
    confirmBinding,
    confirmManagedBinding,
    discoverModels,
    managedRuntimeStore,
    modelGatewayStore,
    probeGateway,
    refreshManagedRuntimeStatus,
    setGatewayHarness,
    setGatewayPortText,
    setManagedHarness,
    setManagedSelectedModel,
    setSelectedModel,
    startSelectedManagedRuntime,
    stopSelectedManagedRuntime
  } from '$lib/stores/modelGateway';
  import { closeModelSetup, modelConnected, modelSetupDrawerOpen, modelSetupMode, setModelConnected } from '$lib/stores/shellStore';
  import type { HarnessId } from '$lib/types/modelGateway';
  import { t } from '$lib/i18n';

  export let onClose: () => void = () => {};

  let portInput = '';
  $: portValid = /^\d+$/.test(portInput) && Number(portInput) >= 1024 && Number(portInput) <= 65535;

  // External flow state
  $: canBindExternal = portValid && Boolean($modelGatewayStore.selectedModelId);
  $: externalStep = !$modelGatewayStore.catalog ? 0 : portValid ? 1 : $modelGatewayStore.models.length ? 2 : 3;

  // Managed flow state
  $: managedState = $managedRuntimeStore.status?.state ?? 'NotInstalled';
  $: managedSelectedModel = $managedRuntimeStore.catalog.find((m) => m.model_id === $managedRuntimeStore.selectedModelId);
  $: managedModelLaunchable = $managedRuntimeStore.readiness?.model_id === managedSelectedModel?.model_id && $managedRuntimeStore.readiness?.launchable === true;
  $: canStartManaged = Boolean(managedSelectedModel) && managedModelLaunchable && (managedState === 'Stopped' || managedState === 'Failed');
  $: canStopManaged = managedState === 'Ready' || managedState === 'Starting' || managedState === 'Validating' || managedState === 'Failed';
  $: canBindManaged = managedState === 'Ready' && managedModelLaunchable && Boolean($managedRuntimeStore.status?.runtime_instance_id) && Boolean($managedRuntimeStore.selectedModelId);
  $: managedTone = managedState === 'Ready' ? 'ready' : managedState === 'Failed' ? 'danger' : managedState === 'Starting' || managedState === 'Validating' || managedState === 'Stopping' ? 'info' : 'disabled';

  function onPortInput(event: Event) {
    const value = (event.currentTarget as HTMLInputElement).value;
    portInput = value.replace(/[^\d]/g, '').slice(0, 5);
    setGatewayPortText(portInput);
  }

  function onExternalHarnessChange(event: Event) {
    setGatewayHarness((event.currentTarget as HTMLSelectElement).value as HarnessId);
  }

  function onManagedHarnessChange(event: Event) {
    setManagedHarness((event.currentTarget as HTMLSelectElement).value as HarnessId);
  }

  function harnessDescription(id: HarnessId): string {
    return id === 'minimal'
      ? $t('setup.no_system_instruction')
      : $t('setup.safe_mode');
  }

  async function onProbe() {
    await probeGateway();
  }

  async function onDiscover() {
    await discoverModels();
  }

  async function onConfirmBinding() {
    await confirmBinding();
    if ($modelGatewayStore.binding) {
      setModelConnected(true);
      closeModelSetup();
    }
  }

  async function onStartManaged() {
    await startSelectedManagedRuntime();
  }

  async function onStopManaged() {
    await stopSelectedManagedRuntime();
  }

  async function onConfirmManagedBinding() {
    await confirmManagedBinding();
    if ($managedRuntimeStore.binding) {
      setModelConnected(true);
      closeModelSetup();
    }
  }

  async function onRefreshManaged() {
    await refreshManagedRuntimeStatus();
  }

  onMount(() => {
    portInput = $modelGatewayStore.portText;
  });

  // Close drawer on Escape handled by shellStore
</script>

<div class="model-setup-drawer" id="model-setup-drawer" role="dialog" aria-modal="true" aria-labelledby="model-setup-title">
  <button type="button" class="drawer-backdrop" onclick={onClose} aria-label={$t('setup.close')}></button>

  <aside class="drawer-panel">
    <header class="drawer-header">
      <h2 id="model-setup-title">{$t('setup.title')}</h2>
      <button type="button" class="icon-button" aria-label={$t('setup.close')} onclick={onClose}>
        <Icon name="cancel" size={20} />
      </button>
    </header>

    <div class="drawer-tabs" role="tablist" aria-label={$t('setup.title')}>
      <button
        type="button"
        role="tab"
        class:active={$modelSetupMode === 'external'}
        aria-selected={$modelSetupMode === 'external'}
        onclick={() => modelSetupMode.set('external')}
      >
        {$t('setup.external_tab')}
      </button>
      <button
        type="button"
        role="tab"
        class:active={$modelSetupMode === 'managed'}
        aria-selected={$modelSetupMode === 'managed'}
        onclick={() => modelSetupMode.set('managed')}
      >
        {$t('setup.managed_tab')}
      </button>
    </div>

    {#if $modelSetupMode === 'external'}
      <div class="drawer-content" role="tabpanel" aria-label={$t('setup.external_tab')}>
        <section class="setup-section" aria-labelledby="external-title">
          <h3 id="external-title">{$t('setup.external_tab')}</h3>
          <p class="section-desc">{$t('setup.external_desc')}</p>

          <div class="step-indicator" aria-label={$t('setup.title')}>
            <span class:active={externalStep >= 1}>{$t('setup.step_port')}</span>
            <span class:active={externalStep >= 2}>{$t('setup.step_model')}</span>
            <span class:active={externalStep >= 3}>{$t('setup.step_mode')}</span>
            <span class:active={externalStep >= 4}>{$t('setup.step_connect')}</span>
          </div>

          <label class="form-field">
            <span>{$t('setup.port')}</span>
            <input
              type="text"
              inputmode="numeric"
              pattern="[0-9]*"
              maxlength="5"
              value={portInput}
              oninput={onPortInput}
              aria-invalid={!portValid}
              placeholder="1234"
            />
          </label>

          <div class="action-row">
            <button type="button" disabled={!portValid || $modelGatewayStore.status === 'Probing'} onclick={onProbe}>
              <Icon name="refresh" size={16} />
              <span>{$t('setup.check_server')}</span>
            </button>
            <button type="button" disabled={!portValid || $modelGatewayStore.status === 'Probing'} onclick={onDiscover}>
              <Icon name="search" size={16} />
              <span>{$t('setup.find_models')}</span>
            </button>
          </div>

          {#if $modelGatewayStore.status === 'Probing'}
            <StatusBadge label={$t('setup.probing')} tone="info" />
          {:else if $modelGatewayStore.status === 'Unavailable'}
            <StatusBadge label={$t('setup.server_unavailable')} tone="danger" />
          {:else if $modelGatewayStore.status === 'Ready'}
            <StatusBadge label={$t('setup.server_ready')} tone="ready" />
          {/if}

          <label class="form-field">
            <span>{$t('setup.model')}</span>
            <select value={$modelGatewayStore.selectedModelId} onchange={(e) => setSelectedModel((e.currentTarget as HTMLSelectElement).value)}>
              <option value="">{$t('setup.select_model')}</option>
              {#each $modelGatewayStore.models as model}
                <option value={model.model_id}>{model.model_id}</option>
              {/each}
            </select>
          </label>

          <label class="form-field">
            <span>{$t('setup.response_mode')}</span>
            <select value={$modelGatewayStore.harnessId} onchange={onExternalHarnessChange}>
              <option value="minimal">{$t('setup.no_system_instruction')}</option>
              <option value="native-localcomet">{$t('setup.safe_mode')}</option>
            </select>
            <p class="field-hint">{harnessDescription($modelGatewayStore.harnessId)}</p>
          </label>

          <button
            type="button"
            class="primary-button full-width"
            disabled={!canBindExternal}
            onclick={onConfirmBinding}
          >
            <Icon name="link" size={16} />
            <span>{$t('setup.connect')}</span>
          </button>

          {#if $modelGatewayStore.binding}
            <div class="fingerprint">
              <span>{$t('setup.binding_id')}</span>
              <code>{$modelGatewayStore.binding.binding_fingerprint}</code>
            </div>
          {/if}

          {#if $modelGatewayStore.lastError}
            <p class="error" role="status">{$modelGatewayStore.lastError.message}</p>
          {/if}
        </section>
      </div>
    {:else}
      <div class="drawer-content" role="tabpanel" aria-label={$t('setup.managed_tab')}>
        <section class="setup-section" aria-labelledby="managed-title">
          <h3 id="managed-title">Runtime LocalComet</h3>
          <p class="section-desc">{$t('setup.managed_desc')}</p>

          <div class="managed-status-grid">
            <div class="status-row">
              <span class="status-label">{$t('setup.runtime_status')}</span>
              <StatusBadge label={managedState === 'NotInstalled' ? $t('setup.not_installed') : managedState} tone={managedTone} />
            </div>
            <div class="status-row">
              <span class="status-label">{$t('setup.runtime_version')}</span>
              <span class="status-value mono">{$managedRuntimeStore.status?.runtime_version ?? $t('setup.not_checked')}</span>
            </div>
            <div class="status-row">
              <span class="status-label">{$t('setup.runtime_model')}</span>
              <span class="status-value">{managedSelectedModel?.display_name ?? $t('setup.not_selected')}</span>
            </div>
            <div class="status-row">
              <span class="status-label">{$t('setup.runtime_inference')}</span>
              <span class="status-value">{$managedRuntimeStore.binding ? $t('setup.connected') : $t('setup.needs_binding')}</span>
            </div>
          </div>

          {#if managedState === 'NotInstalled'}
            <div class="empty-state">
              <p class="empty-title">{$t('setup.runtime_not_installed')}</p>
              <p class="empty-desc">{$t('setup.install_available')}</p>
              <button type="button" class="secondary-button" disabled>{$t('setup.install_available')}</button>
            </div>
          {:else}
            <div class="action-row">
              <button type="button" onclick={onRefreshManaged}>
                <Icon name="refresh" size={16} />
                <span>{$t('setup.refresh')}</span>
              </button>
              <button type="button" disabled={!canStartManaged} onclick={onStartManaged}>
                <Icon name="play" size={16} />
                <span>{$t('setup.start_runtime')}</span>
              </button>
              <button type="button" disabled={!canStopManaged} onclick={onStopManaged}>
                <Icon name="stop" size={16} />
                <span>{$t('setup.stop_runtime')}</span>
              </button>
            </div>

            <label class="form-field">
              <span>{$t('setup.runtime_model')}</span>
              <select value={$managedRuntimeStore.selectedModelId} onchange={(e) => void setManagedSelectedModel((e.currentTarget as HTMLSelectElement).value)}>
                <option value="">{$t('setup.select_local_model')}</option>
                {#each $managedRuntimeStore.catalog as model}
                  <option value={model.model_id}>{model.display_name} ({Math.round(model.asset_bytes / 1024 / 1024)} MiB)</option>
                {/each}
              </select>
            </label>

            <label class="form-field">
              <span>{$t('setup.response_mode')}</span>
              <select value={$managedRuntimeStore.harnessId} onchange={onManagedHarnessChange}>
                <option value="minimal">{$t('setup.no_system_instruction')}</option>
                <option value="native-localcomet">{$t('setup.safe_mode')}</option>
              </select>
              <p class="field-hint">{harnessDescription($managedRuntimeStore.harnessId)}</p>
            </label>

            <button
              type="button"
              class="primary-button full-width"
              disabled={!canBindManaged}
              onclick={onConfirmManagedBinding}
            >
              <Icon name="link" size={16} />
              <span>{$t('setup.connect')}</span>
            </button>

            {#if $managedRuntimeStore.binding}
              <div class="fingerprint">
                <span>{$t('setup.binding_id')}</span>
                <code>{$managedRuntimeStore.binding.binding_fingerprint}</code>
              </div>
            {/if}
          {/if}

          {#if $managedRuntimeStore.lastError}
            <p class="error" role="status">{$managedRuntimeStore.lastError.message}</p>
          {/if}
        </section>
      </div>
    {/if}
  </aside>
</div>

<style>
  .model-setup-drawer {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 50;
    display: flex;
    align-items: center;
    justify-content: flex-end;
  }

  .drawer-backdrop {
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(4px);
  }

  .drawer-panel {
    position: relative;
    width: min(480px, 100vw);
    height: 100%;
    max-height: 100vh;
    background: var(--lc-bg-elevated);
    border-left: var(--border-thin);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: var(--lc-shadow);
  }

  .drawer-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--lc-space-4);
    border-bottom: var(--border-thin);
  }

  .drawer-header h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 700;
  }

  .icon-button {
    width: 40px;
    height: 40px;
    display: grid;
    place-items: center;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-solid);
    color: var(--lc-muted);
    cursor: pointer;
  }

  .icon-button:hover {
    background: var(--lc-panel-soft);
    border-color: var(--lc-line);
    color: var(--lc-text);
  }

  .drawer-tabs {
    display: flex;
    border-bottom: var(--border-thin);
    background: var(--lc-panel-solid);
  }

  .drawer-tabs button {
    flex: 1;
    padding: var(--lc-space-3) var(--lc-space-4);
    border: none;
    background: transparent;
    color: var(--lc-muted);
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
  }

  .drawer-tabs button:hover {
    color: var(--lc-text);
    background: var(--lc-panel-soft);
  }

  .drawer-tabs button.active {
    color: var(--lc-accent);
    border-bottom-color: var(--lc-accent);
    background: var(--lc-accent-dim);
  }

  .drawer-content {
    flex: 1;
    overflow-y: auto;
    padding: var(--lc-space-4);
  }

  .setup-section {
    display: grid;
    gap: var(--lc-space-4);
  }

  .setup-section h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 700;
  }

  .section-desc {
    margin: 0;
    color: var(--lc-muted);
    font-size: 13px;
  }

  .step-indicator {
    display: flex;
    gap: var(--lc-space-2);
    font-size: 11px;
    font-weight: 700;
    color: var(--lc-faint);
    font-family: var(--lc-mono);
  }

  .step-indicator span {
    padding: var(--lc-space-1) var(--lc-space-2);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-soft);
  }

  .step-indicator span.active {
    color: var(--lc-accent);
    background: var(--lc-accent-dim);
    border-color: var(--lc-line-strong);
  }

  .form-field {
    display: grid;
    gap: var(--lc-space-1);
    min-width: 0;
  }

  .form-field span {
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 700;
  }

  .form-field input,
  .form-field select {
    min-height: 36px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-soft);
    color: var(--lc-text);
    font: inherit;
    padding: 0 var(--lc-space-3);
  }

  .form-field input[aria-invalid="true"] {
    border-color: var(--lc-danger);
  }

  .field-hint {
    margin: 0;
    color: var(--lc-faint);
    font-size: 11px;
    line-height: 1.4;
  }

  .action-row {
    display: flex;
    flex-wrap: wrap;
    gap: var(--lc-space-2);
  }

  .action-row button {
    display: inline-flex;
    align-items: center;
    gap: var(--lc-space-2);
    min-height: 36px;
    padding: 0 var(--lc-space-3);
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-solid);
    color: var(--lc-text);
    font-weight: 700;
    font-size: 12px;
    cursor: pointer;
  }

  .action-row button:hover:not(:disabled) {
    background: var(--lc-panel-soft);
    border-color: var(--lc-line);
  }

  .action-row button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .primary-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--lc-space-2);
    min-height: 40px;
    padding: 0 var(--lc-space-4);
    border: none;
    border-radius: var(--lc-radius-sm);
    background: var(--lc-accent);
    color: var(--lc-logo-cut);
    font-weight: 800;
    font-size: 13px;
    cursor: pointer;
  }

  .primary-button.full-width {
    width: 100%;
  }

  .primary-button:hover:not(:disabled) {
    background: var(--lc-accent-strong);
  }

  .primary-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .secondary-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--lc-space-2);
    min-height: 40px;
    padding: 0 var(--lc-space-4);
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-soft);
    color: var(--lc-muted);
    font-weight: 700;
    font-size: 13px;
    cursor: not-allowed;
  }

  .fingerprint {
    display: grid;
    gap: var(--lc-space-1);
    padding-top: var(--lc-space-2);
    border-top: var(--border-thin);
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 700;
  }

  .fingerprint code {
    overflow-wrap: anywhere;
    font-family: var(--lc-mono);
    font-size: 11px;
  }

  .error {
    margin: 0;
    color: var(--lc-danger);
    font-weight: 700;
    font-size: 12px;
  }

  .managed-status-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--lc-space-2) var(--lc-space-4);
  }

  .status-row {
    display: flex;
    flex-direction: column;
    gap: var(--lc-space-1);
  }

  .status-label {
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 700;
  }

  .status-value {
    color: var(--lc-text);
    font-size: 13px;
  }

  .status-value.mono {
    font-family: var(--lc-mono);
  }

  .empty-state {
    display: grid;
    gap: var(--lc-space-2);
    padding: var(--lc-space-6) var(--lc-space-4);
    text-align: center;
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    background: var(--lc-panel-soft);
  }

  .empty-title {
    margin: 0;
    font-size: 14px;
    font-weight: 700;
    color: var(--lc-text);
  }

  .empty-desc {
    margin: 0;
    color: var(--lc-muted);
    font-size: 12px;
  }

  @media (max-width: 680px) {
    .drawer-panel {
      width: 100vw;
      border-left: none;
    }

    .managed-status-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
