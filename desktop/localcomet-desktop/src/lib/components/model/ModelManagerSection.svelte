<script lang="ts">
  import { onMount } from 'svelte';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
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
  import { t } from '$lib/i18n';
  import type { ApprovedDownloadableArtifact } from '$lib/types/modelGateway';

  type Confirmation =
    | { readonly action: 'setup'; readonly artifacts: readonly ApprovedDownloadableArtifact[] }
    | { readonly action: 'download'; readonly artifacts: readonly ApprovedDownloadableArtifact[] }
    | { readonly action: 'remove'; readonly artifacts: readonly ApprovedDownloadableArtifact[] };

  let confirmation: Confirmation | null = null;
  let actionPending = false;
  let selectedModelId = $managedRuntimeStore.selectedModelId;

  $: runtime = $managedRuntimeStore.runtimeCatalog?.[0] ?? null;
  $: modelArtifacts = ($artifactAcquisitionStore.artifacts.filter((artifact) => artifact.kind === 'model') as ApprovedDownloadableArtifact[]);
  $: selectedModelArtifact = modelArtifacts.find((artifact) => artifact.artifact_id === selectedModelId) ?? null;
  $: model = $managedRuntimeStore.catalog.find((candidate) => candidate.model_id === selectedModelId) ?? null;
  $: runtimeArtifact = $artifactAcquisitionStore.artifacts.find((artifact) => artifact.kind === 'runtime') ?? null;
  $: runtimeInstalled = runtime ? installationState(runtime.runtime_id) === 'valid' : false;
  $: modelInstalled = selectedModelArtifact ? installationState(selectedModelArtifact.artifact_id) === 'valid' : false;
  $: runtimeDownload = runtimeArtifact ? $artifactAcquisitionStore.downloads[runtimeArtifact.artifact_id] ?? null : null;
  $: modelDownload = selectedModelArtifact ? $artifactAcquisitionStore.downloads[selectedModelArtifact.artifact_id] ?? null : null;
  $: activeDownload = [runtimeDownload, modelDownload].find((download) => download && !isTerminal(download)) ?? null;
  $: canRemove = modelInstalled && !activeDownload && !['Ready', 'Starting', 'Validating', 'Stopping'].includes($managedRuntimeStore.status?.state ?? '');

  onMount(() => {
    void initializeArtifactAcquisition();
  });

  function installationState(artifactId: string): string {
    return $managedRuntimeStore.installedArtifacts.find((artifact) => artifact.artifact_id === artifactId)?.installation_status ?? 'not_installed';
  }

  function displayState(state: string): string {
    return $t(`models.state.${state}`);
  }

  function requestSetup(): void {
    const artifacts = [runtimeArtifact, selectedModelArtifact].filter((artifact): artifact is ApprovedDownloadableArtifact => artifact !== null);
    if (artifacts.length === 2) confirmation = { action: 'setup', artifacts };
  }

  function requestDownload(artifact: ApprovedDownloadableArtifact): void {
    confirmation = { action: 'download', artifacts: [artifact] };
  }

  function requestRemoval(artifact: ApprovedDownloadableArtifact): void {
    confirmation = { action: 'remove', artifacts: [artifact] };
  }

  async function confirm(): Promise<void> {
    const selected = confirmation;
    confirmation = null;
    if (!selected) return;
    actionPending = true;
    try {
      if (selected.action === 'setup') {
        await setUpManagedModel(selected.artifacts.find((artifact) => artifact.kind === 'model')!.artifact_id);
      } else if (selected.action === 'download') {
        await downloadApprovedArtifact(selected.artifacts[0].artifact_id);
      } else {
        await removeApprovedManagedModel(selected.artifacts[0].artifact_id);
      }
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

  function formatBytes(value: number): string {
    return `${(value / 1024 / 1024).toFixed(value >= 1024 * 1024 * 1024 ? 0 : 1)} MiB`;
  }

  function totalBytes(artifacts: readonly ApprovedDownloadableArtifact[]): number {
    return artifacts.reduce((total, artifact) => total + artifact.expected_bytes, 0);
  }

  function modelStatus(artifact: ApprovedDownloadableArtifact): string {
    const state = installationState(artifact.artifact_id);
    if (state === 'valid') return $t('models.state.valid');
    if (state === 'not_installed') return $t('models.state.not_installed');
    return displayState(state);
  }

  function modelTone(artifact: ApprovedDownloadableArtifact): string {
    return installationState(artifact.artifact_id) === 'valid' ? 'ready' : 'disabled';
  }
</script>

<section class="models-section" aria-labelledby="settings-models">
  <div class="section-heading">
    <div>
      <h3 id="settings-models">{$t('models.title')}</h3>
      <p>{$t('models.boundary')}</p>
    </div>
    <button type="button" class="refresh" disabled={$acquisitionBusy} onclick={() => void refreshManagedRuntimeStatus()}>
      {$t('models.refresh')}
    </button>
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
          <option value={artifact.artifact_id}>{artifact.display_name} · {artifact.license_id} · {formatBytes(artifact.expected_bytes)}</option>
        {/each}
      </select>
    </label>
    <dl>
      <div><dt>{$t('models.model_id')}</dt><dd>{selectedModelArtifact?.artifact_id ?? '—'}</dd></div>
      <div><dt>{$t('models.format')}</dt><dd>{selectedModelArtifact ? `${selectedModelArtifact.format ?? '—'} · ${selectedModelArtifact.quantization ?? '—'}` : '—'}</dd></div>
      <div><dt>{$t('models.license')}</dt><dd>{selectedModelArtifact?.license_id ?? '—'}</dd></div>
      <div><dt>{$t('models.size')}</dt><dd>{selectedModelArtifact ? formatBytes(selectedModelArtifact.expected_bytes) : '—'}</dd></div>
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
      <span class="catalog-count">{modelArtifacts.length} {$t('models.approved_catalog_count')}</span>
    </div>
    <ul class="catalog-list">
      {#each modelArtifacts as artifact}
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
    <div class="progress-panel" role="status">
      <strong>{$t('models.current_download')}</strong>
      <span>{activeDownload.received_bytes.toLocaleString()} / {activeDownload.expected_bytes.toLocaleString()} {$t('models.bytes')}</span>
      <progress max="100" value={activeDownload.percent ?? 0}>{activeDownload.percent ?? 0}%</progress>
      <span>{displayState(activeDownload.lifecycle)}</span>
      <button type="button" class="danger" onclick={() => void cancelApprovedArtifactDownload(activeDownload.artifact_id)}>{$t('models.cancel')}</button>
    </div>
  {/if}
  {#if $artifactAcquisitionStore.setup.lifecycle === 'running' && !activeDownload}
    <div class="progress-panel" role="status">
      <strong>{$t('models.setup_progress')}</strong>
      <span>{$t('models.connecting')}</span>
    </div>
  {/if}
  {#if $managedConnectionBusy}
    <div class="progress-panel" role="status">
      <strong>{$t('models.connecting')}</strong>
      <span>{$t('chat.model_loading_detail')}</span>
    </div>
  {/if}

  <div class="actions" aria-label={$t('models.actions')}>
    {#if (!runtimeInstalled || !modelInstalled) && !activeDownload}
      <button type="button" class="primary" disabled={actionPending} onclick={requestSetup}>{$t('models.setup')}</button>
    {/if}
    {#if runtimeArtifact && !runtimeInstalled && !activeDownload}
      <button type="button" disabled={actionPending} onclick={() => requestDownload(runtimeArtifact)}><span>{runtimeDownload?.lifecycle === 'failed' || runtimeDownload?.lifecycle === 'cancelled' ? $t('models.retry_engine') : $t('models.install_engine')}</span></button>
    {/if}
    {#if selectedModelArtifact && !modelInstalled && !activeDownload}
      <button type="button" disabled={actionPending} onclick={() => requestDownload(selectedModelArtifact)}><span>{modelDownload?.lifecycle === 'failed' || modelDownload?.lifecycle === 'cancelled' ? $t('models.retry_model') : $t('models.download_model')}</span></button>
    {/if}
    {#if runtimeInstalled && modelInstalled && !$managedModelReady && !activeDownload}
      <button type="button" class="primary" disabled={actionPending} onclick={() => void connect()}>{$t('models.connect')}</button>
    {/if}
    {#if $managedRuntimeStore.status?.state === 'Ready'}
      <button type="button" disabled={actionPending} onclick={() => void stopSelectedManagedRuntime()}>{$t('models.disconnect')}</button>
    {/if}
    {#if selectedModelArtifact && modelInstalled && !activeDownload}
      <button type="button" class="danger" disabled={!canRemove || actionPending} onclick={() => requestRemoval(selectedModelArtifact)}>{$t('models.remove_model')}</button>
    {/if}
  </div>
  {#if modelInstalled && !canRemove && !activeDownload}
    <p class="hint">{$t('models.remove_hint')}</p>
  {/if}
  {#if $artifactAcquisitionStore.lastError}
    <p class="error" role="status">{$t('models.download_error')}</p>
  {/if}
  {#if $managedRuntimeStore.lastError}
    <p class="error" role="status">{$managedRuntimeStore.lastError.message}</p>
  {/if}

  {#if confirmation}
    <div class="confirmation" role="alertdialog" aria-modal="true" aria-labelledby="models-confirmation-title">
      <h4 id="models-confirmation-title">{confirmation.action === 'remove' ? $t('models.remove_confirm_title') : $t('models.confirm_title')}</h4>
      <p>{confirmation.action === 'remove' ? $t('models.remove_confirm_detail') : $t('models.confirm_detail')}</p>
      <ul>
        {#each confirmation.artifacts as artifact}
          <li>{artifact.display_name} · {formatBytes(artifact.expected_bytes)} · {artifact.license_id} · {artifact.source_identity}</li>
        {/each}
      </ul>
      {#if confirmation.action !== 'remove'}
        <p>{$t('models.combined_size')}: {formatBytes(totalBytes(confirmation.artifacts))}</p>
        <p>{$t('models.confirm_boundary')}</p>
      {/if}
      <div class="confirmation-actions">
        <button type="button" onclick={() => (confirmation = null)}>{$t('models.cancel')}</button>
        <button type="button" class:danger={confirmation.action === 'remove'} class="primary" onclick={() => void confirm()}>{$t('models.confirm')}</button>
      </div>
    </div>
  {/if}
</section>

<style>
  .models-section { display: grid; gap: var(--lc-space-3); }
  .section-heading, .artifact-heading, .confirmation-actions { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--lc-space-2); }
  .section-heading p, .hint { margin: var(--lc-space-1) 0 0; color: var(--lc-muted); font-size: 11px; line-height: 1.45; }
  .artifact-card, .progress-panel, .confirmation { display: grid; gap: var(--lc-space-2); border: var(--border-thin); border-radius: var(--lc-radius-sm); padding: var(--lc-space-3); background: var(--lc-panel-soft); }
  .artifact-kind { display: block; color: var(--lc-muted); font-size: 10px; font-weight: 760; letter-spacing: .05em; text-transform: uppercase; }
  strong { font-size: 12px; overflow-wrap: anywhere; }
  dl { display: grid; gap: var(--lc-space-1); margin: 0; }
  dl div { display: flex; justify-content: space-between; gap: var(--lc-space-2); font-size: 11px; }
  dt { color: var(--lc-muted); }
  dd { margin: 0; text-align: right; overflow-wrap: anywhere; }
  .actions { display: flex; flex-wrap: wrap; gap: var(--lc-space-2); }
  button { min-height: 34px; border: var(--border-thin); border-radius: var(--lc-radius-sm); padding: 0 var(--lc-space-3); background: var(--lc-panel-solid); color: var(--lc-text); font-size: 12px; font-weight: 760; cursor: pointer; }
  button:disabled { color: var(--lc-faint); cursor: not-allowed; }
  .primary { border-color: var(--lc-accent); background: var(--lc-accent); color: #071009; }
  .danger { color: var(--lc-danger); }
  .progress-panel { font-size: 11px; }
  progress { width: 100%; accent-color: var(--lc-accent); }
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
