<script lang="ts">
  import { onMount } from 'svelte';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import DownloadProgress from '$lib/components/model/DownloadProgress.svelte';
  import {
    acquisitionBusy,
    artifactAcquisitionStore,
    cancelApprovedArtifactDownload,
    downloadApprovedArtifact,
    initializeArtifactAcquisition,
    removeApprovedManagedModel,
    setUpManagedModel,
    setUpLocalAi
  } from '$lib/stores/artifactAcquisition';
  import {
    connectSelectedManagedModel,
    managedConnectionBusy,
    managedModelReady,
    managedRuntimeStore,
    refreshManagedRuntimeStatus,
    setManagedSelectedModel,
    stopSelectedManagedRuntime
  } from '$lib/stores/modelGateway';
  import { importCustomModel } from '$lib/bridge/modelGateway';
  import { open } from '@tauri-apps/plugin-dialog';
  import { t } from '$lib/i18n';
  import type { ApprovedDownloadableArtifact, ManagedDownloadableArtifact } from '$lib/types/modelGateway';
  import Icon from '$lib/components/common/Icon.svelte';

  // The separate "Hugging Face" settings tab was removed: the approved catalog
  // and the list of already-downloaded models now render together in one
  // "Models" section, so this component no longer needs a mode switch.

  type Confirmation =
    | { readonly action: 'setup'; readonly artifacts: readonly ManagedDownloadableArtifact[] }
    | { readonly action: 'download'; readonly artifacts: readonly ApprovedDownloadableArtifact[] }
    | { readonly action: 'remove'; readonly artifacts: readonly ManagedDownloadableArtifact[] }
;

  let confirmation: Confirmation | null = null;
  let actionPending = false;
  let selectedModelId = $managedRuntimeStore.selectedModelId;


  $: runtime = $managedRuntimeStore.runtimeCatalog?.[0] ?? null;
  $: runtimes = $managedRuntimeStore.runtimeCatalog ?? [];
  $: modelArtifacts = $artifactAcquisitionStore.artifacts.filter((artifact) => artifact.kind === 'model');
  $: approvedModelArtifacts = modelArtifacts.filter((artifact): artifact is ApprovedDownloadableArtifact => artifact.trust_kind === 'approved_catalog');
  $: customModelArtifacts = modelArtifacts.filter((artifact) => artifact.trust_kind === 'user_supplied');
  $: selectedModelArtifact = modelArtifacts.find((artifact) => artifact.artifact_id === selectedModelId) ?? null;
  $: runtimeArtifact = $artifactAcquisitionStore.artifacts.find((artifact): artifact is ApprovedDownloadableArtifact => artifact.kind === 'runtime') ?? null;
  $: runtimeInstalled = runtimes.some((item) => installationState(item.runtime_id) === 'valid');
  $: modelInstalled = selectedModelArtifact ? installationState(selectedModelArtifact.artifact_id) === 'valid' : false;
  $: customModelInvalid = selectedModelArtifact?.trust_kind === 'user_supplied' && !modelInstalled;
  $: runtimeDownload = runtimeArtifact ? $artifactAcquisitionStore.downloads[runtimeArtifact.artifact_id] ?? null : null;
  $: modelDownload = selectedModelArtifact ? $artifactAcquisitionStore.downloads[selectedModelArtifact.artifact_id] ?? null : null;
  $: activeDownload = Object.values($artifactAcquisitionStore.downloads).find((download) => !isTerminal(download)) ?? null;
  $: modelCanBeRemoved = selectedModelArtifact !== null && (modelInstalled || selectedModelArtifact.trust_kind === 'user_supplied');
  $: canRemove = modelCanBeRemoved && !activeDownload && !['Ready', 'Starting', 'Validating', 'Stopping'].includes($managedRuntimeStore.status?.state ?? '');

  onMount(() => {
    void initializeArtifactAcquisition();
  });

  function installationState(artifactId: string): string {
    return $managedRuntimeStore.installedArtifacts.find((artifact) => artifact.artifact_id === artifactId)?.installation_status ?? 'not_installed';
  }

  function displayState(state: string): string {
    return $t(`models.state.${state}`);
  }

  async function requestSetup(): Promise<void> {
    const artifacts = [runtimeArtifact, selectedModelArtifact].filter((artifact): artifact is ManagedDownloadableArtifact => artifact !== null);
    if (artifacts.length === 2 && (!customModelInvalid || selectedModelArtifact?.trust_kind === 'approved_catalog')) {
      const modelId = artifacts.find((artifact) => artifact.kind === 'model')?.artifact_id;
      if (modelId) {
        actionPending = true;
        try {
          await setUpManagedModel(modelId);
        } finally {
          actionPending = false;
        }
      }
    }
  }

  async function requestDownload(artifact: ApprovedDownloadableArtifact): Promise<void> {
    actionPending = true;
    try {
      await downloadApprovedArtifact(artifact.artifact_id);
    } finally {
      actionPending = false;
    }
  }

  function requestRemoval(artifact: ManagedDownloadableArtifact): void {
    confirmation = { action: 'remove', artifacts: [artifact] };
  }

  async function confirm(): Promise<void> {
    const selected = confirmation;
    confirmation = null;
    if (!selected) return;
    actionPending = true;
    try {
      await removeApprovedManagedModel(selected.artifacts[0].artifact_id);
    } finally {
      actionPending = false;
    }
  }

  async function connect(): Promise<void> {
    if (!selectedModelArtifact) return;
    actionPending = true;
    try {
      await setManagedSelectedModel(selectedModelArtifact.artifact_id);
      await connectSelectedManagedModel();
    } finally {
      actionPending = false;
    }
  }

  function onModelChange(event: Event) {
    const value = (event.currentTarget as HTMLSelectElement).value;
    selectedModelId = value;
    void setManagedSelectedModel(value);
  }

  function isTerminal(download: { readonly lifecycle: string }): boolean {
    return ['cancelled', 'completed', 'failed'].includes(download.lifecycle);
  }

  async function handleImportGguf() {
    try {
      const file = await open({
        multiple: false,
        filters: [{ name: 'GGUF Models', extensions: ['gguf'] }]
      });
      if (typeof file === 'string') {
        const filename = file.split(/[\\/]/).pop() || 'model.gguf';
        actionPending = true;
        await importCustomModel(file, filename);
        await refreshManagedRuntimeStatus();
      }
    } catch (err) {
      console.error('Import failed', err);
    } finally {
      actionPending = false;
    }
  }

  function formatBytes(value: number): string {
    return `${(value / 1024 / 1024).toFixed(value >= 1024 * 1024 * 1024 ? 0 : 1)} MiB`;
  }

  function totalBytes(artifacts: readonly ManagedDownloadableArtifact[]): number {
    return artifacts.reduce((total, artifact) => total + artifact.expected_bytes, 0);
  }

  function modelStatus(artifact: ManagedDownloadableArtifact): string {
    const state = installationState(artifact.artifact_id);
    if (state === 'valid') return $t('models.state.valid');
    if (state === 'not_installed') return $t('models.state.not_installed');
    return displayState(state);
  }

  function modelTone(artifact: ManagedDownloadableArtifact): string {
    return installationState(artifact.artifact_id) === 'valid' ? 'ready' : 'disabled';
  }
</script>

<section class="models-section" aria-labelledby="settings-models">
  <div class="section-heading">
    <div>
      <h3 id="settings-models">{$t('models.title')}</h3>
      <p>{$t('models.boundary')}</p>
    </div>
    <div style="display: flex; gap: 8px;">
      <button type="button" class="refresh" disabled={$acquisitionBusy} onclick={() => void refreshManagedRuntimeStatus()}>
        {$t('models.refresh')}
      </button>
      <button type="button" disabled={actionPending} onclick={handleImportGguf}>
        {$t('models.import_gguf')}
      </button>
    </div>
  </div>

  <div class="artifact-card">
    <div class="artifact-heading">
      <div>
        <span class="artifact-kind">{$t('models.engine')}</span>
        <strong>{runtime ? `llama.cpp ${runtime.release_tag}` : 'llama.cpp'}</strong>
      </div>
      <StatusBadge label={displayState(runtimeInstalled ? 'valid' : installationState(runtime?.runtime_id ?? ''))} tone={runtimeInstalled ? 'ready' : 'disabled'} />
    </div>
    <dl>
      <div><dt>{$t('models.release')}</dt><dd>{runtime?.release_tag ?? '—'}</dd></div>
      <div><dt>{$t('models.license')}</dt><dd>{runtime?.license_id ?? '—'}</dd></div>
      <div><dt>{$t('models.size')}</dt><dd>{runtimeArtifact ? formatBytes(runtimeArtifact.expected_bytes) : '—'}</dd></div>
      {#if runtimeDownload}
        <div><dt>{$t('models.download')}</dt><dd>{displayState(runtimeDownload.lifecycle)} {runtimeDownload.percent === null ? '' : `${runtimeDownload.percent}%`}</dd></div>
      {/if}
    </dl>
    <dl class="runtime-variants">
      {#each runtimes as item}
        <div>
          <dt>{$t(`models.variant.${item.variant}`)}</dt>
          <dd>
            <StatusBadge label={displayState(installationState(item.runtime_id))} tone={installationState(item.runtime_id) === 'valid' ? 'ready' : 'disabled'} />
          </dd>
        </div>
      {/each}
    </dl>
  </div>

  <div class="artifact-card">
    <div class="artifact-heading">
      <div>
        <span class="artifact-kind">{$t('models.model')}</span>
        <strong>{selectedModelArtifact ? `${selectedModelArtifact.display_name} (${formatBytes(selectedModelArtifact.expected_bytes)})` : $t('models.not_available')}</strong>
      </div>
      <StatusBadge label={displayState(modelInstalled ? 'valid' : installationState(selectedModelArtifact?.artifact_id ?? ''))} tone={modelInstalled ? 'ready' : 'disabled'} />
    </div>
    <label>
      <span>{$t('models.managed_model')}</span>
      <select disabled={$managedConnectionBusy} value={selectedModelId} onchange={onModelChange}>
        <option value="" disabled hidden>{$t('models.not_available')}</option>
        {#each modelArtifacts as artifact}
          <option value={artifact.artifact_id}>{artifact.display_name} · {artifact.license_id ?? $t('models.license_unknown')} · {formatBytes(artifact.expected_bytes)}</option>
        {/each}
      </select>
    </label>
    <dl>
      <div><dt>{$t('models.model_id')}</dt><dd>{selectedModelArtifact?.artifact_id ?? '—'}</dd></div>
      <div><dt>{$t('models.format')}</dt><dd>{selectedModelArtifact ? `${selectedModelArtifact.format ?? '—'} · ${selectedModelArtifact.quantization ?? '—'}` : '—'}</dd></div>
      <div><dt>{$t('models.license')}</dt><dd>{selectedModelArtifact ? selectedModelArtifact.license_id ?? $t('models.license_unknown') : '—'}</dd></div>
      <div><dt>{$t('models.size')}</dt><dd>{selectedModelArtifact ? formatBytes(selectedModelArtifact.expected_bytes) : '—'}</dd></div>
      {#if selectedModelArtifact?.trust_kind === 'user_supplied'}
        <div><dt>{$t('models.custom_source')}</dt><dd>{selectedModelArtifact.source_identity}</dd></div>
        <div><dt>{$t('models.sha256')}</dt><dd>{selectedModelArtifact.expected_sha256}</dd></div>
      {/if}
      <div><dt>{$t('models.connection')}</dt><dd>{$managedModelReady ? $t('models.connected') : $t('models.not_connected')}</dd></div>
      {#if modelDownload}
        <div><dt>{$t('models.download')}</dt><dd>{displayState(modelDownload.lifecycle)} {modelDownload.percent === null ? '' : `${modelDownload.percent}%`}</dd></div>
      {/if}
    </dl>
  </div>

  <div class="catalog-card">
    <div class="catalog-heading">
      <div>
        <span class="artifact-kind">{$t('models.approved_catalog')}</span>
        <strong>{$t('models.approved_catalog_title')}</strong>
      </div>
      <span class="catalog-count">{approvedModelArtifacts.length} {$t('models.approved_catalog_count')}</span>
    </div>
    <ul class="catalog-list">
      {#each approvedModelArtifacts as artifact}
        <li class="catalog-item" class:selected={artifact.artifact_id === selectedModelId}>
          <div class="catalog-main">
            <strong>{artifact.display_name}</strong>
            <StatusBadge label={modelStatus(artifact)} tone={modelTone(artifact)} />
          </div>
          <dl>
            <div><dt>{$t('models.model_id')}</dt><dd>{artifact.artifact_id}</dd></div>
            <div><dt>{$t('models.format')}</dt><dd>{artifact.format ?? '—'} · {artifact.quantization ?? '—'}</dd></div>
            <div><dt>{$t('models.license')}</dt><dd>{artifact.license_id ?? '—'}</dd></div>
            <div><dt>{$t('models.size')}</dt><dd>{formatBytes(artifact.expected_bytes)}</dd></div>
          </dl>
        </li>
      {:else}
        <li class="catalog-empty">{$t('models.approved_catalog_empty')}</li>
      {/each}
    </ul>
  </div>


  {#if activeDownload}
    <DownloadProgress
      title={$t('models.current_download')}
      detail={`${displayState(activeDownload.lifecycle)} - ${(activeDownload.received_bytes / 1024 / 1024).toFixed(1)} / ${(activeDownload.expected_bytes / 1024 / 1024).toFixed(1)} MiB`}
      percent={activeDownload.percent ?? null}
      onCancel={() => void cancelApprovedArtifactDownload(activeDownload.artifact_id)}
    />
  {/if}
  {#if $artifactAcquisitionStore.setup.lifecycle === 'running' && !activeDownload}
    <DownloadProgress
      title={$t('models.setup_progress')}
      detail={$t('models.connecting')}
      percent={null}
      onCancel={null}
    />
  {/if}
  {#if $managedConnectionBusy}
    <DownloadProgress
      title={$t('models.connecting')}
      detail={$t('chat.model_loading_detail')}
      percent={null}
      onCancel={null}
    />
  {/if}

  <div class="actions" aria-label={$t('models.actions')}>
    {#if selectedModelArtifact && (!runtimeInstalled || !modelInstalled) && !activeDownload && !customModelInvalid}
      <button type="button" class="primary" disabled={actionPending} onclick={requestSetup}>{$t('models.setup')}</button>
    {/if}
    {#if runtimeArtifact && !runtimeInstalled && !activeDownload}
      <button type="button" disabled={actionPending} onclick={() => requestDownload(runtimeArtifact)}><span>{runtimeDownload?.lifecycle === 'failed' || runtimeDownload?.lifecycle === 'cancelled' ? $t('models.retry_engine') : $t('models.install_engine')}</span></button>
    {/if}
    {#if selectedModelArtifact?.trust_kind === 'approved_catalog' && !modelInstalled && !activeDownload}
      <button type="button" disabled={actionPending} onclick={() => requestDownload(selectedModelArtifact)}><span>{modelDownload?.lifecycle === 'failed' || modelDownload?.lifecycle === 'cancelled' ? $t('models.retry_model') : $t('models.download_model')}</span></button>
    {/if}
    {#if runtimeInstalled && modelInstalled && !$managedModelReady && !activeDownload}
      <button type="button" class="primary" disabled={actionPending} onclick={() => void connect()}>{$t('models.connect')}</button>
    {/if}
    {#if $managedRuntimeStore.status?.state === 'Ready'}
      <button type="button" disabled={actionPending} onclick={() => void stopSelectedManagedRuntime()}>{$t('models.disconnect')}</button>
    {/if}
    {#if selectedModelArtifact && modelCanBeRemoved && !activeDownload}
      <button type="button" class="danger" disabled={!canRemove || actionPending} onclick={() => requestRemoval(selectedModelArtifact)}>{$t('models.remove_model')}</button>
    {/if}
  </div>

  {#if $artifactAcquisitionStore.lastError}
    <p class="error" role="status">{$t('models.download_error')}: {$artifactAcquisitionStore.lastError.message}</p>
  {/if}
  {#if $managedRuntimeStore.lastError && $managedRuntimeStore.lastError.code !== 'invalid_payload'}
    <p class="error" role="status">{$managedRuntimeStore.lastError.message}</p>
  {/if}

  {#if confirmation}
    <div class="confirmation" role="alertdialog" aria-modal="true" aria-labelledby="models-confirmation-title">
      <h4 id="models-confirmation-title">{$t('models.remove_confirm_title')}</h4>
      <p>{$t('models.remove_confirm_detail')}</p>
      <ul>
        {#each confirmation.artifacts as artifact}
          <li>{artifact.display_name} · {formatBytes(artifact.expected_bytes)} · {artifact.license_id ?? $t('models.license_unknown')} · {artifact.source_identity}</li>
        {/each}
      </ul>
      <div class="confirmation-actions">
        <button type="button" onclick={() => (confirmation = null)}>{$t('models.cancel')}</button>
        <button type="button" class="danger primary" onclick={() => void confirm()}>{$t('models.confirm')}</button>
      </div>
    </div>
  {/if}
</section>

<style>
  .models-section { display: grid; gap: var(--lc-space-3); }
  .section-heading, .artifact-heading, .confirmation-actions { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--lc-space-2); }
  .section-heading p, .hint { margin: var(--lc-space-1) 0 0; color: var(--lc-muted); font-size: 11px; line-height: 1.45; }
  .artifact-card, .confirmation { display: grid; gap: var(--lc-space-2); border: var(--border-thin); border-radius: var(--lc-radius-sm); padding: var(--lc-space-3); background: var(--lc-panel-soft); }
  .artifact-kind { display: block; color: var(--lc-muted); font-size: 10px; font-weight: 760; letter-spacing: .05em; text-transform: uppercase; }
  strong { font-size: 12px; overflow-wrap: anywhere; }
  dl { display: grid; gap: var(--lc-space-1); margin: 0; }
  dl div { display: flex; justify-content: space-between; gap: var(--lc-space-2); font-size: 11px; }
  .runtime-variants { padding-top: var(--lc-space-2); border-top: var(--border-thin); }
  dt { color: var(--lc-muted); }
  dd { margin: 0; text-align: right; overflow-wrap: anywhere; }
  .actions { display: flex; flex-wrap: wrap; gap: var(--lc-space-2); }
  button { min-height: 34px; border: var(--border-thin); border-radius: var(--lc-radius-sm); padding: 0 var(--lc-space-3); background: var(--lc-panel-solid); color: var(--lc-text); font-size: 12px; font-weight: 760; cursor: pointer; }
  button:disabled { color: var(--lc-faint); cursor: not-allowed; }
  .primary { border-color: var(--lc-accent); background: var(--lc-accent); color: #071009; }
  .danger { color: var(--lc-danger); }
  .error { margin: 0; color: var(--lc-danger); font-size: 11px; }
  .confirmation { background: var(--lc-bg-elevated); box-shadow: var(--lc-shadow); }
  .confirmation h4, .confirmation p { margin: 0; }
  .confirmation ul { display: grid; gap: var(--lc-space-1); margin: 0; padding-left: 18px; font-size: 11px; overflow-wrap: anywhere; }
  .refresh { min-height: 30px; padding-inline: var(--lc-space-2); color: var(--lc-muted); }
  .catalog-card { display: grid; gap: var(--lc-space-2); border: var(--border-thin); border-radius: var(--lc-radius-sm); padding: var(--lc-space-3); background: var(--lc-panel-soft); }
  .catalog-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--lc-space-2); }
  .catalog-count { color: var(--lc-muted); font-size: 11px; }
  .catalog-list { display: grid; gap: var(--lc-space-2); margin: 0; padding: 0; list-style: none; }
  .catalog-item { display: grid; gap: var(--lc-space-1); padding: var(--lc-space-2); border: var(--border-thin); border-radius: var(--lc-radius-sm); background: var(--lc-panel-solid); }
  .catalog-item.selected { border-color: var(--lc-accent); }
  .catalog-main { display: flex; align-items: center; justify-content: space-between; gap: var(--lc-space-2); }
  .catalog-empty { color: var(--lc-muted); font-size: 12px; }
</style>
