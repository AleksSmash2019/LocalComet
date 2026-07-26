# Полный исходный код (продолжение)

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/model/ModelGatewayPanel.svelte (233 строк, 7004 байт)

````svelte
<script lang="ts">
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import TelemetryRow from '$lib/components/common/TelemetryRow.svelte';
  import {
    cancelLocalModelTurn,
    confirmBinding,
    discoverModels,
    modelGatewayStore,
    probeGateway,
    setGatewayHarness,
    setGatewayPortText,
    setSelectedModel,
    startLocalModelTurn
  } from '$lib/stores/modelGateway';
  import type { HarnessId } from '$lib/types/modelGateway';

  let prompt = '';
  $: portValid = /^\d+$/.test($modelGatewayStore.portText) && Number($modelGatewayStore.portText) >= 1024 && Number($modelGatewayStore.portText) <= 65535;
  $: canBind = portValid && Boolean($modelGatewayStore.selectedModelId);
  $: canStart = Boolean($modelGatewayStore.binding) && Boolean(prompt.trim()) && $modelGatewayStore.status !== 'Generating' && $modelGatewayStore.status !== 'Cancelling';
  $: canCancel = $modelGatewayStore.status === 'Generating' || $modelGatewayStore.status === 'Cancelling';
  $: statusTone =
    $modelGatewayStore.status === 'Bound' || $modelGatewayStore.status === 'Ready' || $modelGatewayStore.status === 'Completed'
      ? 'ready'
      : $modelGatewayStore.status === 'Failed' || $modelGatewayStore.status === 'Unavailable'
        ? 'danger'
        : $modelGatewayStore.status === 'Generating' || $modelGatewayStore.status === 'Probing' || $modelGatewayStore.status === 'Cancelling'
          ? 'info'
          : 'disabled';

  function onHarnessChange(event: Event) {
    const target = event.currentTarget as HTMLSelectElement;
    setGatewayHarness(target.value as HarnessId);
  }
</script>

<section class="model-panel card-surface" aria-label="External local server">
  <header class="model-panel-header">
    <div>
      <p class="eyebrow">External local server</p>
      <h2>OpenAI-compatible local</h2>
    </div>
    <StatusBadge label={$modelGatewayStore.status} tone={statusTone} />
  </header>

  <div class="gateway-grid">
    <TelemetryRow label="Provider" value="openai-compatible-local" mono />
    <TelemetryRow label="Host" value="127.0.0.1" mono />
    <TelemetryRow label="Tools Executed" value={$modelGatewayStore.toolsExecuted} tone="disabled" mono />
    <TelemetryRow label="Persistence" value={$modelGatewayStore.persistence} tone="disabled" />
  </div>

  <div class="gateway-controls" aria-label="Gateway controls">
    <label>
      <span>Port</span>
      <input
        inputmode="numeric"
        pattern="[0-9]*"
        maxlength="5"
        value={$modelGatewayStore.portText}
        aria-invalid={!portValid}
        oninput={(event) => setGatewayPortText((event.currentTarget as HTMLInputElement).value)}
      />
    </label>
    <button type="button" disabled={!portValid || $modelGatewayStore.status === 'Probing'} onclick={() => void probeGateway()}>Probe</button>
    <button type="button" disabled={!portValid || $modelGatewayStore.status === 'Probing'} onclick={() => void discoverModels()}>List Models</button>
  </div>

  <div class="gateway-controls" aria-label="Binding controls">
    <label>
      <span>Model</span>
      <select value={$modelGatewayStore.selectedModelId} onchange={(event) => setSelectedModel((event.currentTarget as HTMLSelectElement).value)}>
        <option value="">Select discovered model</option>
        {#each $modelGatewayStore.models as model}
          <option value={model.model_id}>{model.model_id}</option>
        {/each}
      </select>
    </label>
    <label>
      <span>Harness</span>
      <select value={$modelGatewayStore.harnessId} onchange={onHarnessChange}>
        <option value="minimal">minimal</option>
        <option value="native-localcomet">native-localcomet</option>
      </select>
    </label>
    <button type="button" disabled={!canBind} onclick={() => void confirmBinding()}>Confirm Binding</button>
  </div>

  <div class="fingerprint" aria-label="Binding fingerprint">
    <span>Fingerprint</span>
    <code>{$modelGatewayStore.binding?.binding_fingerprint ?? 'Binding required'}</code>
  </div>

  <label class="prompt-box">
    <span>Prompt</span>
    <textarea
      bind:value={prompt}
      rows="3"
      maxlength="12000"
      disabled={!$modelGatewayStore.binding || canCancel}
      placeholder={$modelGatewayStore.binding ? 'Send one text-only local prompt...' : 'Confirm a binding before starting a real turn'}
    ></textarea>
  </label>

  <div class="turn-actions">
    <button type="button" disabled={!canStart} onclick={() => void startLocalModelTurn(prompt)}>Start</button>
    <button type="button" disabled={!canCancel} onclick={() => void cancelLocalModelTurn()}>Cancel</button>
    <StatusBadge label={$modelGatewayStore.modelCalled ? 'Model Called: Yes' : 'Model Called: No'} tone={$modelGatewayStore.modelCalled ? 'ready' : 'disabled'} />
  </div>

  {#if $modelGatewayStore.generatedText}
    <pre class="generated" aria-label="Generated local model text">{$modelGatewayStore.generatedText}</pre>
  {/if}
  {#if $modelGatewayStore.lastError}
    <p class="gateway-error" role="status">{$modelGatewayStore.lastError.message}</p>
  {/if}
</section>

<style>
  .model-panel {
    display: grid;
    gap: 14px;
    padding: 16px;
    border-color: var(--lc-border-strong);
  }

  .model-panel-header,
  .gateway-controls,
  .turn-actions {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .model-panel-header {
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

  .gateway-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  label {
    display: grid;
    gap: 5px;
    min-width: 150px;
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 700;
  }

  input,
  select,
  textarea {
    min-height: 36px;
    border: 1px solid var(--lc-border);
    border-radius: 6px;
    background: var(--lc-panel-soft);
    color: var(--lc-text);
    font: inherit;
    padding: 8px 10px;
  }

  textarea {
    resize: vertical;
    min-height: 76px;
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
  .generated {
    overflow-wrap: anywhere;
    font-family: var(--lc-mono);
  }

  .generated {
    max-height: 180px;
    margin: 0;
    overflow: auto;
    white-space: pre-wrap;
    border: 1px solid var(--lc-border);
    border-radius: 6px;
    background: var(--lc-panel-soft);
    color: var(--lc-text);
    padding: 12px;
  }

  .gateway-error {
    margin: 0;
    color: var(--lc-danger);
    font-weight: 700;
  }

  @media (max-width: 720px) {
    .gateway-grid {
      grid-template-columns: 1fr;
    }

    label,
    .gateway-controls button {
      width: 100%;
    }
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/model/ModelManagerSection.svelte (256 строк, 13148 байт)

````svelte
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

  $: runtime = $managedRuntimeStore.runtimeCatalog[0] ?? null;
  $: model = $managedRuntimeStore.catalog[0] ?? null;
  $: runtimeArtifact = $artifactAcquisitionStore.artifacts.find((artifact) => artifact.kind === 'runtime') ?? null;
  $: modelArtifact = $artifactAcquisitionStore.artifacts.find((artifact) => artifact.kind === 'model') ?? null;
  $: runtimeInstalled = runtime ? installationState(runtime.runtime_id) === 'valid' : false;
  $: modelInstalled = model ? installationState(model.model_id) === 'valid' : false;
  $: runtimeDownload = runtimeArtifact ? $artifactAcquisitionStore.downloads[runtimeArtifact.artifact_id] ?? null : null;
  $: modelDownload = modelArtifact ? $artifactAcquisitionStore.downloads[modelArtifact.artifact_id] ?? null : null;
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
    const artifacts = [runtimeArtifact, modelArtifact].filter((artifact): artifact is ApprovedDownloadableArtifact => artifact !== null);
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
        await setUpLocalAi();
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
    if (!model) return;
    actionPending = true;
    try {
      await setManagedSelectedModel(model.model_id);
      await connectSelectedManagedModel();
    } finally {
      actionPending = false;
    }
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
        <strong>{model?.display_name ?? $t('models.not_available')}</strong>
      </div>
      <StatusBadge label={displayState(modelInstalled ? 'valid' : installationState(model?.model_id ?? ''))} tone={modelInstalled ? 'ready' : 'disabled'} />
    </div>
    <dl>
      <div><dt>{$t('models.model_id')}</dt><dd>{model?.model_id ?? '—'}</dd></div>
      <div><dt>{$t('models.format')}</dt><dd>{model ? `${model.format} · ${model.quantization}` : '—'}</dd></div>
      <div><dt>{$t('models.license')}</dt><dd>{model?.license_id ?? '—'}</dd></div>
      <div><dt>{$t('models.size')}</dt><dd>{modelArtifact ? formatBytes(modelArtifact.expected_bytes) : '—'}</dd></div>
      <div><dt>{$t('models.connection')}</dt><dd>{$managedModelReady ? $t('models.connected') : $t('models.not_connected')}</dd></div>
      {#if modelDownload}
        <div><dt>{$t('models.download')}</dt><dd>{displayState(modelDownload.lifecycle)} {modelDownload.percent === null ? '' : `${modelDownload.percent}%`}</dd></div>
      {/if}
    </dl>
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
    {#if modelArtifact && !modelInstalled && !activeDownload}
      <button type="button" disabled={actionPending} onclick={() => requestDownload(modelArtifact)}><span>{modelDownload?.lifecycle === 'failed' || modelDownload?.lifecycle === 'cancelled' ? $t('models.retry_model') : $t('models.download_model')}</span></button>
    {/if}
    {#if runtimeInstalled && modelInstalled && !$managedModelReady && !activeDownload}
      <button type="button" class="primary" disabled={actionPending} onclick={() => void connect()}>{$t('models.connect')}</button>
    {/if}
    {#if $managedRuntimeStore.status?.state === 'Ready'}
      <button type="button" disabled={actionPending} onclick={() => void stopSelectedManagedRuntime()}>{$t('models.disconnect')}</button>
    {/if}
    {#if modelArtifact && modelInstalled && !activeDownload}
      <button type="button" class="danger" disabled={!canRemove || actionPending} onclick={() => requestRemoval(modelArtifact)}>{$t('models.remove_model')}</button>
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
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/model/ModelSetupDrawer.svelte (643 строк, 19826 байт)

````svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import {
    confirmBinding,
    connectSelectedManagedModel,
    discoverModels,
    inferenceBusy,
    managedConnectionBusy,
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
  import { closeModelSetup, modelSetupDrawerOpen, modelSetupMode } from '$lib/stores/shellStore';
  import type { HarnessId } from '$lib/types/modelGateway';
  import { t } from '$lib/i18n';

  export let onClose: () => void = () => {};

  let portInput = '';
  $: portValid = /^\d+$/.test(portInput) && Number(portInput) >= 1024 && Number(portInput) <= 65535;

  // External flow state
  $: canBindExternal = !$inferenceBusy && portValid && Boolean($modelGatewayStore.selectedModelId);
  $: externalStep = !$modelGatewayStore.catalog ? 0 : portValid ? 1 : $modelGatewayStore.models.length ? 2 : 3;

  // Managed flow state
  $: managedState = $managedRuntimeStore.status?.state ?? 'NotInstalled';
  $: managedSelectedModel = $managedRuntimeStore.catalog.find((m) => m.model_id === $managedRuntimeStore.selectedModelId);
  $: managedModelLaunchable = $managedRuntimeStore.readiness?.model_id === managedSelectedModel?.model_id && $managedRuntimeStore.readiness?.launchable === true;
  $: canStartManaged = !$inferenceBusy && !$managedConnectionBusy && Boolean(managedSelectedModel) && managedModelLaunchable && (managedState === 'Stopped' || managedState === 'Failed');
  $: canStopManaged = !$inferenceBusy && !$managedConnectionBusy && (managedState === 'Ready' || managedState === 'Starting' || managedState === 'Validating' || managedState === 'Failed');
  $: canBindManaged = !$inferenceBusy && !$managedConnectionBusy && managedModelLaunchable && ['Stopped', 'Failed', 'Ready'].includes(managedState) && Boolean($managedRuntimeStore.selectedModelId);
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
  }

  async function onStartManaged() {
    await startSelectedManagedRuntime();
  }

  async function onStopManaged() {
    await stopSelectedManagedRuntime();
  }

  async function onConfirmManagedBinding() {
    const connected = await connectSelectedManagedModel();
    if (connected) {
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
              disabled={$inferenceBusy}
              aria-invalid={!portValid}
              placeholder="1234"
            />
          </label>

          <div class="action-row">
            <button type="button" disabled={$inferenceBusy || !portValid || $modelGatewayStore.status === 'Probing'} onclick={onProbe}>
              <Icon name="refresh" size={16} />
              <span>{$t('setup.check_server')}</span>
            </button>
            <button type="button" disabled={$inferenceBusy || !portValid || $modelGatewayStore.status === 'Probing'} onclick={onDiscover}>
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
            <select disabled={$inferenceBusy} value={$modelGatewayStore.selectedModelId} onchange={(e) => setSelectedModel((e.currentTarget as HTMLSelectElement).value)}>
              <option value="">{$t('setup.select_model')}</option>
              {#each $modelGatewayStore.models as model}
                <option value={model.model_id}>{model.model_id}</option>
              {/each}
            </select>
          </label>

          <label class="form-field">
            <span>{$t('setup.response_mode')}</span>
            <select disabled={$inferenceBusy} value={$modelGatewayStore.harnessId} onchange={onExternalHarnessChange}>
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
            <p class="field-hint">{$t('setup.external_diagnostics_only')}</p>
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
              <span class="status-value">{$managedRuntimeStore.status?.inference_ready && $managedRuntimeStore.status?.model_state === 'Ready' ? $t('setup.connected') : $t('setup.needs_binding')}</span>
            </div>
          </div>

          {#if managedState === 'NotInstalled'}
            <div class="empty-state">
              <p class="empty-title">{$t('setup.runtime_not_installed')}</p>
              <p class="empty-desc">{$t('setup.install_available')}</p>
            </div>
          {:else}
            <div class="action-row">
              <button type="button" disabled={$inferenceBusy} onclick={onRefreshManaged}>
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
              <select disabled={$inferenceBusy} value={$managedRuntimeStore.selectedModelId} onchange={(e) => void setManagedSelectedModel((e.currentTarget as HTMLSelectElement).value)}>
                <option value="">{$t('setup.select_local_model')}</option>
                {#each $managedRuntimeStore.catalog as model}
                  <option value={model.model_id}>{model.display_name} ({Math.round(model.asset_bytes / 1024 / 1024)} MiB)</option>
                {/each}
              </select>
            </label>

            <label class="form-field">
              <span>{$t('setup.response_mode')}</span>
              <select disabled={$inferenceBusy} value={$managedRuntimeStore.harnessId} onchange={onManagedHarnessChange}>
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
              <span>{$t($managedConnectionBusy ? 'chat.model_connecting' : 'setup.connect')}</span>
            </button>

            {#if $managedConnectionBusy}
              <p class="connection-progress" role="status">{$t('chat.model_loading_detail')}</p>
            {/if}

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

  .connection-progress {
    margin: 0;
    color: var(--lc-muted);
    font-size: 12px;
    line-height: 1.5;
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
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/onboarding/OnboardingScreen.svelte (88 строк, 6425 байт)

````svelte
<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import LocalCometLogo from '$lib/components/common/LocalCometLogo.svelte';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import { t } from '$lib/i18n';
  import { artifactAcquisitionStore } from '$lib/stores/artifactAcquisition';
  import { controlPlaneStore } from '$lib/stores/controlPlane';
  import { managedModelReady, managedRuntimeStore } from '$lib/stores/modelGateway';
  import { openSettings, setActiveWorkspace } from '$lib/stores/shellStore';

  $: controlReady = $controlPlaneStore.bridgeState === 'READY';
  $: sidecarReady = $controlPlaneStore.bootstrap?.sidecar_ready === true;
  $: catalogReady = $managedRuntimeStore.catalogIdentity !== null && $artifactAcquisitionStore.artifacts.length > 0;
  $: runtimeInstalled = $managedRuntimeStore.installedArtifacts.some(
    (artifact) => artifact.kind === 'runtime' && artifact.installation_status === 'valid'
  );
  $: modelInstalled = $managedRuntimeStore.installedArtifacts.some(
    (artifact) => artifact.kind === 'model' && artifact.installation_status === 'valid'
  );

  function tone(ready: boolean, pending = false): string {
    if (ready) return 'ready';
    return pending ? 'info' : 'unknown';
  }
</script>

<main id="setup-workspace" class="onboarding" aria-labelledby="onboarding-title">
  <div class="onboarding-card">
    <div class="mark"><LocalCometLogo size={58} /></div>
    <span class="eyebrow">{$t('onboarding.eyebrow')}</span>
    <h1 id="onboarding-title">{$t('onboarding.title')}</h1>
    <p class="lead">{$t('onboarding.subtitle')}</p>
    <div class="privacy"><Icon name="shield" size={16} /> {$t('onboarding.local_boundary')}</div>

    <section aria-labelledby="environment-title">
      <div class="section-heading">
        <div>
          <span class="step">01</span>
          <h2 id="environment-title">{$t('onboarding.environment')}</h2>
        </div>
        <button type="button" class="refresh" onclick={() => openSettings('models')}>{$t('onboarding.manage')}</button>
      </div>
      <div class="checks">
        <div><span>{$t('onboarding.control_plane')}</span><StatusBadge label={$t(controlReady ? 'common.ready' : 'common.not_determined')} tone={tone(controlReady, $controlPlaneStore.bridgeState === 'CONNECTING')} /></div>
        <div><span>{$t('onboarding.sidecar')}</span><StatusBadge label={$t(sidecarReady ? 'common.ready' : 'common.not_determined')} tone={tone(sidecarReady, $controlPlaneStore.bridgeState === 'CONNECTING')} /></div>
        <div><span>{$t('onboarding.catalog')}</span><StatusBadge label={$t(catalogReady ? 'common.verified' : 'common.not_determined')} tone={tone(catalogReady)} /></div>
        <div><span>{$t('onboarding.runtime')}</span><StatusBadge label={$t(runtimeInstalled ? 'common.verified' : 'onboarding.not_installed')} tone={runtimeInstalled ? 'ready' : 'disabled'} /></div>
        <div><span>{$t('onboarding.model')}</span><StatusBadge label={$t(modelInstalled ? 'common.verified' : 'onboarding.not_installed')} tone={modelInstalled ? 'ready' : 'disabled'} /></div>
        <div><span>{$t('onboarding.inference')}</span><StatusBadge label={$t($managedModelReady ? 'common.ready' : 'onboarding.not_connected')} tone={$managedModelReady ? 'ready' : 'disabled'} /></div>
      </div>
    </section>

    <div class="actions">
      <button type="button" class="primary" onclick={() => openSettings('models')}>
        <Icon name="model" size={18} />
        {$t('onboarding.open_models')}
      </button>
      <button type="button" onclick={() => setActiveWorkspace('chat')}>{$t('onboarding.continue_chat')}</button>
    </div>
    <p class="boundary">{$t('onboarding.boundary')}</p>
  </div>
</main>

<style>
  .onboarding { min-width: 0; min-height: 0; overflow-y: auto; padding: clamp(20px, 5vw, 56px); background: radial-gradient(circle at 50% 0%, var(--lc-accent-dim), transparent 42%); }
  .onboarding-card { width: min(100%, 720px); display: grid; justify-items: center; gap: var(--lc-space-3); margin: 0 auto; }
  .mark { display: grid; place-items: center; width: 88px; height: 88px; border: var(--border-thin); border-radius: 24px; background: var(--lc-panel); box-shadow: var(--lc-shadow); }
  .eyebrow, .step { color: var(--lc-accent); font-family: var(--lc-mono); font-size: 11px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
  h1, h2, p { margin: 0; }
  h1 { font-size: clamp(25px, 4vw, 34px); letter-spacing: -.04em; text-align: center; }
  .lead { max-width: 600px; color: var(--lc-muted); line-height: 1.6; text-align: center; }
  .privacy { display: inline-flex; align-items: center; gap: var(--lc-space-2); color: var(--lc-accent); font-size: 12px; font-weight: 760; }
  section { width: 100%; display: grid; gap: var(--lc-space-3); margin-top: var(--lc-space-4); border: var(--border-thin); border-radius: var(--lc-radius-lg); padding: clamp(16px, 3vw, 24px); background: var(--lc-panel-solid); }
  .section-heading, .section-heading > div, .checks > div, .actions { display: flex; align-items: center; }
  .section-heading { justify-content: space-between; gap: var(--lc-space-3); }
  .section-heading > div { gap: var(--lc-space-2); }
  h2 { font-size: 16px; }
  button { border: var(--border-thin); border-radius: var(--lc-radius-sm); padding: 0 var(--lc-space-3); background: var(--lc-panel-soft); cursor: pointer; }
  button:hover { border-color: var(--lc-line-strong); }
  .refresh { min-height: 34px; color: var(--lc-muted); font-size: 12px; }
  .checks { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--lc-space-2); }
  .checks > div { min-width: 0; justify-content: space-between; gap: var(--lc-space-2); border: var(--border-thin); border-radius: var(--lc-radius-sm); padding: var(--lc-space-3); background: var(--lc-panel-soft); font-size: 12px; font-weight: 700; }
  .actions { flex-wrap: wrap; justify-content: center; gap: var(--lc-space-2); }
  .actions button { display: inline-flex; align-items: center; gap: var(--lc-space-2); }
  .primary { border-color: var(--lc-accent); background: var(--lc-accent); color: #071009; font-weight: 800; }
  .boundary { max-width: 620px; color: var(--lc-faint); font-size: 11px; line-height: 1.5; text-align: center; }
  @media (max-width: 620px) { .checks { grid-template-columns: 1fr; } .section-heading { align-items: flex-start; } }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/review/DecisionConfirmationDialog.svelte (409 строк, 10452 байт)

````svelte
<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';
  import { t } from '$lib/i18n';
  import { cycleDialogFocusIndex } from '$lib/stores/reviewCenter';
  import type { DecisionIntent, ReviewCenterItem } from '$lib/types/knowledgeReview';

  export let review: ReviewCenterItem;
  export let intent: DecisionIntent;
  export let comment: string;
  export let actorIdentifier = '';
  export let actorDisplayName = '';
  export let submitting = false;
  export let errorKey: string | null = null;
  export let triggerElement: HTMLElement | null = null;
  export let onClose: () => void = () => {};
  export let onComment: (value: string) => void = () => {};
  export let onActorIdentifier: (value: string) => void = () => {};
  export let onActorDisplayName: (value: string) => void = () => {};
  export let onConfirm: () => void | Promise<void> = () => {};

  let dialogElement: HTMLDivElement;
  let previousFocus: HTMLElement | null = null;

  const focusableSelector = [
    'button:not([disabled])',
    'textarea:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    '[href]',
    '[tabindex]:not([tabindex="-1"])'
  ].join(',');

  onMount(() => {
    previousFocus =
      triggerElement ??
      (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    void tick().then(() => {
      dialogElement?.querySelectorAll<HTMLElement>(focusableSelector)?.[0]?.focus();
    });
  });

  onDestroy(() => {
    (triggerElement ?? previousFocus)?.focus();
  });

  function handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      if (submitting) return;
      event.preventDefault();
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== 'Tab') return;

    const focusable = Array.from(
      dialogElement.querySelectorAll<HTMLElement>(focusableSelector)
    );
    if (focusable.length === 0) {
      event.preventDefault();
      dialogElement.focus();
      return;
    }
    const currentIndex = focusable.indexOf(document.activeElement as HTMLElement);
    const nextIndex = cycleDialogFocusIndex(currentIndex, focusable.length, event.shiftKey);
    event.preventDefault();
    focusable[nextIndex]?.focus();
  }

  function handleBackdropClick(event: MouseEvent): void {
    if (!submitting && event.target === event.currentTarget) onClose();
  }

  function submit(event: SubmitEvent): void {
    event.preventDefault();
    if (!submitting) void onConfirm();
  }

  $: intentKey = `review.decision.${intent.toLowerCase()}`;
  $: exactChange = review.changeIdentity ?? $t('review.none');
</script>

<div
  class="dialog-backdrop"
  role="presentation"
  onclick={handleBackdropClick}
  onkeydown={handleKeydown}
>
  <div
    bind:this={dialogElement}
    class="decision-dialog"
    role="dialog"
    aria-modal="true"
    aria-labelledby="review-decision-dialog-title"
    aria-describedby="review-decision-dialog-description"
    aria-busy={submitting}
    tabindex="-1"
  >
    <form onsubmit={submit}>
      <header>
        <p class="dialog-eyebrow">
          {review.fixture
            ? $t('review.decision.fixture_only')
            : $t('review.decision.real_e9c')}
        </p>
        <h2 id="review-decision-dialog-title">{$t('review.decision.dialog_title')}</h2>
        <p id="review-decision-dialog-description">
          {review.fixture
            ? $t('review.decision.dialog_description_fixture')
            : $t('review.decision.dialog_description_real')}
        </p>
      </header>

      <dl class="binding-grid">
        <div>
          <dt>{$t('review.identity.proposal_id')}</dt>
          <dd><code>{review.proposalId}</code></dd>
        </div>
        <div>
          <dt>{$t('review.identity.review_identity')}</dt>
          <dd><code>{review.reviewArtifactIdentity}</code></dd>
        </div>
        <div>
          <dt>{$t('review.identity.change_identity')}</dt>
          <dd><code>{exactChange}</code></dd>
        </div>
        <div>
          <dt>{$t('review.identity.observed_revision')}</dt>
          <dd><code>{review.observedVaultRevision}</code></dd>
        </div>
        <div>
          <dt>{$t('review.decision.intent')}</dt>
          <dd><strong>{$t(intentKey)}</strong></dd>
        </div>
      </dl>

      {#if !review.fixture}
        <div class="actor-grid">
          <label for="review-actor-identifier">
            {$t('review.decision.actor_identifier')}
            <input
              id="review-actor-identifier"
              value={actorIdentifier}
              maxlength="256"
              autocomplete="off"
              disabled={submitting}
              oninput={(event) =>
                onActorIdentifier((event.currentTarget as HTMLInputElement).value)}
            />
          </label>
          <label for="review-actor-display-name">
            {$t('review.decision.actor_display_name')}
            <input
              id="review-actor-display-name"
              value={actorDisplayName}
              maxlength="256"
              autocomplete="off"
              disabled={submitting}
              oninput={(event) =>
                onActorDisplayName((event.currentTarget as HTMLInputElement).value)}
            />
          </label>
        </div>
        <p class="actor-note">{$t('review.decision.actor_evidence_only')}</p>
      {/if}

      <label for="review-decision-comment">
        {$t('review.decision.comment')}
        {#if intent === 'REQUEST_CHANGES'}
          <span class="required">{$t('review.decision.required')}</span>
        {/if}
      </label>
      <textarea
        id="review-decision-comment"
        value={comment}
        maxlength="2000"
        rows="5"
        disabled={submitting}
        aria-invalid={Boolean(errorKey)}
        aria-describedby={errorKey ? 'review-decision-error' : undefined}
        placeholder={$t('review.decision.comment_placeholder')}
        oninput={(event) => onComment((event.currentTarget as HTMLTextAreaElement).value)}
      ></textarea>

      {#if errorKey}
        <p id="review-decision-error" class="dialog-error" role="alert">
          {$t(errorKey)}
        </p>
      {/if}

      <p class="hard-stop-note">
        <strong>{$t('review.decision.hard_stop_title')}</strong>
        {review.fixture
          ? $t('review.decision.hard_stop_detail')
          : $t('review.decision.real_hard_stop_detail')}
      </p>

      <footer>
        <button type="button" class="secondary-button" disabled={submitting} onclick={onClose}>
          {$t('review.decision.cancel')}
        </button>
        <button type="submit" class="primary-button" disabled={submitting}>
          {submitting ? $t('review.decision.submitting') : $t('review.decision.confirm')}
        </button>
      </footer>
    </form>
  </div>
</div>

<style>
  .dialog-backdrop {
    position: fixed;
    inset: 0;
    z-index: 90;
    display: grid;
    place-items: center;
    background: rgba(0, 0, 0, 0.66);
    padding: var(--lc-space-4);
  }

  .decision-dialog {
    width: min(680px, 100%);
    max-height: min(800px, calc(100vh - 32px));
    overflow: auto;
    border: 1px solid var(--lc-line-strong);
    border-radius: var(--lc-radius-lg);
    background: var(--lc-panel-solid);
    box-shadow: var(--lc-shadow);
  }

  form {
    display: grid;
    gap: var(--lc-space-4);
    padding: var(--lc-space-5);
  }

  header {
    display: grid;
    gap: var(--lc-space-2);
  }

  .dialog-eyebrow {
    margin: 0;
    color: var(--lc-info);
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 820;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  h2 {
    margin: 0;
    font-size: 20px;
  }

  header p:last-child,
  .actor-note {
    margin: 0;
    color: var(--lc-muted);
    font-size: 12px;
    line-height: 1.5;
  }

  .binding-grid {
    display: grid;
    gap: var(--lc-space-2);
    margin: 0;
  }

  .binding-grid > div {
    min-width: 0;
    display: grid;
    grid-template-columns: minmax(150px, 0.32fr) minmax(0, 1fr);
    gap: var(--lc-space-3);
    border-top: var(--border-thin);
    padding-top: var(--lc-space-2);
  }

  dt {
    color: var(--lc-muted);
    font-size: 11px;
  }

  dd {
    min-width: 0;
    margin: 0;
    overflow-wrap: anywhere;
    font-size: 11px;
  }

  code {
    font-family: var(--lc-mono);
  }

  .actor-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--lc-space-3);
  }

  label {
    display: grid;
    gap: var(--lc-space-2);
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 700;
  }

  input,
  textarea {
    min-width: 0;
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    background: var(--lc-panel);
    color: var(--lc-text);
    font: inherit;
    padding: var(--lc-space-3);
  }

  input {
    min-height: 44px;
  }

  textarea {
    resize: vertical;
  }

  input:focus-visible,
  textarea:focus-visible,
  button:focus-visible {
    outline: 2px solid var(--lc-accent);
    outline-offset: 2px;
  }

  .required,
  .dialog-error {
    color: var(--lc-danger);
  }

  .dialog-error {
    margin: 0;
    font-size: 12px;
  }

  .hard-stop-note {
    border: 1px solid color-mix(in srgb, var(--lc-warning) 42%, transparent);
    border-radius: var(--lc-radius-md);
    background: color-mix(in srgb, var(--lc-warning) 8%, transparent);
    margin: 0;
    padding: var(--lc-space-3);
    color: var(--lc-muted);
    font-size: 11px;
    line-height: 1.5;
  }

  .hard-stop-note strong {
    display: block;
    margin-bottom: 4px;
    color: var(--lc-warning);
  }

  footer {
    display: flex;
    justify-content: flex-end;
    gap: var(--lc-space-3);
  }

  button {
    min-height: 44px;
    border-radius: var(--lc-radius-md);
    padding: 0 var(--lc-space-4);
    font-weight: 800;
    cursor: pointer;
  }

  button:disabled {
    cursor: wait;
    opacity: 0.56;
  }

  .secondary-button {
    border: var(--border-thin);
    background: var(--lc-panel);
    color: var(--lc-text);
  }

  .primary-button {
    border: 1px solid var(--lc-line-strong);
    background: var(--lc-accent);
    color: var(--lc-bg);
  }

  @media (max-width: 640px) {
    form {
      padding: var(--lc-space-4);
    }

    .binding-grid > div,
    .actor-grid {
      grid-template-columns: 1fr;
    }

    footer {
      display: grid;
      grid-template-columns: 1fr;
    }
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/review/RepresentationDeltaPanel.svelte (177 строк, 4830 байт)

````svelte
<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import { t } from '$lib/i18n';
  import type { LineEndingProfileView, ReviewCenterItem } from '$lib/types/knowledgeReview';

  export let review: ReviewCenterItem;

  function profileText(profile: LineEndingProfileView | null): string {
    if (!profile) return $t('review.representation.absent');
    return `${profile.label} · CRLF ${profile.crlfCount} · LF ${profile.lfCount} · CR ${profile.crCount}`;
  }
</script>

<section class="review-panel" aria-labelledby="review-representation-heading">
  <header class="panel-header">
    <div>
      <p class="panel-eyebrow">{$t('review.representation.eyebrow')}</p>
      <h2 id="review-representation-heading">{$t('review.representation.title')}</h2>
    </div>
    {#if review.representationDelta?.rawTextChangedSemanticEqual}
      <span class="representation-badge">
        <Icon name="audit" size={15} />
        {$t('review.representation.only')}
      </span>
    {/if}
  </header>

  {#if review.representationDelta === null}
    <div class="no-material">
      {$t('review.representation.no_material')}
    </div>
  {:else}
    <dl class="representation-list">
      <div>
        <dt>{$t('review.representation.identity')}</dt>
        <dd><code>{review.representationDelta.identity}</code></dd>
      </div>
      <div>
        <dt>{$t('review.representation.line_endings')}</dt>
        <dd>
          <span>{profileText(review.representationDelta.beforeLineEndings)}</span>
          <span aria-hidden="true">→</span>
          <span>{profileText(review.representationDelta.afterLineEndings)}</span>
        </dd>
      </div>
      <div>
        <dt>{$t('review.representation.terminal_newline')}</dt>
        <dd>
          {review.representationDelta.terminalNewlineChanged ? $t('review.changed') : $t('review.unchanged')}
        </dd>
      </div>
      <div>
        <dt>{$t('review.representation.source_bytes_known')}</dt>
        <dd>{review.representationDelta.afterSourceBytesKnown ? $t('review.yes') : $t('review.no')}</dd>
      </div>
      <div>
        <dt>{$t('review.representation.bytes_same_text')}</dt>
        <dd>{review.representationDelta.sourceBytesChangedTextIdentical ? $t('review.yes') : $t('review.no')}</dd>
      </div>
      <div>
        <dt>{$t('review.representation.raw_semantic_equal')}</dt>
        <dd class:highlight={review.representationDelta.rawTextChangedSemanticEqual}>
          {review.representationDelta.rawTextChangedSemanticEqual ? $t('review.yes') : $t('review.no')}
        </dd>
      </div>
      <div>
        <dt>{$t('review.representation.semantic_changed')}</dt>
        <dd>{review.representationDelta.semanticContentChanged ? $t('review.yes') : $t('review.no')}</dd>
      </div>
    </dl>
  {/if}
</section>

<style>
  .review-panel {
    border: var(--border-thin);
    border-radius: var(--lc-radius-lg);
    background: var(--lc-panel);
    padding: var(--lc-space-4);
  }

  .panel-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--lc-space-3);
    margin-bottom: var(--lc-space-4);
  }

  .panel-eyebrow {
    margin: 0 0 4px;
    color: var(--lc-accent);
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.11em;
    text-transform: uppercase;
  }

  h2 {
    margin: 0;
    font-size: 16px;
  }

  .representation-badge {
    min-height: 28px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border: 1px solid color-mix(in srgb, var(--lc-warning) 42%, transparent);
    border-radius: 999px;
    color: var(--lc-warning);
    padding: 0 9px;
    font-size: 10px;
    font-weight: 800;
  }

  .representation-list {
    display: grid;
    gap: var(--lc-space-2);
    margin: 0;
  }

  .representation-list > div {
    min-width: 0;
    display: grid;
    grid-template-columns: minmax(170px, 0.35fr) minmax(0, 1fr);
    gap: var(--lc-space-3);
    border-top: var(--border-thin);
    padding-top: var(--lc-space-2);
  }

  dt {
    color: var(--lc-muted);
    font-size: 11px;
  }

  dd {
    min-width: 0;
    display: flex;
    flex-wrap: wrap;
    gap: var(--lc-space-2);
    overflow-wrap: anywhere;
    margin: 0;
    color: var(--lc-text);
    font-size: 11px;
  }

  dd.highlight {
    color: var(--lc-warning);
    font-weight: 800;
  }

  code {
    overflow-wrap: anywhere;
    font-family: var(--lc-mono);
    font-size: 10px;
  }

  .no-material {
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    color: var(--lc-muted);
    padding: var(--lc-space-3);
    font-size: 12px;
  }

  @media (max-width: 760px) {
    .representation-list > div {
      grid-template-columns: 1fr;
    }

    .panel-header {
      flex-direction: column;
    }
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/review/ReviewActivityTimeline.svelte (137 строк, 2739 байт)

````svelte
<script lang="ts">
  import { t } from '$lib/i18n';
  import { reviewActivity } from '$lib/stores/reviewCenter';
</script>

<section class="activity review-panel" aria-labelledby="review-activity-title">
  <header>
    <div>
      <p>{$t('review.activity.eyebrow')}</p>
      <h2 id="review-activity-title">{$t('review.activity.title')}</h2>
    </div>
    <span>{$reviewActivity.length}/128</span>
  </header>

  {#if $reviewActivity.length === 0}
    <p class="empty">{$t('review.activity.empty')}</p>
  {:else}
    <ol aria-live="polite">
      {#each [...$reviewActivity].reverse() as event (event.id)}
        <li>
          <span class="sequence">{event.sequence}</span>
          <div>
            <strong>{$t(event.messageKey)}</strong>
            {#if event.reviewArtifactIdentity}
              <code>{event.reviewArtifactIdentity}</code>
            {/if}
            {#if event.errorCode}
              <span class="error-code">{event.errorCode}</span>
            {/if}
          </div>
        </li>
      {/each}
    </ol>
  {/if}

  <p class="boundary">{$t('review.activity.boundary')}</p>
</section>

<style>
  .review-panel {
    border: var(--border-thin);
    border-radius: var(--lc-radius-lg);
    background: var(--lc-panel);
    padding: var(--lc-space-4);
  }

  header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--lc-space-3);
    margin-bottom: var(--lc-space-3);
  }

  header p {
    margin: 0 0 4px;
    color: var(--lc-accent);
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.11em;
    text-transform: uppercase;
  }

  header span {
    color: var(--lc-muted);
    font-family: var(--lc-mono);
    font-size: 11px;
  }

  h2,
  .empty {
    margin: 0;
  }

  h2 {
    font-size: 16px;
  }

  .empty,
  .boundary {
    color: var(--lc-muted);
    font-size: 11px;
    line-height: 1.5;
  }

  ol {
    display: grid;
    gap: var(--lc-space-2);
    max-height: 320px;
    overflow: auto;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    min-width: 0;
    display: grid;
    grid-template-columns: 32px minmax(0, 1fr);
    gap: var(--lc-space-2);
    border-top: var(--border-thin);
    padding-top: var(--lc-space-2);
  }

  .sequence {
    color: var(--lc-accent);
    font-family: var(--lc-mono);
    font-size: 11px;
  }

  li div {
    min-width: 0;
    display: grid;
    gap: 4px;
  }

  strong {
    font-size: 12px;
  }

  code,
  .error-code {
    overflow-wrap: anywhere;
    color: var(--lc-muted);
    font-family: var(--lc-mono);
    font-size: 10px;
  }

  .error-code {
    color: var(--lc-danger);
  }

  .boundary {
    margin: var(--lc-space-3) 0 0;
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/review/ReviewCenterWorkspace.svelte (562 строк, 15040 байт)

````svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import { t } from '$lib/i18n';
  import {
    loadReviewCenter,
    retryReviewCenter,
    reviewQueue,
    reviewCenterState,
    selectedReview,
    selectedReviewId
  } from '$lib/stores/reviewCenter';
  import ReviewActivityTimeline from './ReviewActivityTimeline.svelte';
  import ReviewCommandBar from './ReviewCommandBar.svelte';
  import ReviewDecisionPanel from './ReviewDecisionPanel.svelte';
  import ReviewDiagnosticsPanel from './ReviewDiagnosticsPanel.svelte';
  import ReviewFindingsPanel from './ReviewFindingsPanel.svelte';
  import ReviewIdentityPanel from './ReviewIdentityPanel.svelte';
  import ReviewMetadataPanel from './ReviewMetadataPanel.svelte';
  import ReviewQueueSidebar from './ReviewQueueSidebar.svelte';
  import ReviewTextDiffPanel from './ReviewTextDiffPanel.svelte';
  import ReviewValidationPanel from './ReviewValidationPanel.svelte';
  import RepresentationDeltaPanel from './RepresentationDeltaPanel.svelte';

  $: selectedStatus = $selectedReview?.status ?? null;
  $: selectedQueueItem = $reviewQueue.find((item) => item.id === $selectedReviewId) ?? null;
  $: statusTone =
    selectedStatus === 'CLEAR'
      ? 'ready'
      : selectedStatus === 'BLOCKED'
        ? 'danger'
        : 'waiting';

  $: statusIcon =
    selectedStatus === 'CLEAR'
      ? 'check'
      : selectedStatus === 'BLOCKED'
        ? 'cancel'
        : 'audit';

  onMount(() => {
    void loadReviewCenter();
  });
</script>

<main id="review-workspace" class="review-workspace" aria-label={$t('review.workspace_label')}>
  <ReviewQueueSidebar />

  <article class="review-detail" aria-labelledby="review-center-heading">
    <header class="review-header">
      <div class="review-heading">
        <p class="review-eyebrow">{$t('review.eyebrow')}</p>
        <div class="title-row">
          <span class="title-icon" aria-hidden="true">
            <Icon name={statusIcon} size={22} />
          </span>
          <div>
            <h1 id="review-center-heading">{$t('review.title')}</h1>
            <p>{$t('review.subtitle')}</p>
          </div>
        </div>
      </div>
      <div class="header-status">
        {#if $selectedReview}
          <StatusBadge
            label={$t(`review.status.${$selectedReview.status}`)}
            tone={statusTone}
          />
        {/if}
        <span class="source-marker">
          {#if $selectedReview?.fixture}
            {$t('review.fixture_badge')}: {$selectedReview.fixtureLabel}
          {:else}
            {$t('review.source.local_control_plane')}
          {/if}
        </span>
      </div>
    </header>

    <div class="command-bar-wrap">
      <ReviewCommandBar />
    </div>

    <div class="review-content">
      {#if $reviewCenterState.status === 'idle'}
        <section class="review-state" aria-live="polite">
          <Icon name="audit" size={24} />
          <div>
            <h2>{$t('review.state.idle')}</h2>
            <p>{$t('review.state.idle_detail')}</p>
            <code>{$t('review.source.local_control_plane')}</code>
          </div>
        </section>
      {:else if $reviewCenterState.status === 'loading'}
        <section class="review-state" aria-live="polite" aria-busy="true">
          <Icon name="audit" size={24} />
          <div>
            <h2>{$t('review.state.loading')}</h2>
            <p>{$t('review.state.loading_detail')}</p>
            <code>{$t('review.source.local_control_plane')}</code>
          </div>
        </section>
      {:else if $reviewCenterState.status === 'empty'}
        <section class="review-state" aria-live="polite">
          <Icon name="audit" size={24} />
          <div>
            <h2>{$t('review.state.empty')}</h2>
            <p>{$t('review.state.empty_detail')}</p>
            <code>{$t('review.source.local_control_plane')}</code>
            <p class="decision-unavailable">{$t('review.decision.unavailable')}</p>
            <strong>{$t('review.decision.hard_stop_title')}</strong>
          </div>
          <button type="button" onclick={() => void loadReviewCenter()}>
            {$t('review.refresh')}
          </button>
        </section>
      {:else if $reviewCenterState.status === 'error'}
        <section class="review-state review-state-error" aria-live="assertive">
          <Icon name="cancel" size={24} />
          <div>
            <h2>{$t('review.state.error')}</h2>
            <p>{$reviewCenterState.error?.message ?? $t('review.state.error_detail')}</p>
            <code>{$reviewCenterState.error?.code ?? 'review_bridge_error'}</code>
          </div>
          {#if $reviewCenterState.retryable}
            <button type="button" onclick={() => void retryReviewCenter()}>
              {$t('review.retry')}
            </button>
          {/if}
        </section>
      {:else if $selectedReview}
        {#if !$selectedReview.fixture && $selectedReview.stale === true}
          <section class="stale-notice" role="alert">
            <Icon name="cancel" size={20} />
            <div>
              <strong>{$t('review.stale.title')}</strong>
              <span>{$t('review.stale.detail')}</span>
            </div>
          </section>
        {:else if !$selectedReview.fixture && $selectedReview.stale === null}
          <section class="stale-notice freshness-unknown" role="alert">
            <Icon name="audit" size={20} />
            <div>
              <strong>{$t('review.stale.unknown_title')}</strong>
              <span>{$t('review.stale.unknown_detail')}</span>
            </div>
          </section>
        {/if}

        {#if $selectedReview.detailProjectionTruncated || selectedQueueItem?.detailProjectionTruncated}
          <section
            class="detail-truncated-notice"
            role="note"
            aria-label={$t('review.detail_truncated.title')}
          >
            <Icon name="audit" size={20} />
            <div>
              <strong>{$t('review.detail_truncated.title')}</strong>
              <span>{$t('review.detail_truncated.detail')}</span>
            </div>
          </section>
        {/if}

        <ReviewIdentityPanel review={$selectedReview} />

        <div class="two-column">
          <ReviewValidationPanel review={$selectedReview} />
          <ReviewFindingsPanel review={$selectedReview} />
        </div>

        <ReviewMetadataPanel review={$selectedReview} />

        <div class="two-column">
          <ReviewTextDiffPanel review={$selectedReview} />
          <RepresentationDeltaPanel review={$selectedReview} />
        </div>

        <section class="human-preview" aria-labelledby="human-review-preview-heading">
          <header>
            <div>
              <p class="panel-eyebrow">{$t('review.preview.eyebrow')}</p>
              <h2 id="human-review-preview-heading">{$t('review.preview.title')}</h2>
            </div>
            {#if $selectedReview.humanReviewPreview.truncated}
              <span class="truncated-badge">{$t('review.preview.truncated')}</span>
            {/if}
          </header>
          <pre>{$selectedReview.humanReviewPreview.text}</pre>
        </section>

        <ReviewDecisionPanel review={$selectedReview} />

        <div class="two-column command-center-observability">
          <ReviewDiagnosticsPanel />
          <ReviewActivityTimeline />
        </div>

        <section class="phase-boundary" aria-label={$t('review.phase_boundary.title')}>
          <Icon name="shield" size={20} />
          <div>
            <strong>{$t('review.phase_boundary.title')}</strong>
            <span>{$t('review.phase_boundary.detail')}</span>
          </div>
        </section>
      {/if}
    </div>
  </article>
</main>

<style>
  .review-workspace {
    min-width: 0;
    min-height: 0;
    display: grid;
    grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
    overflow: hidden;
    background: var(--lc-bg);
  }

  .review-detail {
    min-width: 0;
    min-height: 0;
    overflow: auto;
  }

  .review-header {
    position: sticky;
    top: 0;
    z-index: 10;
    min-height: 88px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--lc-space-4);
    border-bottom: var(--border-thin);
    background: color-mix(in srgb, var(--lc-bg-elevated) 94%, transparent);
    backdrop-filter: blur(18px);
    padding: var(--lc-space-3) var(--lc-space-5);
  }

  .review-heading {
    min-width: 0;
  }

  .review-eyebrow,
  .panel-eyebrow {
    margin: 0 0 4px;
    color: var(--lc-accent);
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.11em;
    text-transform: uppercase;
  }

  .title-row {
    display: flex;
    align-items: flex-start;
    gap: var(--lc-space-3);
  }

  .title-icon {
    display: grid;
    place-items: center;
    width: 38px;
    height: 38px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    background: var(--lc-panel-soft);
    color: var(--lc-accent);
  }

  h1,
  h2 {
    margin: 0;
  }

  h1 {
    font-size: clamp(18px, 2vw, 24px);
  }

  .title-row p {
    margin: 4px 0 0;
    color: var(--lc-muted);
    font-size: 12px;
  }

  .header-status {
    display: grid;
    justify-items: end;
    gap: var(--lc-space-2);
  }

  .source-marker {
    max-width: 320px;
    overflow-wrap: anywhere;
    color: var(--lc-info);
    font-family: var(--lc-mono);
    font-size: 10px;
    text-align: right;
  }

  .review-state {
    min-height: 220px;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: start;
    gap: var(--lc-space-4);
    border: var(--border-thin);
    border-radius: var(--lc-radius-lg);
    background: var(--lc-panel);
    padding: var(--lc-space-5);
    color: var(--lc-accent);
  }

  .review-state div {
    display: grid;
    gap: var(--lc-space-2);
  }

  .review-state h2,
  .review-state p {
    margin: 0;
  }

  .review-state p {
    color: var(--lc-muted);
    font-size: 12px;
    line-height: 1.55;
  }

  .review-state code {
    overflow-wrap: anywhere;
    color: var(--lc-accent);
    font-family: var(--lc-mono);
    font-size: 11px;
  }

  .review-state button {
    min-height: 44px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    background: var(--lc-panel-soft);
    color: var(--lc-text);
    padding: 0 var(--lc-space-4);
    cursor: pointer;
  }

  .review-state button:focus-visible {
    outline: 1px solid var(--lc-accent);
    outline-offset: 2px;
    box-shadow: var(--focus-ring);
  }

  .review-state-error {
    color: var(--lc-danger);
  }

  .review-state .decision-unavailable {
    color: var(--lc-warning);
  }

  .review-content {
    width: min(1180px, 100%);
    display: grid;
    gap: var(--lc-space-4);
    margin: 0 auto;
    padding: var(--lc-space-5);
  }

  .two-column {
    min-width: 0;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--lc-space-4);
  }

  .human-preview {
    min-width: 0;
    border: var(--border-thin);
    border-radius: var(--lc-radius-lg);
    background: var(--lc-panel);
    padding: var(--lc-space-4);
  }

  .human-preview header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--lc-space-3);
    margin-bottom: var(--lc-space-3);
  }

  .human-preview h2 {
    font-size: 16px;
  }

  .human-preview pre {
    max-height: 280px;
    overflow: auto;
    margin: 0;
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    background: var(--color-code);
    color: var(--lc-text);
    padding: var(--lc-space-3);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    font-family: var(--lc-mono);
    font-size: 11px;
    line-height: 1.55;
  }

  .truncated-badge {
    border: 1px solid color-mix(in srgb, var(--lc-warning) 42%, transparent);
    border-radius: 999px;
    color: var(--lc-warning);
    padding: 4px 8px;
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
  }

  .phase-boundary {
    min-height: 56px;
    display: flex;
    align-items: center;
    gap: var(--lc-space-3);
    border: 1px solid color-mix(in srgb, var(--lc-info) 38%, transparent);
    border-radius: var(--lc-radius-lg);
    background: color-mix(in srgb, var(--lc-info) 6%, transparent);
    color: var(--lc-info);
    padding: var(--lc-space-3) var(--lc-space-4);
  }

  .detail-truncated-notice {
    min-height: 56px;
    display: flex;
    align-items: center;
    gap: var(--lc-space-3);
    border: 1px solid color-mix(in srgb, var(--lc-warning) 48%, transparent);
    border-radius: var(--lc-radius-md);
    background: color-mix(in srgb, var(--lc-warning) 8%, transparent);
    color: var(--lc-warning);
    padding: var(--lc-space-3) var(--lc-space-4);
  }

  .detail-truncated-notice div {
    display: grid;
    gap: 3px;
  }

  .detail-truncated-notice strong {
    font-size: 12px;
  }

  .detail-truncated-notice span {
    color: var(--lc-muted);
    font-size: 11px;
    line-height: 1.45;
  }

  .phase-boundary div {
    display: grid;
    gap: 3px;
  }

  .phase-boundary strong {
    font-size: 12px;
  }

  .phase-boundary span {
    color: var(--lc-muted);
    font-size: 11px;
    line-height: 1.45;
  }

  @media (max-width: 920px) {
    .review-workspace {
      grid-template-columns: minmax(0, 1fr);
      grid-template-rows: auto minmax(0, 1fr);
    }

    .review-header {
      position: static;
      padding-inline: var(--lc-space-4);
    }

    .review-content {
      padding: var(--lc-space-4);
    }
  }

  @media (max-width: 760px) {
    .review-header {
      align-items: stretch;
      flex-direction: column;
    }

    .header-status {
      justify-items: start;
    }

    .source-marker {
      text-align: left;
    }

    .review-state {
      grid-template-columns: 1fr;
    }

    .review-state button {
      width: 100%;
    }

    .two-column {
      grid-template-columns: 1fr;
    }

    .review-content {
      padding: var(--lc-space-3);
    }
  }

  .command-bar-wrap {
    padding: var(--lc-space-4) var(--lc-space-5) 0;
  }

  .stale-notice {
    display: flex;
    align-items: flex-start;
    gap: var(--lc-space-3);
    border: 1px solid color-mix(in srgb, var(--lc-danger) 46%, transparent);
    border-radius: var(--lc-radius-lg);
    background: color-mix(in srgb, var(--lc-danger) 8%, transparent);
    padding: var(--lc-space-4);
    color: var(--lc-danger);
  }

  .stale-notice.freshness-unknown {
    border-color: color-mix(in srgb, var(--lc-warning) 46%, transparent);
    background: color-mix(in srgb, var(--lc-warning) 8%, transparent);
    color: var(--lc-warning);
  }

  .stale-notice div {
    display: grid;
    gap: 4px;
  }

  .stale-notice span {
    color: var(--lc-muted);
    font-size: 12px;
    line-height: 1.5;
  }

  .command-center-observability {
    align-items: start;
  }

</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/review/ReviewCommandBar.svelte (260 строк, 5930 байт)

````svelte
<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import { t } from '$lib/i18n';
  import {
    clearReviewFilters,
    filteredReviewQueue,
    refreshReviewCenter,
    reviewCenterState,
    reviewFilters,
    setReviewQuery,
    setReviewSort,
    toggleReviewOperation,
    toggleReviewStatus
  } from '$lib/stores/reviewCenter';
  import type { ReviewOperation, ReviewStatus } from '$lib/types/knowledgeReview';

  const statuses: readonly ReviewStatus[] = ['CLEAR', 'REVIEW_REQUIRED', 'BLOCKED'];
  const operations: readonly ReviewOperation[] = [
    'CREATE_NEW',
    'UPDATE_EXISTING',
    'DELETE',
    'MOVE',
    'RENAME',
    'SUPERSEDE'
  ];

  $: filtersActive =
    $reviewFilters.query.length > 0 ||
    $reviewFilters.statuses.length > 0 ||
    $reviewFilters.operations.length > 0;
</script>

<section class="command-bar" aria-label={$t('review.command_bar.label')}>
  <div class="search-field">
    <label for="review-search">{$t('review.command_bar.search')}</label>
    <input
      id="review-search"
      type="search"
      maxlength="200"
      value={$reviewFilters.query}
      placeholder={$t('review.command_bar.search_placeholder')}
      oninput={(event) => setReviewQuery((event.currentTarget as HTMLInputElement).value)}
    />
  </div>

  <fieldset>
    <legend>{$t('review.command_bar.status_filter')}</legend>
    <div class="filter-row">
      {#each statuses as status}
        <button
          type="button"
          class:active={$reviewFilters.statuses.includes(status)}
          aria-pressed={$reviewFilters.statuses.includes(status)}
          onclick={() => toggleReviewStatus(status)}
        >
          {$t(`review.status.${status}`)}
        </button>
      {/each}
    </div>
  </fieldset>

  <fieldset class="operation-filter">
    <legend>{$t('review.command_bar.operation_filter')}</legend>
    <div class="filter-row">
      {#each operations as operation}
        <button
          type="button"
          class:active={$reviewFilters.operations.includes(operation)}
          aria-pressed={$reviewFilters.operations.includes(operation)}
          onclick={() => toggleReviewOperation(operation)}
        >
          {operation}
        </button>
      {/each}
    </div>
  </fieldset>

  <div class="command-actions">
    <label for="review-sort">{$t('review.command_bar.sort')}</label>
    <select
      id="review-sort"
      value={$reviewFilters.sort}
      onchange={(event) =>
        setReviewSort(
          (event.currentTarget as HTMLSelectElement).value as
            | 'IDENTITY_ASC'
            | 'STATUS_THEN_IDENTITY'
        )}
    >
      <option value="STATUS_THEN_IDENTITY">{$t('review.command_bar.sort_status')}</option>
      <option value="IDENTITY_ASC">{$t('review.command_bar.sort_identity')}</option>
    </select>

    <span class="filtered-count" aria-live="polite">
      {$filteredReviewQueue.length} {$t('review.command_bar.visible')}
    </span>

    <button type="button" disabled={!filtersActive} onclick={clearReviewFilters}>
      {$t('review.command_bar.clear')}
    </button>
    <button
      type="button"
      class="refresh-button"
      disabled={$reviewCenterState.status === 'loading'}
      onclick={() => void refreshReviewCenter()}
    >
      <Icon name="refresh" size={17} />
      {$t('review.command_bar.revalidate')}
    </button>
  </div>
</section>

<style>
  .command-bar {
    display: grid;
    grid-template-columns: minmax(220px, 1.25fr) minmax(0, 1fr);
    gap: var(--lc-space-3);
    border: var(--border-thin);
    border-radius: var(--lc-radius-lg);
    background: var(--lc-panel);
    padding: var(--lc-space-4);
  }

  .search-field,
  .command-actions {
    min-width: 0;
    display: flex;
    align-items: end;
    gap: var(--lc-space-2);
    flex-wrap: wrap;
  }

  .search-field {
    display: grid;
    align-content: start;
  }

  label,
  legend {
    color: var(--lc-muted);
    font-size: 11px;
    font-weight: 760;
  }

  input,
  select,
  button {
    min-height: 44px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    background: var(--lc-panel-soft);
    color: var(--lc-text);
    font: inherit;
  }

  input,
  select {
    min-width: 0;
    padding: 0 var(--lc-space-3);
  }

  input {
    width: 100%;
  }

  button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--lc-space-2);
    padding: 0 var(--lc-space-3);
    cursor: pointer;
  }

  button.active {
    border-color: var(--lc-accent);
    background: var(--lc-accent-dim);
    color: var(--lc-accent);
  }

  button:disabled {
    cursor: not-allowed;
    opacity: 0.52;
  }

  input:focus-visible,
  select:focus-visible,
  button:focus-visible {
    outline: 2px solid var(--lc-accent);
    outline-offset: 2px;
  }

  fieldset {
    min-width: 0;
    margin: 0;
    border: 0;
    padding: 0;
  }

  .operation-filter {
    grid-column: 1 / -1;
  }

  .filter-row {
    display: flex;
    gap: var(--lc-space-2);
    flex-wrap: wrap;
    margin-top: var(--lc-space-2);
  }

  .filter-row button {
    min-height: 44px;
    font-family: var(--lc-mono);
    font-size: 10px;
  }

  .command-actions {
    grid-column: 1 / -1;
  }

  .command-actions label {
    align-self: center;
  }

  .filtered-count {
    align-self: center;
    color: var(--lc-muted);
    font-family: var(--lc-mono);
    font-size: 11px;
  }

  .refresh-button {
    margin-left: auto;
    border-color: var(--lc-line-strong);
    color: var(--lc-accent);
  }

  @media (max-width: 760px) {
    .command-bar {
      grid-template-columns: 1fr;
    }

    .operation-filter,
    .command-actions {
      grid-column: 1;
    }

    .refresh-button {
      margin-left: 0;
      width: 100%;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    * {
      scroll-behavior: auto !important;
      transition: none !important;
    }
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/review/ReviewDecisionPanel.svelte (358 строк, 9631 байт)

````svelte
<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import DecisionConfirmationDialog from './DecisionConfirmationDialog.svelte';
  import { t } from '$lib/i18n';
  import {
    closeDecisionDialog,
    confirmDecision,
    decisionDialog,
    decisionResult,
    openDecisionDialog,
    setDecisionActorDisplayName,
    setDecisionActorIdentifier,
    setDecisionComment
  } from '$lib/stores/reviewCenter';
  import type { DecisionIntent, ReviewCenterItem } from '$lib/types/knowledgeReview';

  export let review: ReviewCenterItem;

  let triggerElement: HTMLElement | null = null;

  $: realReview = review.fixture === false;
  $: staleOrUnknown = review.fixture === false && review.stale !== false;
  $: approveDisabled =
    $decisionDialog.submitting || review.status === 'BLOCKED' || staleOrUnknown;
  $: otherDisabled = $decisionDialog.submitting || staleOrUnknown;
  $: resultForReview =
    $decisionResult &&
    ($decisionResult.fixture
      ? $decisionResult.reviewArtifactIdentity === review.reviewArtifactIdentity
      : $decisionResult.decision.review_artifact_identity === review.reviewArtifactIdentity)
      ? $decisionResult
      : null;

  function requestIntent(intent: DecisionIntent, event: MouseEvent): void {
    triggerElement = event.currentTarget as HTMLElement;
    openDecisionDialog(review, intent);
  }

  async function confirm(): Promise<void> {
    await confirmDecision(review);
  }
</script>

<section class="review-panel decision-panel" aria-labelledby="review-decision-heading">
  <header class="panel-header">
    <div>
      <p class="panel-eyebrow">{$t('review.decision.eyebrow')}</p>
      <h2 id="review-decision-heading">{$t('review.decision.title')}</h2>
    </div>
    <span class:fixture-badge={!realReview} class:real-badge={realReview}>
      {realReview
        ? $t('review.decision.real_e9c')
        : $t('review.decision.fixture_only')}
    </span>
  </header>

  <p class="decision-boundary">
    {realReview
      ? $t('review.decision.real_boundary')
      : $t('review.decision.boundary')}
  </p>

  {#if review.fixture === false && review.stale === true}
    <p class="stale-note" role="alert">{$t('review.decision.stale')}</p>
  {:else if review.fixture === false && review.stale === null}
    <p class="stale-note" role="alert">{$t('review.decision.freshness_unknown')}</p>
  {/if}

  <div class="decision-actions" role="group" aria-label={$t('review.decision.actions')}>
    <button
      type="button"
      class="approve-button"
      disabled={approveDisabled}
      aria-disabled={approveDisabled}
      title={review.status === 'BLOCKED'
        ? $t('review.decision.blocked_approval')
        : staleOrUnknown
          ? $t('review.decision.stale_or_unknown')
          : $t('review.decision.approve')}
      onclick={(event) => requestIntent('APPROVE', event)}
    >
      <Icon name="check" size={18} />
      {$t('review.decision.approve')}
    </button>
    <button
      type="button"
      class="reject-button"
      disabled={otherDisabled}
      aria-disabled={otherDisabled}
      title={staleOrUnknown
        ? $t('review.decision.stale_or_unknown')
        : $t('review.decision.reject')}
      onclick={(event) => requestIntent('REJECT', event)}
    >
      <Icon name="cancel" size={18} />
      {$t('review.decision.reject')}
    </button>
    <button
      type="button"
      class="request-button"
      disabled={otherDisabled}
      aria-disabled={otherDisabled}
      title={staleOrUnknown
        ? $t('review.decision.stale_or_unknown')
        : $t('review.decision.request_changes')}
      onclick={(event) => requestIntent('REQUEST_CHANGES', event)}
    >
      <Icon name="audit" size={18} />
      {$t('review.decision.request_changes')}
    </button>
  </div>

  {#if review.status === 'BLOCKED'}
    <p class="blocked-note">{$t('review.decision.blocked_approval')}</p>
  {/if}

  <div class="decision-result" aria-live="polite" aria-atomic="true">
    {#if resultForReview?.fixture}
      <strong>{$t('review.decision.fixture_result')}</strong>
      <span>{$t(resultForReview.messageKey)}</span>
      <code>{resultForReview.intent}</code>
    {:else if resultForReview && !resultForReview.fixture}
      <strong>{$t('review.decision.real_result')}</strong>
      <span>{$t(resultForReview.messageKey)}</span>
      <dl>
        <div>
          <dt>{$t('review.decision.decision_identity')}</dt>
          <dd><code>{resultForReview.decision.decision_identity}</code></dd>
        </div>
        <div>
          <dt>{$t('review.decision.intent')}</dt>
          <dd><code>{resultForReview.decision.decision}</code></dd>
        </div>
        <div>
          <dt>{$t('review.decision.vault_modified')}</dt>
          <dd>{$t('review.no')}</dd>
        </div>
      </dl>
    {/if}
  </div>

  <div class="hard-stop">
    <Icon name="shield" size={17} />
    <div>
      <strong>{$t('review.decision.hard_stop_title')}</strong>
      <span>
        {realReview
          ? $t('review.decision.real_hard_stop_detail')
          : $t('review.decision.hard_stop_detail')}
      </span>
    </div>
  </div>
</section>

{#if $decisionDialog.open && $decisionDialog.intent}
  <DecisionConfirmationDialog
    {review}
    intent={$decisionDialog.intent}
    comment={$decisionDialog.comment}
    actorIdentifier={$decisionDialog.actorIdentifier}
    actorDisplayName={$decisionDialog.actorDisplayName}
    submitting={$decisionDialog.submitting}
    errorKey={$decisionDialog.errorKey}
    {triggerElement}
    onClose={closeDecisionDialog}
    onComment={setDecisionComment}
    onActorIdentifier={setDecisionActorIdentifier}
    onActorDisplayName={setDecisionActorDisplayName}
    onConfirm={confirm}
  />
{/if}

<style>
  .review-panel {
    border: 1px solid var(--lc-line-strong);
    border-radius: var(--lc-radius-lg);
    background: linear-gradient(180deg, var(--lc-accent-dim), var(--lc-panel));
    padding: var(--lc-space-4);
  }

  .panel-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--lc-space-3);
    margin-bottom: var(--lc-space-3);
  }

  .panel-eyebrow {
    margin: 0 0 4px;
    color: var(--lc-accent);
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.11em;
    text-transform: uppercase;
  }

  h2 {
    margin: 0;
    font-size: 16px;
  }

  .fixture-badge,
  .real-badge {
    border: 1px solid color-mix(in srgb, var(--lc-info) 45%, transparent);
    border-radius: 999px;
    padding: 4px 8px;
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
  }

  .fixture-badge {
    color: var(--lc-info);
  }

  .real-badge {
    color: var(--lc-accent);
  }

  .decision-boundary {
    margin: 0 0 var(--lc-space-4);
    color: var(--lc-muted);
    font-size: 12px;
    line-height: 1.55;
  }

  .decision-actions {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--lc-space-3);
  }

  .decision-actions button {
    min-height: 48px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--lc-space-2);
    border-radius: var(--lc-radius-md);
    padding: 0 var(--lc-space-3);
    font-size: 12px;
    font-weight: 820;
    cursor: pointer;
  }

  .decision-actions button:focus-visible {
    outline: 2px solid var(--lc-accent);
    outline-offset: 2px;
  }

  .decision-actions button:disabled {
    cursor: not-allowed;
    opacity: 0.45;
  }

  .approve-button {
    border: 1px solid var(--lc-line-strong);
    background: var(--lc-accent-dim);
    color: var(--lc-accent);
  }

  .reject-button {
    border: 1px solid color-mix(in srgb, var(--lc-danger) 42%, transparent);
    background: color-mix(in srgb, var(--lc-danger) 8%, transparent);
    color: var(--lc-danger);
  }

  .request-button {
    border: 1px solid color-mix(in srgb, var(--lc-warning) 42%, transparent);
    background: color-mix(in srgb, var(--lc-warning) 8%, transparent);
    color: var(--lc-warning);
  }

  .blocked-note,
  .stale-note {
    margin: var(--lc-space-3) 0 0;
    color: var(--lc-danger);
    font-size: 12px;
  }

  .stale-note {
    margin: 0 0 var(--lc-space-3);
  }

  .decision-result {
    min-height: 22px;
    display: grid;
    gap: var(--lc-space-2);
    margin-top: var(--lc-space-4);
  }

  .decision-result strong {
    color: var(--lc-accent);
  }

  .decision-result span,
  .decision-result code,
  .decision-result dt,
  .decision-result dd {
    overflow-wrap: anywhere;
    font-size: 11px;
  }

  .decision-result code {
    font-family: var(--lc-mono);
  }

  .decision-result dl {
    display: grid;
    gap: var(--lc-space-2);
    margin: 0;
  }

  .decision-result dl > div {
    display: grid;
    grid-template-columns: minmax(120px, 0.35fr) minmax(0, 1fr);
    gap: var(--lc-space-2);
  }

  .decision-result dd {
    margin: 0;
  }

  .hard-stop {
    display: flex;
    align-items: flex-start;
    gap: var(--lc-space-3);
    border: 1px solid color-mix(in srgb, var(--lc-warning) 42%, transparent);
    border-radius: var(--lc-radius-md);
    background: color-mix(in srgb, var(--lc-warning) 8%, transparent);
    margin-top: var(--lc-space-4);
    padding: var(--lc-space-3);
    color: var(--lc-warning);
  }

  .hard-stop div {
    display: grid;
    gap: 4px;
  }

  .hard-stop span {
    color: var(--lc-muted);
    font-size: 11px;
    line-height: 1.5;
  }

  @media (max-width: 760px) {
    .decision-actions {
      grid-template-columns: 1fr;
    }

    .decision-result dl > div {
      grid-template-columns: 1fr;
    }
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/review/ReviewDiagnosticsPanel.svelte (157 строк, 3724 байт)

````svelte
<script lang="ts">
  import { t } from '$lib/i18n';
  import { reviewDiagnostics } from '$lib/stores/reviewCenter';
</script>

<section class="diagnostics review-panel" aria-labelledby="review-diagnostics-title">
  <header>
    <div>
      <p>{$t('review.diagnostics.eyebrow')}</p>
      <h2 id="review-diagnostics-title">{$t('review.diagnostics.title')}</h2>
    </div>
    <span class="connection-state state-{$reviewDiagnostics.sidecarConnectionState.toLowerCase()}">
      {$t(`review.connection.${$reviewDiagnostics.sidecarConnectionState}`)}
    </span>
  </header>

  <dl>
    <div>
      <dt>{$t('review.diagnostics.command_center')}</dt>
      <dd><code>{$reviewDiagnostics.commandCenterVersion}</code></dd>
    </div>
    <div>
      <dt>{$t('review.diagnostics.frontend_contract')}</dt>
      <dd><code>{$reviewDiagnostics.frontendContractVersion}</code></dd>
    </div>
    <div>
      <dt>{$t('review.diagnostics.tauri')}</dt>
      <dd>{$t(`review.connection.${$reviewDiagnostics.tauriBridgeStatus}`)}</dd>
    </div>
    <div>
      <dt>{$t('review.diagnostics.sidecar')}</dt>
      <dd>{$t(`review.connection.${$reviewDiagnostics.sidecarConnectionState}`)}</dd>
    </div>
    <div>
      <dt>{$t('review.diagnostics.python_runtime')}</dt>
      <dd><code>{$reviewDiagnostics.pythonRuntimeContractVersion ?? $t('review.unavailable')}</code></dd>
    </div>
    <div>
      <dt>{$t('review.diagnostics.inbox')}</dt>
      <dd>{$reviewDiagnostics.inboxCount}</dd>
    </div>
    <div>
      <dt>{$t('review.diagnostics.stale')}</dt>
      <dd>{$reviewDiagnostics.staleCount}</dd>
    </div>
    <div>
      <dt>{$t('review.diagnostics.blocked')}</dt>
      <dd>{$reviewDiagnostics.blockedCount}</dd>
    </div>
    <div>
      <dt>{$t('review.diagnostics.decisions')}</dt>
      <dd>{$reviewDiagnostics.sessionDecisionCount}</dd>
    </div>
    <div>
      <dt>{$t('review.diagnostics.last_error')}</dt>
      <dd><code>{$reviewDiagnostics.lastErrorCode ?? $t('review.none')}</code></dd>
    </div>
  </dl>

  <p class="boundary">{$t('review.diagnostics.boundary')}</p>
</section>

<style>
  .review-panel {
    border: var(--border-thin);
    border-radius: var(--lc-radius-lg);
    background: var(--lc-panel);
    padding: var(--lc-space-4);
  }

  header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--lc-space-3);
    margin-bottom: var(--lc-space-3);
  }

  header p {
    margin: 0 0 4px;
    color: var(--lc-accent);
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.11em;
    text-transform: uppercase;
  }

  h2 {
    margin: 0;
    font-size: 16px;
  }

  .connection-state {
    border: var(--border-thin);
    border-radius: 999px;
    padding: 4px 9px;
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
  }

  .state-connected {
    color: var(--lc-accent);
  }

  .state-error,
  .state-unavailable {
    color: var(--lc-danger);
  }

  .state-connecting {
    color: var(--lc-warning);
  }

  dl {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--lc-space-2);
    margin: 0;
  }

  dl > div {
    min-width: 0;
    border-top: var(--border-thin);
    padding-top: var(--lc-space-2);
  }

  dt {
    color: var(--lc-muted);
    font-size: 10px;
    text-transform: uppercase;
  }

  dd {
    margin: 4px 0 0;
    overflow-wrap: anywhere;
    font-size: 12px;
  }

  code {
    font-family: var(--lc-mono);
  }

  .boundary {
    margin: var(--lc-space-3) 0 0;
    color: var(--lc-muted);
    font-size: 11px;
    line-height: 1.5;
  }

  @media (max-width: 760px) {
    dl {
      grid-template-columns: 1fr;
    }
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/review/ReviewFindingsPanel.svelte (203 строк, 4551 байт)

````svelte
<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import { t } from '$lib/i18n';
  import { sortReviewFindings } from '$lib/types/knowledgeReview';
  import type { ReviewCenterItem } from '$lib/types/knowledgeReview';

  export let review: ReviewCenterItem;

  $: findings = sortReviewFindings(review.findings);
</script>

<section class="review-panel" aria-labelledby="review-findings-heading">
  <header class="panel-header">
    <div>
      <p class="panel-eyebrow">{$t('review.findings.eyebrow')}</p>
      <h2 id="review-findings-heading">{$t('review.findings.title')}</h2>
    </div>
    <span class="finding-count">{findings.length}</span>
  </header>

  {#if findings.length === 0}
    <div class="empty-findings">
      <Icon name="check" size={18} />
      <span>{$t('review.findings.none')}</span>
    </div>
  {:else}
    <ol class="finding-list">
      {#each findings as finding}
        <li class:blocking={finding.severity === 'BLOCKING'}>
          <header>
            <span class="finding-icon" aria-hidden="true">
              <Icon name={finding.severity === 'BLOCKING' ? 'cancel' : 'audit'} size={17} />
            </span>
            <div>
              <code>{finding.code}</code>
              <span class="severity">
                {$t(`review.severity.${finding.severity}`)}
              </span>
            </div>
          </header>
          <p>{finding.message}</p>
          {#if finding.details.length > 0}
            <dl>
              {#each finding.details as detail}
                <div>
                  <dt>{detail[0]}</dt>
                  <dd><code>{detail[1]}</code></dd>
                </div>
              {/each}
            </dl>
          {/if}
        </li>
      {/each}
    </ol>
  {/if}
</section>

<style>
  .review-panel {
    border: var(--border-thin);
    border-radius: var(--lc-radius-lg);
    background: var(--lc-panel);
    padding: var(--lc-space-4);
  }

  .panel-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--lc-space-3);
    margin-bottom: var(--lc-space-4);
  }

  .panel-eyebrow {
    margin: 0 0 4px;
    color: var(--lc-accent);
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.11em;
    text-transform: uppercase;
  }

  h2 {
    margin: 0;
    font-size: 16px;
  }

  .finding-count {
    display: grid;
    place-items: center;
    min-width: 28px;
    height: 28px;
    border: var(--border-thin);
    border-radius: 999px;
    color: var(--lc-muted);
    font-family: var(--lc-mono);
    font-size: 12px;
  }

  .empty-findings {
    min-height: 48px;
    display: flex;
    align-items: center;
    gap: var(--lc-space-2);
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    color: var(--lc-accent);
    padding: var(--lc-space-3);
    font-size: 12px;
  }

  .finding-list {
    display: grid;
    gap: var(--lc-space-3);
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .finding-list > li {
    border: 1px solid color-mix(in srgb, var(--lc-warning) 34%, transparent);
    border-radius: var(--lc-radius-md);
    background: color-mix(in srgb, var(--lc-warning) 6%, transparent);
    padding: var(--lc-space-3);
  }

  .finding-list > li.blocking {
    border-color: color-mix(in srgb, var(--lc-danger) 40%, transparent);
    background: color-mix(in srgb, var(--lc-danger) 7%, transparent);
  }

  li > header {
    display: flex;
    align-items: flex-start;
    gap: var(--lc-space-2);
  }

  .finding-icon {
    color: var(--lc-warning);
  }

  .blocking .finding-icon {
    color: var(--lc-danger);
  }

  li > header > div {
    min-width: 0;
    display: grid;
    gap: 4px;
  }

  li code {
    overflow-wrap: anywhere;
    font-family: var(--lc-mono);
    font-size: 11px;
  }

  .severity {
    color: var(--lc-muted);
    font-size: 10px;
    font-weight: 780;
  }

  li p {
    margin: var(--lc-space-2) 0 0 26px;
    color: var(--lc-text);
    font-size: 12px;
    line-height: 1.55;
  }

  dl {
    display: grid;
    gap: 6px;
    margin: var(--lc-space-3) 0 0 26px;
  }

  dl > div {
    min-width: 0;
    display: grid;
    grid-template-columns: minmax(110px, 0.3fr) minmax(0, 1fr);
    gap: var(--lc-space-2);
  }

  dt,
  dd {
    margin: 0;
    overflow-wrap: anywhere;
    color: var(--lc-muted);
    font-size: 11px;
  }

  @media (max-width: 760px) {
    dl > div {
      grid-template-columns: 1fr;
    }

    li p,
    dl {
      margin-left: 0;
    }
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/review/ReviewIdentityPanel.svelte (313 строк, 8416 байт)

````svelte
<script module lang="ts">
  import type { ReviewCenterItem } from '$lib/types/knowledgeReview';

  export type ReviewIdentityRow = Readonly<{
    key: string;
    labelKey: string;
    value: string | null;
  }>;

  export type ReviewClipboard = {
    writeText: (value: string) => Promise<void>;
  };

  export function getReviewIdentityRows(review: ReviewCenterItem): readonly ReviewIdentityRow[] {
    return [
      { key: 'proposal', labelKey: 'review.identity.proposal_id', value: review.proposalId },
      { key: 'review', labelKey: 'review.identity.review_identity', value: review.reviewArtifactIdentity },
      { key: 'change', labelKey: 'review.identity.change_identity', value: review.changeIdentity },
      { key: 'expected', labelKey: 'review.identity.expected_revision', value: review.expectedVaultRevision },
      { key: 'observed', labelKey: 'review.identity.observed_revision', value: review.observedVaultRevision },
      { key: 'target', labelKey: 'review.identity.target_id', value: review.targetStableId },
      { key: 'operation', labelKey: 'review.identity.operation', value: review.operation }
    ];
  }

  export function isReviewCopyActivationKey(key: string): boolean {
    return key === 'Enter' || key === ' ';
  }

  export async function writeReviewValueToClipboard(
    value: string,
    clipboard: ReviewClipboard | undefined,
    timeoutMs = 1200
  ): Promise<boolean> {
    if (!clipboard) return false;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    try {
      const copyAttempt = clipboard.writeText(value).then(
        () => true,
        () => false
      );
      const timeout = new Promise<boolean>((resolve) => {
        timeoutId = setTimeout(() => resolve(false), timeoutMs);
      });
      return await Promise.race([copyAttempt, timeout]);
    } finally {
      if (timeoutId !== undefined) clearTimeout(timeoutId);
    }
  }
</script>

<script lang="ts">
  import { onDestroy } from 'svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import { t } from '$lib/i18n';

  export let review: ReviewCenterItem;

  type CopyFeedback = Readonly<{
    key: string;
    outcome: 'success' | 'failure';
  }>;

  let copyFeedback: CopyFeedback | null = null;
  let feedbackTimer: number | null = null;
  let feedbackReviewId = review.id;

  $: rows = getReviewIdentityRows(review);
  $: if (review.id !== feedbackReviewId) {
    feedbackReviewId = review.id;
    copyFeedback = null;
    clearFeedbackTimer();
  }

  function clearFeedbackTimer(): void {
    if (feedbackTimer === null || typeof window === 'undefined') return;
    window.clearTimeout(feedbackTimer);
    feedbackTimer = null;
  }

  async function copyValue(key: string, value: string): Promise<void> {
    const clipboard = typeof navigator === 'undefined' ? undefined : navigator.clipboard;
    const copied = await writeReviewValueToClipboard(value, clipboard);
    copyFeedback = { key, outcome: copied ? 'success' : 'failure' };
    clearFeedbackTimer();
    if (typeof window !== 'undefined') {
      feedbackTimer = window.setTimeout(() => {
        if (copyFeedback?.key === key) copyFeedback = null;
        feedbackTimer = null;
      }, 2200);
    }
  }

  function handleCopyKeydown(event: KeyboardEvent, key: string, value: string): void {
    if (!isReviewCopyActivationKey(event.key)) return;
    event.preventDefault();
    void copyValue(key, value);
  }

  onDestroy(clearFeedbackTimer);
</script>

<section class="review-panel identity-panel" aria-labelledby="review-identity-heading">
  <header class="panel-header">
    <div>
      <p class="panel-eyebrow">{$t('review.identity.eyebrow')}</p>
      <h2 id="review-identity-heading">{$t('review.identity.title')}</h2>
    </div>
    <span class:fixture-badge={review.fixture} class:source-badge={!review.fixture}>
      {review.fixture
        ? $t('review.fixture_badge')
        : $t('review.source.local_control_plane')}
    </span>
  </header>

  <dl class="identity-list">
    {#each rows as row}
      {@const key = row.key}
      {@const value = row.value}
      <div class="identity-row">
        <dt>{$t(row.labelKey)}</dt>
        <dd>
          <code class:value-unavailable={!value}>{value ?? $t('review.unavailable')}</code>
          {#if value}
            <button
              type="button"
              class="copy-button"
              aria-label={`${$t('review.copy')} ${$t(row.labelKey)}`}
              title={$t('review.copy')}
              onclick={() => void copyValue(key, value)}
              onkeydown={(event) => handleCopyKeydown(event, key, value)}
            >
              <Icon
                name={copyFeedback?.key === key
                  ? copyFeedback.outcome === 'success'
                    ? 'check'
                    : 'cancel'
                  : 'link'}
                size={16}
              />
              <span>
                {copyFeedback?.key === key
                  ? copyFeedback.outcome === 'success'
                    ? $t('review.copied')
                    : $t('review.copy_failed')
                  : $t('review.copy')}
              </span>
            </button>
          {/if}
        </dd>
      </div>
    {/each}
  </dl>
  <p
    class:copy-error={copyFeedback?.outcome === 'failure'}
    class="copy-announcement"
    aria-live="polite"
    aria-atomic="true"
  >
    {copyFeedback
      ? copyFeedback.outcome === 'success'
        ? $t('review.copy_success')
        : $t('review.copy_failure')
      : ''}
  </p>
</section>

<style>
  .review-panel {
    border: var(--border-thin);
    border-radius: var(--lc-radius-lg);
    background: var(--lc-panel);
    padding: var(--lc-space-4);
  }

  .panel-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--lc-space-3);
    margin-bottom: var(--lc-space-4);
  }

  .panel-eyebrow {
    margin: 0 0 4px;
    color: var(--lc-accent);
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.11em;
    text-transform: uppercase;
  }

  h2 {
    margin: 0;
    font-size: 16px;
  }

  .fixture-badge {
    border: 1px solid color-mix(in srgb, var(--lc-info) 45%, transparent);
    border-radius: 999px;
    color: var(--lc-info);
    padding: 4px 8px;
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
  }

  .source-badge {
    border: 1px solid color-mix(in srgb, var(--lc-accent) 45%, transparent);
    border-radius: 999px;
    color: var(--lc-accent);
    padding: 4px 8px;
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
  }

  .identity-list {
    display: grid;
    gap: var(--lc-space-2);
    margin: 0;
  }

  .identity-row {
    min-width: 0;
    display: grid;
    grid-template-columns: minmax(140px, 0.35fr) minmax(0, 1fr);
    align-items: start;
    gap: var(--lc-space-3);
    border-top: var(--border-thin);
    padding-top: var(--lc-space-2);
  }

  dt {
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 720;
  }

  dd {
    min-width: 0;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--lc-space-2);
    margin: 0;
  }

  code {
    min-width: 0;
    overflow-wrap: anywhere;
    color: var(--lc-text);
    font-family: var(--lc-mono);
    font-size: 11px;
    line-height: 1.55;
  }

  .value-unavailable {
    color: var(--lc-faint);
  }

  .copy-button {
    flex: 0 0 auto;
    min-height: 44px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-soft);
    color: var(--lc-muted);
    padding: 0 var(--lc-space-3);
    cursor: pointer;
  }

  .copy-button:hover {
    border-color: var(--lc-line-strong);
    color: var(--lc-accent);
  }

  .copy-button:focus-visible {
    outline: 1px solid var(--lc-accent);
    outline-offset: 2px;
    box-shadow: var(--focus-ring);
  }

  .copy-announcement {
    min-height: 1em;
    margin: var(--lc-space-2) 0 0;
    color: var(--lc-accent);
    font-size: 11px;
  }

  .copy-announcement.copy-error {
    color: var(--lc-danger);
  }

  @media (max-width: 760px) {
    .identity-row {
      grid-template-columns: 1fr;
    }

    dd {
      flex-direction: column;
    }

    .copy-button {
      width: 100%;
      justify-content: center;
    }
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/review/ReviewMetadataPanel.svelte (225 строк, 5124 байт)

````svelte
<script lang="ts">
  import { t } from '$lib/i18n';
  import {
    PROPOSED_CONTENT_FIELDS,
    type MetadataChange,
    type MetadataValue,
    type ProposedContentField,
    type ReviewCenterItem
  } from '$lib/types/knowledgeReview';

  export let review: ReviewCenterItem;

  function formatValue(value: MetadataValue): string {
    if (value === null) return 'null';
    if (typeof value === 'string') return value;
    if (typeof value === 'boolean') return value ? 'true' : 'false';
    return JSON.stringify(value);
  }

  function fieldValue(field: ProposedContentField): MetadataValue {
    return review.proposedContent[field];
  }

  function changeFor(field: ProposedContentField): MetadataChange | undefined {
    return review.metadataChanges.find((change) => change.field === field);
  }
</script>

<section class="review-panel" aria-labelledby="review-metadata-heading">
  <header class="panel-header">
    <div>
      <p class="panel-eyebrow">{$t('review.metadata.eyebrow')}</p>
      <h2 id="review-metadata-heading">{$t('review.metadata.title')}</h2>
    </div>
    <span class="field-count">
      {PROPOSED_CONTENT_FIELDS.length} {$t('review.metadata.fields')}
    </span>
  </header>

  <p class="metadata-note">{$t('review.metadata.projection_note')}</p>

  <dl class="metadata-list">
    {#each PROPOSED_CONTENT_FIELDS as field}
      {@const change = changeFor(field)}
      <div class:changed={Boolean(change)} class="metadata-row">
        <dt>
          <code>{field}</code>
          <span>{$t(`review.metadata.field.${field}`)}</span>
        </dt>
        <dd>
          <pre>{formatValue(fieldValue(field))}</pre>
          {#if change}
            <div class="change-detail" aria-label={$t('review.metadata.changed')}>
              <div>
                <span>{$t('review.metadata.before')}</span>
                <code>{formatValue(change.before)}</code>
              </div>
              <div>
                <span>{$t('review.metadata.after')}</span>
                <code>{formatValue(change.after)}</code>
              </div>
            </div>
          {/if}
        </dd>
      </div>
    {/each}
  </dl>
</section>

<style>
  .review-panel {
    border: var(--border-thin);
    border-radius: var(--lc-radius-lg);
    background: var(--lc-panel);
    padding: var(--lc-space-4);
  }

  .panel-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--lc-space-3);
    margin-bottom: var(--lc-space-3);
  }

  .panel-eyebrow {
    margin: 0 0 4px;
    color: var(--lc-accent);
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.11em;
    text-transform: uppercase;
  }

  h2 {
    margin: 0;
    font-size: 16px;
  }

  .field-count {
    color: var(--lc-muted);
    font-family: var(--lc-mono);
    font-size: 11px;
  }

  .metadata-note {
    margin: 0 0 var(--lc-space-4);
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-soft);
    color: var(--lc-muted);
    padding: var(--lc-space-3);
    font-size: 12px;
    line-height: 1.5;
  }

  .metadata-list {
    display: grid;
    gap: 0;
    margin: 0;
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    overflow: hidden;
  }

  .metadata-row {
    min-width: 0;
    display: grid;
    grid-template-columns: minmax(170px, 0.32fr) minmax(0, 1fr);
    gap: var(--lc-space-3);
    border-bottom: var(--border-thin);
    background: var(--lc-panel-solid);
    padding: var(--lc-space-3);
  }

  .metadata-row:last-child {
    border-bottom: 0;
  }

  .metadata-row.changed {
    box-shadow: inset 3px 0 0 var(--lc-warning);
  }

  dt,
  dd {
    min-width: 0;
    margin: 0;
  }

  dt {
    display: grid;
    align-content: start;
    gap: 4px;
  }

  dt code {
    color: var(--lc-text);
    font-family: var(--lc-mono);
    font-size: 11px;
    overflow-wrap: anywhere;
  }

  dt span {
    color: var(--lc-muted);
    font-size: 11px;
  }

  pre {
    max-height: 180px;
    overflow: auto;
    margin: 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    color: var(--lc-text);
    font-family: var(--lc-mono);
    font-size: 11px;
    line-height: 1.55;
  }

  .change-detail {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--lc-space-2);
    margin-top: var(--lc-space-3);
  }

  .change-detail > div {
    min-width: 0;
    display: grid;
    gap: 4px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-soft);
    padding: var(--lc-space-2);
  }

  .change-detail span {
    color: var(--lc-warning);
    font-size: 10px;
    font-weight: 800;
    text-transform: uppercase;
  }

  .change-detail code {
    overflow-wrap: anywhere;
    color: var(--lc-muted);
    font-family: var(--lc-mono);
    font-size: 10px;
  }

  @media (max-width: 760px) {
    .metadata-row {
      grid-template-columns: 1fr;
    }

    .change-detail {
      grid-template-columns: 1fr;
    }

    .panel-header {
      flex-direction: column;
    }
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/review/ReviewQueueSidebar.svelte (351 строк, 8930 байт)

````svelte
<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import { t } from '$lib/i18n';
  import {
    filteredReviewQueue,
    moveReviewSelection,
    reviewCenterState,
    reviewFilters,
    reviewQueue,
    selectReview,
    selectReviewBoundary,
    selectedReviewId
  } from '$lib/stores/reviewCenter';
  import type { ReviewStatus } from '$lib/types/knowledgeReview';

  function statusIcon(status: ReviewStatus): string {
    if (status === 'CLEAR') return 'check';
    if (status === 'BLOCKED') return 'cancel';
    return 'audit';
  }

  function handleQueueKey(event: KeyboardEvent): void {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      moveReviewSelection(1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      moveReviewSelection(-1);
    } else if (event.key === 'Home') {
      event.preventDefault();
      selectReviewBoundary('first');
    } else if (event.key === 'End') {
      event.preventDefault();
      selectReviewBoundary('last');
    } else {
      return;
    }

    requestAnimationFrame(() => {
      document
        .querySelector<HTMLButtonElement>('.review-queue-button[aria-current="true"]')
        ?.focus();
    });
  }

  $: filteredEmpty = $reviewQueue.length > 0 && $filteredReviewQueue.length === 0;
</script>

<div class="review-queue-mobile">
  <label for="review-queue-select">{$t('review.queue_mobile_label')}</label>
  <select
    id="review-queue-select"
    value={$selectedReviewId ?? ''}
    disabled={$filteredReviewQueue.length === 0}
    onchange={(event) => selectReview((event.currentTarget as HTMLSelectElement).value)}
  >
    {#if $filteredReviewQueue.length === 0}
      <option value="">
        {filteredEmpty ? $t('review.queue_filtered_empty') : $t('review.state.empty')}
      </option>
    {/if}
    {#each $filteredReviewQueue as review}
      <option value={review.id}>
        {$t(`review.status.${review.status}`)} — {review.targetStableId}
        {#if review.stale === true}— {$t('review.stale.badge')}{/if}
        {#if review.detailProjectionTruncated}— {$t('review.detail_truncated.badge')}{/if}
      </option>
    {/each}
  </select>
</div>

<nav class="review-queue" aria-label={$t('review.queue_label')}>
  <header class="queue-header">
    <div>
      <p class="eyebrow">{$t('review.queue_eyebrow')}</p>
      <h2>{$t('review.queue_title')}</h2>
    </div>
    <span class="queue-count" aria-label={$t('review.queue_visible_count')}>
      {$filteredReviewQueue.length}/{$reviewCenterState.totalCount}
    </span>
  </header>

  <p class="queue-help">{$t('review.queue_help')}</p>
  {#if $reviewCenterState.truncated}
    <p class="queue-truncated">
      {$t('review.queue_truncated')}
      {#if $reviewCenterState.nextOffset !== null}
        <code>{$reviewCenterState.nextOffset}</code>
      {/if}
    </p>
  {/if}

  {#if filteredEmpty}
    <p class="filtered-empty">
      {$t('review.queue_filtered_empty')}
      <span class="visually-hidden">{$reviewFilters.query}</span>
    </p>
  {/if}

  <div class="queue-list" role="listbox" aria-label={$t('review.queue_label')}>
    {#each $filteredReviewQueue as review (review.id)}
      <button
        type="button"
        class:active={$selectedReviewId === review.id}
        class="review-queue-button status-{review.status.toLowerCase()}"
        role="option"
        aria-selected={$selectedReviewId === review.id}
        aria-current={$selectedReviewId === review.id ? 'true' : undefined}
        onclick={() => selectReview(review.id)}
        onkeydown={handleQueueKey}
      >
        <span class="queue-status-icon" aria-hidden="true">
          <Icon name={statusIcon(review.status)} size={17} />
        </span>
        <span class="queue-copy">
          <span class="queue-status">{$t(`review.status.${review.status}`)}</span>
          <span class="queue-target">{review.targetStableId}</span>
          <span class="queue-operation">{review.operation}</span>
          {#if review.stale === true}
            <span class="stale-badge">{$t('review.stale.badge')}</span>
          {:else if review.stale === null}
            <span class="stale-badge">{$t('review.stale.unknown')}</span>
          {/if}
          {#if review.detailProjectionTruncated}
            <span class="detail-truncated-badge">{$t('review.detail_truncated.badge')}</span>
          {/if}
        </span>
        <span
          class:fixture-dot={review.fixture}
          class:source-dot={!review.fixture}
          title={review.fixture
            ? $t('review.fixture_badge')
            : $t('review.source.local_control_plane')}
          aria-hidden="true"
        ></span>
      </button>
    {/each}
  </div>
</nav>

<style>
  .review-queue {
    min-width: 0;
    min-height: 0;
    overflow: auto;
    border-right: var(--border-thin);
    background: var(--lc-panel);
    padding: var(--lc-space-4);
  }

  .queue-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--lc-space-3);
  }

  .eyebrow {
    margin: 0 0 4px;
    color: var(--lc-accent);
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.11em;
    text-transform: uppercase;
  }

  h2 {
    margin: 0;
    font-size: 16px;
  }

  .queue-count {
    display: grid;
    place-items: center;
    min-width: 28px;
    height: 28px;
    border: var(--border-thin);
    border-radius: 999px;
    color: var(--lc-muted);
    font-family: var(--lc-mono);
    font-size: 12px;
  }

  .queue-help {
    margin: var(--lc-space-3) 0;
    color: var(--lc-muted);
    font-size: 12px;
    line-height: 1.45;
  }

  .queue-truncated {
    margin: calc(var(--lc-space-2) * -1) 0 var(--lc-space-3);
    color: var(--lc-warning);
    font-size: 11px;
  }

  .queue-truncated code {
    font-family: var(--lc-mono);
  }

  .queue-list {
    display: grid;
    gap: var(--lc-space-2);
  }

  .review-queue-button {
    position: relative;
    min-height: 76px;
    width: 100%;
    display: grid;
    grid-template-columns: 24px minmax(0, 1fr) 8px;
    align-items: start;
    gap: var(--lc-space-2);
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    background: var(--lc-panel-soft);
    padding: var(--lc-space-3);
    text-align: left;
    cursor: pointer;
  }

  .review-queue-button:hover,
  .review-queue-button.active {
    border-color: var(--lc-line-strong);
    background: var(--lc-accent-dim);
  }

  .review-queue-button:focus-visible,
  .review-queue-mobile select:focus-visible {
    outline: 1px solid var(--lc-accent);
    outline-offset: 2px;
    box-shadow: var(--focus-ring);
  }

  .queue-status-icon {
    display: grid;
    place-items: center;
    width: 24px;
    height: 24px;
  }

  .status-clear .queue-status-icon {
    color: var(--lc-accent);
  }

  .status-review_required .queue-status-icon {
    color: var(--lc-warning);
  }

  .status-blocked .queue-status-icon {
    color: var(--lc-danger);
  }

  .queue-copy {
    min-width: 0;
    display: grid;
    gap: 4px;
  }

  .queue-status {
    color: var(--lc-text);
    font-size: 11px;
    font-weight: 820;
    letter-spacing: 0.05em;
  }

  .queue-target,
  .queue-operation {
    overflow-wrap: anywhere;
    color: var(--lc-muted);
    font-family: var(--lc-mono);
    font-size: 11px;
  }

  .detail-truncated-badge {
    width: fit-content;
    border: 1px solid color-mix(in srgb, var(--lc-warning) 48%, transparent);
    border-radius: 999px;
    color: var(--lc-warning);
    padding: 2px 7px;
    font-family: var(--lc-mono);
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 0.06em;
  }

  .fixture-dot {
    align-self: center;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--lc-info);
  }

  .source-dot {
    align-self: center;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--lc-accent);
  }

  .review-queue-mobile {
    display: none;
  }

  @media (max-width: 920px) {
    .review-queue {
      display: none;
    }

    .review-queue-mobile {
      display: grid;
      gap: var(--lc-space-2);
      border-bottom: var(--border-thin);
      background: var(--lc-panel);
      padding: var(--lc-space-3);
    }

    .review-queue-mobile label {
      color: var(--lc-muted);
      font-size: 12px;
      font-weight: 720;
    }

    .review-queue-mobile select {
      min-height: 44px;
      width: 100%;
      border: var(--border-thin);
      border-radius: var(--lc-radius-sm);
      background: var(--lc-panel-solid);
      color: var(--lc-text);
      padding: 0 var(--lc-space-3);
    }
  }

  .stale-badge {
    color: var(--lc-warning);
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
  }

  .filtered-empty {
    margin: var(--lc-space-3) 0;
    color: var(--lc-muted);
    font-size: 12px;
    line-height: 1.5;
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/review/ReviewTextDiffPanel.svelte (181 строк, 4333 байт)

````svelte
<script lang="ts">
  import { t } from '$lib/i18n';
  import type { ReviewCenterItem } from '$lib/types/knowledgeReview';

  export let review: ReviewCenterItem;
</script>

<section class="review-panel" aria-labelledby="review-diff-heading">
  <header class="panel-header">
    <div>
      <p class="panel-eyebrow">{$t('review.diff.eyebrow')}</p>
      <h2 id="review-diff-heading">{$t('review.diff.title')}</h2>
    </div>
    {#if review.textDiff.previewTruncated}
      <span class="truncated-badge">{$t('review.diff.truncated')}</span>
    {/if}
  </header>

  <p class="preview-contract">
    <strong>{$t('review.diff.preview_label')}</strong>
    <span>{$t('review.diff.not_full_diff')}</span>
  </p>

  {#if review.status === 'BLOCKED' || review.textDiff.preview === null}
    <div class="no-material">
      <strong>{$t('review.diff.no_material')}</strong>
      <span>{$t('review.diff.blocked_suppression')}</span>
    </div>
  {:else}
    <pre class="diff-preview" aria-label={$t('review.diff.preview_label')}>{review.textDiff.preview || $t('review.diff.empty')}</pre>
  {/if}

  <dl class="diff-meta">
    <div>
      <dt>{$t('review.diff.hash')}</dt>
      <dd><code>{review.textDiff.fullDiffHash ?? $t('review.unavailable')}</code></dd>
    </div>
    <div>
      <dt>{$t('review.diff.bytes')}</dt>
      <dd>{review.textDiff.fullDiffUtf8Bytes ?? $t('review.unavailable')}</dd>
    </div>
    <div>
      <dt>{$t('review.diff.full_available')}</dt>
      <dd>{review.textDiff.fullDiffAvailable ? $t('review.yes') : $t('review.no')}</dd>
    </div>
    <div>
      <dt>{$t('review.diff.preview_truncated')}</dt>
      <dd>{review.textDiff.previewTruncated ? $t('review.yes') : $t('review.no')}</dd>
    </div>
  </dl>
</section>

<style>
  .review-panel {
    min-width: 0;
    border: var(--border-thin);
    border-radius: var(--lc-radius-lg);
    background: var(--lc-panel);
    padding: var(--lc-space-4);
  }

  .panel-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--lc-space-3);
    margin-bottom: var(--lc-space-3);
  }

  .panel-eyebrow {
    margin: 0 0 4px;
    color: var(--lc-accent);
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.11em;
    text-transform: uppercase;
  }

  h2 {
    margin: 0;
    font-size: 16px;
  }

  .truncated-badge {
    border: 1px solid color-mix(in srgb, var(--lc-warning) 42%, transparent);
    border-radius: 999px;
    color: var(--lc-warning);
    padding: 4px 8px;
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
  }

  .preview-contract {
    display: flex;
    flex-wrap: wrap;
    gap: var(--lc-space-2);
    margin: 0 0 var(--lc-space-3);
    color: var(--lc-muted);
    font-size: 12px;
  }

  .preview-contract strong {
    color: var(--lc-text);
  }

  .diff-preview {
    min-height: 96px;
    max-height: 420px;
    overflow: auto;
    margin: 0;
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    background: var(--color-code);
    color: var(--lc-text);
    padding: var(--lc-space-3);
    white-space: pre;
    font-family: var(--lc-mono);
    font-size: 11px;
    line-height: 1.55;
  }

  .no-material {
    display: grid;
    gap: 6px;
    border: 1px solid color-mix(in srgb, var(--lc-danger) 38%, transparent);
    border-radius: var(--lc-radius-md);
    background: color-mix(in srgb, var(--lc-danger) 7%, transparent);
    color: var(--lc-muted);
    padding: var(--lc-space-3);
    font-size: 12px;
  }

  .no-material strong {
    color: var(--lc-danger);
  }

  .diff-meta {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--lc-space-3);
    margin: var(--lc-space-4) 0 0;
  }

  .diff-meta > div {
    min-width: 0;
    border-top: var(--border-thin);
    padding-top: var(--lc-space-2);
  }

  dt {
    margin-bottom: 4px;
    color: var(--lc-muted);
    font-size: 11px;
  }

  dd {
    min-width: 0;
    overflow-wrap: anywhere;
    margin: 0;
    color: var(--lc-text);
    font-size: 11px;
  }

  code {
    overflow-wrap: anywhere;
    font-family: var(--lc-mono);
    font-size: 10px;
  }

  @media (max-width: 760px) {
    .diff-meta {
      grid-template-columns: 1fr;
    }

    .diff-preview {
      max-height: 320px;
    }
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/review/ReviewValidationPanel.svelte (190 строк, 4324 байт)

````svelte
<script lang="ts">
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import { t } from '$lib/i18n';
  import type { ReviewCenterItem } from '$lib/types/knowledgeReview';

  export let review: ReviewCenterItem;

  $: validationTone =
    review.validation.outcome === 'VALID'
      ? 'ready'
      : review.validation.outcome === 'STALE'
        ? 'waiting'
        : 'danger';
</script>

<section class="review-panel" aria-labelledby="review-validation-heading">
  <header class="panel-header">
    <div>
      <p class="panel-eyebrow">{$t('review.validation.eyebrow')}</p>
      <h2 id="review-validation-heading">{$t('review.validation.title')}</h2>
    </div>
    <StatusBadge
      label={$t(`review.validation.outcome.${review.validation.outcome}`)}
      tone={validationTone}
    />
  </header>

  <dl class="validation-grid">
    <div>
      <dt>{$t('review.validation.contract')}</dt>
      <dd><code>{review.validation.contractVersion}</code></dd>
    </div>
    <div>
      <dt>{$t('review.validation.content_hash')}</dt>
      <dd><code>{review.validation.proposalContentHash}</code></dd>
    </div>
    <div>
      <dt>{$t('review.validation.validated_revision')}</dt>
      <dd><code>{review.validation.validatedVaultRevision}</code></dd>
    </div>
    <div>
      <dt>{$t('review.validation.snapshot')}</dt>
      <dd>{review.validation.snapshotSummary}</dd>
    </div>
  </dl>

  {#if review.validation.snapshotTruncated}
    <p class="truncation-notice">
      {$t('review.validation.snapshot_truncated')}
    </p>
  {/if}

  <section class="source-findings" aria-labelledby="review-source-findings-heading">
    <h3 id="review-source-findings-heading">{$t('review.validation.source_findings')}</h3>
    {#if review.validation.sourceFindings.length === 0}
      <p>{$t('review.none')}</p>
    {:else}
      <ul>
        {#each review.validation.sourceFindings as sourceFinding}
          <li>
            <code>{sourceFinding[0]}</code>
            <span>{sourceFinding[1]}</span>
          </li>
        {/each}
      </ul>
    {/if}
  </section>
</section>

<style>
  .review-panel {
    border: var(--border-thin);
    border-radius: var(--lc-radius-lg);
    background: var(--lc-panel);
    padding: var(--lc-space-4);
  }

  .panel-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--lc-space-3);
    margin-bottom: var(--lc-space-4);
  }

  .panel-eyebrow {
    margin: 0 0 4px;
    color: var(--lc-accent);
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.11em;
    text-transform: uppercase;
  }

  h2,
  h3 {
    margin: 0;
  }

  h2 {
    font-size: 16px;
  }

  h3 {
    font-size: 13px;
  }

  .validation-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--lc-space-3);
    margin: 0;
  }

  .validation-grid > div {
    min-width: 0;
    border-top: var(--border-thin);
    padding-top: var(--lc-space-2);
  }

  dt {
    margin-bottom: 6px;
    color: var(--lc-muted);
    font-size: 11px;
    font-weight: 720;
  }

  dd {
    min-width: 0;
    overflow-wrap: anywhere;
    margin: 0;
    color: var(--lc-text);
    font-size: 12px;
    line-height: 1.5;
  }

  code {
    overflow-wrap: anywhere;
    font-family: var(--lc-mono);
    font-size: 11px;
  }

  .truncation-notice {
    border: 1px solid color-mix(in srgb, var(--lc-warning) 38%, transparent);
    border-radius: var(--lc-radius-sm);
    background: color-mix(in srgb, var(--lc-warning) 8%, transparent);
    color: var(--lc-warning);
    padding: var(--lc-space-3);
    font-size: 12px;
  }

  .source-findings {
    margin-top: var(--lc-space-4);
    border-top: var(--border-thin);
    padding-top: var(--lc-space-3);
  }

  .source-findings p {
    color: var(--lc-muted);
    font-size: 12px;
  }

  ul {
    display: grid;
    gap: var(--lc-space-2);
    margin: var(--lc-space-2) 0 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: flex;
    flex-wrap: wrap;
    gap: var(--lc-space-2);
    color: var(--lc-muted);
    font-size: 11px;
  }

  @media (max-width: 760px) {
    .validation-grid {
      grid-template-columns: 1fr;
    }

    .panel-header {
      align-items: stretch;
      flex-direction: column;
    }
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/shell/AgentInspector.svelte (202 строк, 4487 байт)

````svelte
<script lang="ts">
  import { DESKTOP_SHELL_VERSION } from '$lib/version';
  import { inspectorMock, inspectorSections } from '$lib/data/mockData';
  import { activeInspectorSection, inspectorVisible, setActiveInspectorSection } from '$lib/stores/shellStore';
  import type { InspectorSection } from '$lib/data/mockData';

  export let className = '';
  export let onClose: () => void = () => undefined;
</script>

<aside class="inspector {className}" class:hidden={!$inspectorVisible && !className} aria-label="Agent Inspector">
  <header>
    <div>
      <span class="eyebrow">Agent Inspector</span>
      <h2>{inspectorMock.status}</h2>
    </div>
    <button type="button" class="plain-button close-button" aria-label="Close Agent Inspector" onclick={onClose}>Close</button>
  </header>

  <div class="tabs" role="tablist" aria-label="Inspector sections">
    {#each inspectorSections as section}
      <button
        type="button"
        class="section-tab"
        role="tab"
        aria-selected={$activeInspectorSection === section}
        onclick={() => setActiveInspectorSection(section as InspectorSection)}
      >
        {section}
      </button>
    {/each}
  </div>

  <section class="overview" aria-label="Agent status overview">
    <dl>
      <div><dt>Status</dt><dd>{inspectorMock.status}</dd></div>
      <div><dt>Autonomy</dt><dd>{inspectorMock.autonomy}</dd></div>
      <div><dt>Risk</dt><dd class="risk">{inspectorMock.risk}</dd></div>
      <div><dt>Actions used</dt><dd>{inspectorMock.actionsUsed}</dd></div>
      <div><dt>Runtime</dt><dd>{inspectorMock.runtime}</dd></div>
      <div><dt>Kill switch</dt><dd>{inspectorMock.killSwitch}</dd></div>
    </dl>
  </section>

  <section aria-label="Plan">
    <h3>Plan</h3>
    <ol>
      {#each inspectorMock.planSteps as step}
        <li>{step}</li>
      {/each}
    </ol>
  </section>

  <section aria-label="Actions">
    <h3>Actions</h3>
    {#each inspectorMock.actions as action}
      <div class="action-row">
        <span>{action.label}</span>
        <strong>{action.state}</strong>
      </div>
    {/each}
  </section>

  <section aria-label="Deferred entries">
    <h3>Reserved</h3>
    <div class="reserved-grid">
      {#each inspectorMock.reserved as item}
        <div class="reserved-item">
          <strong>{item.label}</strong>
          <span>{item.state}</span>
        </div>
      {/each}
    </div>
  </section>

  <footer aria-label="About desktop shell">
    <span>Desktop shell {DESKTOP_SHELL_VERSION}</span>
  </footer>
</aside>

<style>
  .inspector {
    width: var(--inspector-width);
    min-width: var(--inspector-width);
    overflow-y: auto;
    border-left: var(--border-thin);
    border-right: 0;
    padding: var(--space-4);
  }

  .inspector.hidden {
    display: none;
  }

  header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
  }

  .eyebrow,
  dt,
  footer {
    color: var(--color-muted);
    font-size: 12px;
    font-weight: 700;
  }

  h2,
  h3 {
    margin: var(--space-1) 0 0;
  }

  h2 {
    font-size: 18px;
  }

  h3 {
    margin-top: var(--space-5);
    font-size: 14px;
  }

  .close-button {
    padding: 0 var(--space-3);
  }

  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin: var(--space-4) 0;
  }

  .section-tab {
    min-height: 34px;
    padding: 0 var(--space-3);
    color: var(--color-muted);
  }

  .section-tab[aria-selected='true'] {
    background: var(--color-accent-soft);
    color: var(--color-accent);
  }

  dl {
    display: grid;
    gap: var(--space-2);
    margin: 0;
  }

  dl div,
  .action-row,
  .reserved-item {
    display: flex;
    justify-content: space-between;
    gap: var(--space-3);
    border: var(--border-thin);
    border-radius: var(--radius-2);
    background: var(--color-elevated);
    padding: var(--space-3);
  }

  dd {
    margin: 0;
    font-weight: 800;
  }

  .risk {
    color: var(--risk-medium);
  }

  ol {
    margin: var(--space-3) 0 0;
    padding-left: var(--space-5);
  }

  li + li {
    margin-top: var(--space-2);
  }

  .action-row + .action-row {
    margin-top: var(--space-2);
  }

  .action-row strong,
  .reserved-item span {
    color: var(--color-muted);
    font-size: 12px;
  }

  .reserved-grid {
    display: grid;
    gap: var(--space-2);
  }

  footer {
    margin-top: var(--space-6);
    border-top: var(--border-thin);
    padding-top: var(--space-4);
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/shell/AppShell.svelte (279 строк, 9541 байт)

````svelte
<script lang="ts">
  import { onMount, tick } from 'svelte';
  import '../../../app.css';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import CommandPalette from '$lib/components/common/CommandPalette.svelte';
  import Diagnostics from '$lib/components/agent/Diagnostics.svelte';
  import ChatHeader from './ChatHeader.svelte';
  import ConversationSidebar from './ConversationSidebar.svelte';
  import NavigationRail from './NavigationRail.svelte';
  import SettingsPanel from './SettingsPanel.svelte';
  import MessageComposer from '$lib/components/chat/MessageComposer.svelte';
  import MessageList from '$lib/components/chat/MessageList.svelte';
  import ModelSetupDrawer from '$lib/components/model/ModelSetupDrawer.svelte';
  import ReviewCenterWorkspace from '$lib/components/review/ReviewCenterWorkspace.svelte';
  import OnboardingScreen from '$lib/components/onboarding/OnboardingScreen.svelte';
  import {
    activeWorkspace,
    chatMessages,
    closeDiagnosticsPanel,
    closeModelSetup,
    closeSettings,
    handleGlobalEscape,
    inspectorDrawerOpen,
    inspectorVisible,
    modelSetupDrawerOpen,
    openCommandPalette,
    openSettings,
    settingsPanelOpen,
    sidebarExpanded,
    themeMode
  } from '$lib/stores/shellStore';
  import { controlPlaneStore, initializeControlPlaneBridge, shutdownControlPlaneBridge } from '$lib/stores/controlPlane';
  import { initializeModelGateway, shutdownModelGateway } from '$lib/stores/modelGateway';
  import { initializeArtifactAcquisition, resetArtifactAcquisitionStore } from '$lib/stores/artifactAcquisition';
  import { initializeKnowledgePreviewEvents, shutdownKnowledgePreviewEvents } from '$lib/stores/knowledgePreview';
  import { locale, t } from '$lib/i18n';
  import type { ResolvedTheme } from '$lib/data/mockData';
  import { followTranscriptToEnd, isTranscriptNearBottom } from '$lib/components/chat/transcriptScroll';

  let systemDark = false;
  let resolvedTheme: ResolvedTheme = 'light';
  let transcriptViewport: HTMLDivElement;
  let followTranscript = true;
  let transcriptRevision = 0;

  function recordTranscriptPosition(): void {
    if (!transcriptViewport) return;
    followTranscript = isTranscriptNearBottom(transcriptViewport);
  }

  function handleTranscriptKeydown(event: KeyboardEvent): void {
    if (!transcriptViewport) return;
    const page = Math.max(40, Math.floor(transcriptViewport.clientHeight * 0.9));
    if (event.key === 'PageUp') {
      event.preventDefault();
      transcriptViewport.scrollTop = Math.max(0, transcriptViewport.scrollTop - page);
    } else if (event.key === 'PageDown') {
      event.preventDefault();
      transcriptViewport.scrollTop = Math.min(
        transcriptViewport.scrollHeight,
        transcriptViewport.scrollTop + page
      );
    } else if (event.key === 'Home') {
      event.preventDefault();
      transcriptViewport.scrollTop = 0;
    } else if (event.key === 'End') {
      event.preventDefault();
      transcriptViewport.scrollTop = transcriptViewport.scrollHeight;
    } else {
      return;
    }
    recordTranscriptPosition();
  }

  async function revealLatestTranscriptContent(): Promise<void> {
    if (!transcriptViewport || !followTranscript) return;
    await tick();
    if (!transcriptViewport || !followTranscript) return;
    followTranscriptToEnd(transcriptViewport, true);
  }

  function closeSettingsAndRestoreFocus(): void {
    closeSettings();
    queueMicrotask(() => {
      document.querySelector<HTMLButtonElement>('[data-settings-trigger]')?.focus();
    });
  }

  $: resolvedTheme = $themeMode === 'system' ? (systemDark ? 'dark' : 'light') : $themeMode;
  $: transcriptRevision = $chatMessages.reduce(
    (revision, message) => revision + message.body.length + (message.state?.length ?? 0),
    $chatMessages.length
  );
  $: if (transcriptViewport && transcriptRevision >= 0) {
    void revealLatestTranscriptContent();
  }

  onMount(() => {
    const media = window.matchMedia?.('(prefers-color-scheme: dark)');
    if (media) {
      systemDark = media.matches;
      const update = (event: MediaQueryListEvent) => {
        systemDark = event.matches;
      };
      media.addEventListener('change', update);
      return () => media.removeEventListener('change', update);
    }
    return undefined;
  });

  onMount(() => {
    const media = window.matchMedia?.('(max-width: 920px)');
    if (!media) return undefined;
    const update = (matches: boolean) => {
      if (matches) sidebarExpanded.set(false);
    };
    update(media.matches);
    const listener = (event: MediaQueryListEvent) => update(event.matches);
    media.addEventListener('change', listener);
    return () => media.removeEventListener('change', listener);
  });

  onMount(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        openCommandPalette();
        return;
      }
      if (event.ctrlKey && !event.altKey && !event.shiftKey && event.key === ',') {
        event.preventDefault();
        openSettings();
        return;
      }
      if (event.key === 'Escape' && $settingsPanelOpen) {
        event.preventDefault();
        closeSettingsAndRestoreFocus();
        return;
      }
      if (handleGlobalEscape(event.key)) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  });

  onMount(() => {
    void initializeControlPlaneBridge();
    void initializeModelGateway();
    void initializeArtifactAcquisition();
    void initializeKnowledgePreviewEvents();
    document.documentElement.lang = $locale;
    return () => {
      shutdownModelGateway();
      resetArtifactAcquisitionStore();
      shutdownKnowledgePreviewEvents();
      shutdownControlPlaneBridge();
    };
  });

  $: controlPlaneLabel =
    $controlPlaneStore.bridgeState === 'READY'
      ? $t('diag.control_plane_connected')
      : $controlPlaneStore.bridgeState === 'CONNECTING'
        ? $t('diag.control_plane_starting')
        : $controlPlaneStore.bridgeState === 'UNAVAILABLE'
          ? $t('diag.control_plane_unavailable')
          : $controlPlaneStore.bridgeState === 'ERROR'
            ? $t('diag.control_plane_error')
            : $t('diag.control_plane_unknown');
  $: controlPlaneTone =
    $controlPlaneStore.bridgeState === 'READY'
      ? 'ready'
      : $controlPlaneStore.bridgeState === 'CONNECTING'
        ? 'info'
        : $controlPlaneStore.bridgeState === 'ERROR'
          ? 'danger'
          : $controlPlaneStore.bridgeState === 'UNAVAILABLE'
            ? 'disabled'
            : 'unknown';
</script>

<div class="app-shell" data-theme={resolvedTheme}>
  <a
    class="skip-link"
    href={$activeWorkspace === 'review' ? '#review-workspace' : $activeWorkspace === 'setup' ? '#setup-workspace' : '#chat-workspace'}
  >
    {$activeWorkspace === 'review' ? $t('review.skip_link') : $activeWorkspace === 'setup' ? $t('onboarding.skip_link') : $t('common.skip_link')}
  </a>
  <NavigationRail />
  <header class="title-bar" aria-label={$t('app.title_bar')}>
    <div class="palette-hint" aria-hidden="true">
      <kbd>Ctrl</kbd><kbd>K</kbd><span>{$t('commandPalette.search')}</span>
    </div>
    <StatusBadge label={controlPlaneLabel} tone={controlPlaneTone} />
  </header>

  <div
    class:focused-mode={$activeWorkspace !== 'chat'}
    class:diagnostics-open={$activeWorkspace === 'chat' && $inspectorVisible}
    class="shell-body"
  >
    {#if $activeWorkspace === 'chat'}
      <ConversationSidebar />
      <main id="chat-workspace" class="main-workspace" aria-label="LocalComet chat workspace">
        <ChatHeader />
        <!-- svelte-ignore a11y_no_noninteractive_tabindex a11y_no_noninteractive_element_interactions (the transcript viewport must receive native scroll keys) -->
        <div
          class="chat-scroll"
          bind:this={transcriptViewport}
          role="region"
          tabindex="0"
          aria-label={$t('chat.message_history')}
          onscroll={recordTranscriptPosition}
          onkeydown={handleTranscriptKeydown}
        >
          <div class="content-column">
            <MessageList />
          </div>
        </div>
        <MessageComposer />
      </main>
      <Diagnostics className={$inspectorDrawerOpen ? 'drawer-open' : ''} onClose={closeDiagnosticsPanel} />
      {#if $modelSetupDrawerOpen}
        <ModelSetupDrawer onClose={closeModelSetup} />
      {/if}
    {:else if $activeWorkspace === 'review'}
      <ReviewCenterWorkspace />
    {:else}
      <OnboardingScreen />
    {/if}
  </div>

  {#if $settingsPanelOpen}
    <SettingsPanel onClose={closeSettingsAndRestoreFocus} />
  {/if}
  <CommandPalette />
</div>

<style>
  .app-shell {
    height: 100dvh;
    max-height: 100dvh;
    overflow: hidden;
  }

  .shell-body {
    min-width: 0;
    min-height: 0;
    overflow: hidden;
  }

  .main-workspace {
    min-width: 0;
    min-height: 0;
    height: 100%;
    grid-template-rows: auto minmax(0, 1fr) auto;
    overflow: hidden;
  }

  .chat-scroll {
    min-width: 0;
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
    overscroll-behavior: contain;
    scrollbar-gutter: stable;
  }

  .content-column {
    min-width: 0;
  }

  .shell-body.focused-mode {
    grid-template-columns: minmax(0, 1fr);
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/shell/ChatHeader.svelte (219 строк, 6389 байт)

````svelte
<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import { conversationTitleById } from '$lib/data/mockData';
  import { approvedManagedModelInstalled, connectSelectedManagedModel, inferenceRequestStore, managedConnectionBusy, managedModelReady, managedRuntimeStore, modelGatewayStore } from '$lib/stores/modelGateway';
  import { selectedConversationId, sidebarExpanded, openModelSetup, modelSetupDrawerOpen, inspectorVisible, inspectorDrawerOpen, openSettings, setDiagnosticsPanelOpen } from '$lib/stores/shellStore';
  import { t } from '$lib/i18n';

  $: title = (() => {
    const raw = conversationTitleById($selectedConversationId);
    const v = $t('item.' + raw);
    return v.startsWith('item.') ? raw : v;
  })();

  // Connection summary for header
  $: connectionSummary = (() => {
    if (['submitted', 'accepted', 'streaming', 'cancelling'].includes($inferenceRequestStore.lifecycle)) return { label: $t('conn.request_generating'), tone: 'info' as const };
    if ($inferenceRequestStore.lifecycle === 'failed' || $inferenceRequestStore.lifecycle === 'timed_out' || $modelGatewayStore.status === 'Failed') return { label: $t('conn.request_error'), tone: 'danger' as const };
    if ($managedModelReady) return { label: $t('conn.model_ready'), tone: 'ready' as const };
    if ($managedRuntimeStore.lastError || $managedRuntimeStore.status?.last_error || $managedRuntimeStore.status?.state === 'Failed') return { label: $t('conn.model_error'), tone: 'danger' as const };
    if ($managedConnectionBusy || ['Validating', 'Starting', 'Stopping'].includes($managedRuntimeStore.status?.state ?? '') || ['Validating', 'Loading', 'Unloading'].includes($managedRuntimeStore.status?.model_state ?? '')) return { label: $t('conn.model_loading'), tone: 'info' as const };
    return { label: $t('conn.model_unavailable'), tone: 'disabled' as const };
  })();
  $: safeModelIdentity = $managedRuntimeStore.status?.model_display_name ?? $managedRuntimeStore.status?.model_id ?? '';

  async function connectManagedModel(): Promise<void> {
    openModelSetup('managed');
    await connectSelectedManagedModel();
  }

</script>

<header class="chat-header">
  <button
    type="button"
    class="icon-button sidebar-toggle"
    aria-label={$t('sidebar.toggle')}
    title={$t('sidebar.toggle')}
    aria-expanded={$sidebarExpanded}
    onclick={() => sidebarExpanded.update((value) => !value)}
  >
    <Icon name="menu" />
  </button>

  <div class="title-block">
    <h1>{title}</h1>
  </div>

  <div class="connection-summary" aria-label={$t('conn.status')}>
    <StatusBadge label={connectionSummary.label} tone={connectionSummary.tone} />
  </div>

  <div class="header-actions">
    {#if !$managedModelReady}
      <button
        type="button"
        class="primary-button"
        onclick={() => $approvedManagedModelInstalled ? void connectManagedModel() : openSettings('models')}
        disabled={$managedConnectionBusy}
        aria-expanded={$modelSetupDrawerOpen}
        aria-controls="model-setup-drawer"
      >
        <Icon name="link" size={16} />
        <span>{$t($managedConnectionBusy ? 'chat.model_connecting' : $approvedManagedModelInstalled ? 'chat.connect_model' : 'chat.setup_local_ai')}</span>
      </button>
    {:else}
      <div class="ready-details" title={safeModelIdentity}>
        <StatusBadge label={$t('conn.runtime_ready')} tone="ready" />
        <span>{safeModelIdentity}</span>
      </div>
    {/if}

    <button
      type="button"
      class="icon-button"
      aria-label={$t('diag.toggle')}
      title={$t('diag.toggle')}
      aria-expanded={$inspectorVisible || $inspectorDrawerOpen}
      onclick={() => {
        const next = !($inspectorVisible || $inspectorDrawerOpen);
        setDiagnosticsPanelOpen(next);
      }}
    >
      <Icon name="inspector" />
    </button>
  </div>
</header>

<style>
  .chat-header {
    min-height: 48px;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto auto;
    align-items: center;
    gap: 8px;
    border-bottom: var(--border-thin);
    background: color-mix(in srgb, var(--lc-bg-elevated) 64%, transparent);
    padding: 8px 16px;
    backdrop-filter: blur(12px);
  }

  .icon-button {
    width: 32px;
    height: 32px;
    min-height: 32px;
    display: grid;
    place-items: center;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: transparent;
    color: var(--lc-muted);
  }

  .icon-button:hover {
    background: var(--lc-panel-soft);
    border-color: var(--lc-line);
    color: var(--lc-text);
  }

  .sidebar-toggle {
    display: none;
  }

  .title-block {
    min-width: 0;
  }

  h1 {
    margin: 0;
    overflow: hidden;
    font-size: 16px;
    font-weight: 700;
    color: var(--lc-text);
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .connection-summary {
    display: flex;
    align-items: center;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: var(--lc-space-2);
  }

  .ready-details {
    min-width: 0;
    display: flex;
    align-items: center;
    gap: var(--lc-space-2);
  }

  .ready-details > span {
    max-width: 150px;
    overflow: hidden;
    color: var(--lc-muted);
    font-size: 12px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .primary-button {
    display: inline-flex;
    align-items: center;
    gap: var(--lc-space-2);
    min-height: 32px;
    padding: 0 12px;
    border: none;
    border-radius: var(--lc-radius-sm);
    background: var(--lc-accent);
    color: var(--lc-logo-cut);
    font-weight: 650;
    font-size: 13px;
    cursor: pointer;
  }

  .primary-button:hover {
    background: var(--lc-accent-strong);
  }

  .primary-button:disabled {
    cursor: wait;
    opacity: 0.7;
  }

  .primary-button:focus-visible {
    outline: none;
    box-shadow: var(--focus-ring);
  }

  @media (max-width: 680px) {
    .chat-header {
      grid-template-columns: auto minmax(0, 1fr) auto;
      min-height: 48px;
      padding-inline: 12px;
    }

    .primary-button span {
      display: none;
    }

    .primary-button {
      padding: 0 var(--lc-space-2);
    }

    .ready-details > span {
      display: none;
    }
  }

  @media (max-width: 920px) {
    .sidebar-toggle {
      display: grid;
    }
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/shell/ConversationSidebar.svelte (133 строк, 3614 байт)

````svelte
<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import { conversationGroups } from '$lib/data/mockData';
  import { selectedConversationId, setSelectedConversation, sidebarExpanded } from '$lib/stores/shellStore';
  import { t } from '$lib/i18n';

  const hiddenConversationGroupLabels = new Set(['reserved', 'disabled']);
  const visibleConversationGroups = conversationGroups
    .filter((group) => !hiddenConversationGroupLabels.has(group.label))
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => item.id !== 'cancellation-demo')
    }))
    .filter((group) => group.items.length > 0);

  type Translate = (key: string) => string;

  function tGroup(label: string, translate: Translate): string {
    const v = translate('group.' + label);
    return v.startsWith('group.') ? label : v;
  }

  function tItem(value: string, translate: Translate): string {
    const v = translate('item.' + value);
    return v.startsWith('item.') ? value : v;
  }

</script>

<aside class="sidebar" class:sidebar-open={$sidebarExpanded} aria-label={$t('sidebar.label')}>
  <div class="sidebar-top">
    <button
      type="button"
      class="plain-button collapse-button"
      aria-label={$t('sidebar.collapse')}
      aria-expanded={$sidebarExpanded}
      onclick={() => sidebarExpanded.update((value) => !value)}
    >
      <Icon name={$sidebarExpanded ? 'collapse' : 'expand'} size={18} />
    </button>
  </div>

  <div class="conversation-groups">
    {#each visibleConversationGroups as group}
      <section aria-label={tGroup(group.label, $t)}>
        <h2>{tGroup(group.label, $t)}</h2>
        {#each group.items as item}
          <button
            type="button"
            class="conversation-button"
            class:selected={$selectedConversationId === item.id}
            aria-current={$selectedConversationId === item.id ? 'page' : undefined}
            onclick={() => setSelectedConversation(item.id)}
          >
            <span>{tItem(item.title, $t)}</span>
          </button>
        {/each}
      </section>
    {/each}
  </div>
</aside>

<style>
  .sidebar {
    width: var(--sidebar-width);
    min-width: var(--sidebar-width);
    display: flex;
    flex-direction: column;
    padding: 8px;
    overflow-y: auto;
    transition: transform var(--lc-transition-normal);
  }

  .sidebar-top {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    min-height: 36px;
  }

  .collapse-button {
    width: 34px;
    min-height: 34px;
    display: grid;
    place-items: center;
  }

  h2 {
    margin: 12px 8px 6px;
    color: var(--lc-faint);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .conversation-button {
    width: 100%;
    min-height: 34px;
    display: block;
    text-align: left;
    padding: 6px 8px;
    color: var(--lc-muted);
    font-size: 12.5px;
    font-weight: 560;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .conversation-button.selected {
    background: var(--lc-accent-dim);
    border-color: transparent;
    color: var(--lc-accent);
  }

  @media (max-width: 920px) {
    .sidebar:not(.sidebar-open) {
      display: none;
    }

    .sidebar.sidebar-open {
      position: fixed;
      top: var(--shell-header-height);
      left: var(--rail-width);
      z-index: 35;
      display: flex;
      width: min(var(--sidebar-width), calc(100vw - var(--rail-width)));
      height: calc(100vh - var(--shell-header-height));
      box-shadow: var(--lc-shadow);
    }
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/shell/NavigationRail.svelte (163 строк, 3636 байт)

````svelte
<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import LocalCometLogo from '$lib/components/common/LocalCometLogo.svelte';
  import { t } from '$lib/i18n';
  import {
    activeWorkspace,
    closeSettings,
    openSettings,
    setActiveWorkspace,
    settingsPanelOpen
  } from '$lib/stores/shellStore';

  function openChat(): void {
    closeSettings();
    setActiveWorkspace('chat');
  }

  function openSetup(): void {
    closeSettings();
    setActiveWorkspace('setup');
  }

</script>

<nav class="rail" aria-label={$t('nav.main')}>
  <div class="rail-mark" title="LocalComet">
    <LocalCometLogo size={26} />
    <span class="rail-wordmark"><span>Local</span>Comet</span>
  </div>
  <div class="rail-group">
    <button
      type="button"
      class="rail-button"
      aria-label={$t('nav.chat')}
      aria-current={$activeWorkspace === 'chat' && !$settingsPanelOpen ? 'page' : undefined}
      title={$t('nav.chat')}
      onclick={openChat}
    >
      <Icon name="chat" />
      <span class="rail-label">{$t('nav.chat')}</span>
    </button>
    <button
      type="button"
      class="rail-button"
      aria-label={$t('nav.setup')}
      aria-current={$activeWorkspace === 'setup' && !$settingsPanelOpen ? 'page' : undefined}
      title={$t('nav.setup')}
      onclick={openSetup}
    >
      <Icon name="spark" />
      <span class="rail-label">{$t('nav.setup')}</span>
    </button>
  </div>
  <div class="rail-group rail-bottom">
    <button
      type="button"
      class="rail-button"
      aria-label={$t('nav.settings')}
      aria-current={$settingsPanelOpen ? 'page' : undefined}
      title={$t('nav.settings')}
      data-settings-trigger="true"
      onclick={openSettings}
    >
      <Icon name="settings" />
      <span class="rail-label">{$t('nav.settings')}</span>
    </button>
  </div>
</nav>

<style>
  .rail {
    grid-column: 1;
    grid-row: 1 / 3;
    width: var(--rail-width);
    min-width: var(--rail-width);
    display: flex;
    flex-direction: column;
    border-right: var(--border-thin);
    background: color-mix(in srgb, var(--lc-bg-elevated) 82%, transparent);
    backdrop-filter: blur(12px);
  }

  .rail-mark {
    height: var(--shell-header-height);
    display: flex;
    align-items: center;
    gap: 10px;
    border-bottom: var(--border-thin);
    padding: 0 20px;
  }

  .rail-wordmark {
    min-width: 0;
    color: var(--lc-accent);
    font-family: Sora, Inter, "Segoe UI", system-ui, sans-serif;
    font-size: 15px;
    font-weight: 800;
    letter-spacing: -0.025em;
    white-space: nowrap;
  }

  .rail-wordmark span {
    color: var(--lc-text);
  }

  .rail-group {
    display: grid;
    gap: 2px;
    padding: 8px 12px;
  }

  .rail-bottom {
    margin-top: auto;
    border-top: var(--border-thin);
  }

  .rail-button {
    position: relative;
    width: 100%;
    min-height: 36px;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0 12px;
    color: var(--lc-muted);
    font-size: 13.5px;
    font-weight: 600;
    text-align: left;
  }

  .rail-button[aria-current='page'] {
    background: var(--lc-accent-dim);
    color: var(--lc-accent);
    border-color: transparent;
  }

  .rail-button:focus-visible {
    outline: none;
    box-shadow: var(--focus-ring);
  }

  @media (max-width: 1279px) {
    .rail-mark {
      justify-content: center;
      padding: 0;
    }

    .rail-wordmark,
    .rail-label {
      display: none;
    }

    .rail-group {
      padding: 8px 4px;
    }

    .rail-button {
      justify-content: center;
      min-height: 44px;
      padding: 0;
    }
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/components/shell/SettingsPanel.svelte (494 строк, 13144 байт)

````svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import ModelManagerSection from '$lib/components/model/ModelManagerSection.svelte';
  import ObservabilityRoom from '$lib/components/logs/ObservabilityRoom.svelte';
  import { controlPlaneStore } from '$lib/stores/controlPlane';
  import {
    inspectorDrawerOpen,
    inspectorVisible,
    setDiagnosticsPanelOpen,
    settingsSection,
    setThemeMode,
    themeMode
  } from '$lib/stores/shellStore';
  import { locale, setLocale, t, type Language } from '$lib/i18n';
  import type { ThemeMode } from '$lib/data/mockData';
  import {
    DESKTOP_BUILD_LABEL,
    DESKTOP_BUILD_STATUS,
    DESKTOP_SHELL_VERSION
  } from '$lib/version';
  import { filesCapabilityAvailable, initializeFilesCapability } from '$lib/stores/files';

  export let onClose: () => void = () => undefined;

  let closeButton: HTMLButtonElement;

  const sections = [
    { id: 'interface', labelKey: 'settings.tab_interface' },
    { id: 'models', labelKey: 'settings.tab_models' },
    { id: 'observability', labelKey: 'settings.tab_observability' },
    { id: 'about', labelKey: 'settings.tab_about' }
  ] as const;

  const themes: ReadonlyArray<{ mode: ThemeMode; icon: string; labelKey: string }> = [
    { mode: 'system', icon: 'system', labelKey: 'settings.theme_system' },
    { mode: 'light', icon: 'sun', labelKey: 'settings.theme_light' },
    { mode: 'dark', icon: 'moon', labelKey: 'settings.theme_dark' }
  ];

  const languages: ReadonlyArray<{ code: Language; labelKey: string }> = [
    { code: 'ru', labelKey: 'lang.russian' },
    { code: 'en', labelKey: 'lang.english' }
  ];

  $: diagnosticsOpen = $inspectorVisible || $inspectorDrawerOpen;
  $: connectionLabel =
    $controlPlaneStore.bridgeState === 'READY'
      ? $t('diag.control_plane_connected')
      : $controlPlaneStore.bridgeState === 'CONNECTING'
        ? $t('diag.control_plane_starting')
        : $controlPlaneStore.bridgeState === 'UNAVAILABLE'
          ? $t('diag.control_plane_unavailable')
          : $controlPlaneStore.bridgeState === 'ERROR'
            ? $t('diag.control_plane_error')
            : $t('diag.control_plane_unknown');

  onMount(() => {
    closeButton?.focus();
    void initializeFilesCapability();
  });
</script>

<div
  id="settings-panel"
  class="settings-panel"
  role="dialog"
  aria-modal="false"
  aria-labelledby="settings-title"
>
  <header>
    <div>
      <span class="eyebrow">LocalComet</span>
      <h2 id="settings-title">{$t('settings.title')}</h2>
    </div>
    <button
      type="button"
      class="plain-button close-button"
      bind:this={closeButton}
      aria-label={$t('settings.close')}
      title={$t('settings.close')}
      onclick={onClose}
    >
      <Icon name="cancel" size={16} />
      <span>{$t('settings.close')}</span>
    </button>
  </header>

  <nav class="settings-tabs" aria-label={$t('settings.sections')}>
    {#each sections as item}
      <button
        type="button"
        class:active={$settingsSection === item.id}
        aria-current={$settingsSection === item.id ? 'page' : undefined}
        onclick={() => settingsSection.set(item.id)}
      >{$t(item.labelKey)}</button>
    {/each}
  </nav>

  <div class="settings-content">
    <div class:panel-hidden={$settingsSection !== 'interface'} aria-hidden={$settingsSection !== 'interface'}>
      <section aria-labelledby="settings-appearance">
      <h3 id="settings-appearance">{$t('settings.appearance')}</h3>
      <div class="choice-grid theme-grid" role="group" aria-label={$t('settings.theme')}>
        {#each themes as item}
          <button
            type="button"
            class:selected={$themeMode === item.mode}
            aria-label={$t(item.labelKey)}
            aria-pressed={$themeMode === item.mode}
            title={$t(item.labelKey)}
            onclick={() => setThemeMode(item.mode)}
          >
            <Icon name={item.icon} size={18} />
            <span>{$t(item.labelKey)}</span>
          </button>
        {/each}
      </div>
      </section>

      <section aria-labelledby="settings-language">
      <h3 id="settings-language">{$t('settings.language')}</h3>
      <div class="choice-grid language-grid" role="group" aria-label={$t('settings.language')}>
        {#each languages as item}
          <button
            type="button"
            class:selected={$locale === item.code}
            aria-label={$t(item.labelKey)}
            aria-pressed={$locale === item.code}
            title={$t(item.labelKey)}
            onclick={() => setLocale(item.code)}
          >
            <span>{$t(item.labelKey)}</span>
          </button>
        {/each}
      </div>
      </section>

      <section aria-labelledby="settings-diagnostics">
      <h3 id="settings-diagnostics">{$t('settings.diagnostics')}</h3>
      <div class="diagnostics-setting">
        <div class="connection-state">
          <span>{$t('settings.connection_state')}</span>
          <output title={connectionLabel}>{connectionLabel}</output>
        </div>
        <button
          type="button"
          class="diagnostics-toggle"
          aria-pressed={diagnosticsOpen}
          aria-controls="diagnostics-panel"
          onclick={() => setDiagnosticsPanelOpen(!diagnosticsOpen)}
        >
          <Icon name="inspector" size={18} />
          <span>{$t(diagnosticsOpen ? 'settings.hide_diagnostics' : 'settings.show_diagnostics')}</span>
        </button>
      </div>
      </section>
    </div>

    <div class:panel-hidden={$settingsSection !== 'models'} aria-hidden={$settingsSection !== 'models'}>
      <ModelManagerSection />
    </div>
    <div class:panel-hidden={$settingsSection !== 'observability'} aria-hidden={$settingsSection !== 'observability'}>
      <ObservabilityRoom />
    </div>

    <section class:panel-hidden={$settingsSection !== 'about'} aria-hidden={$settingsSection !== 'about'} aria-labelledby="settings-about">
      <h3 id="settings-about">{$t('settings.about')}</h3>
      <dl class="about-list">
        <div>
          <dt>{$t('settings.application')}</dt>
          <dd>LocalComet</dd>
        </div>
        <div>
          <dt>{$t('settings.version')}</dt>
          <dd>{DESKTOP_SHELL_VERSION}</dd>
        </div>
        <div>
          <dt>{$t('settings.build')}</dt>
          <dd>{DESKTOP_BUILD_LABEL}</dd>
        </div>
        <div>
          <dt>{$t('settings.build_status')}</dt>
          <dd>{DESKTOP_BUILD_STATUS}</dd>
        </div>
      </dl>
      <div class="capability-summary" aria-label={$t('settings.capabilities')}>
        <div>
          <h4>{$t('settings.available')}</h4>
          <ul>
            <li>{$t('capability.local_chat')}</li>
            <li>{$t('capability.local_model_inference')}</li>
            <li>{$t('capability.approved_model_setup')}</li>
            {#if $filesCapabilityAvailable}<li>{$t('capability.files')}</li>{/if}
          </ul>
        </div>
        <div>
          <h4>{$t('settings.unavailable')}</h4>
          <ul>
            <li>{$t('capability.internet')}</li>
            <li>{$t('capability.email')}</li>
            <li>{$t('capability.browser')}</li>
            {#if !$filesCapabilityAvailable}<li>{$t('capability.files')}</li>{/if}
            <li>{$t('capability.vault')}</li>
            <li>{$t('capability.computer_use')}</li>
            <li>{$t('capability.shell')}</li>
            <li>{$t('capability.external_tools')}</li>
          </ul>
        </div>
      </div>
      <p class="capability-note">{$t('settings.project_context_unavailable')}</p>
    </section>
  </div>
</div>

<style>
  .settings-panel {
    position: fixed;
    top: var(--shell-header-height);
    right: 0;
    bottom: 0;
    z-index: 50;
    width: min(820px, calc(100vw - var(--rail-width)));
    min-width: 0;
    overflow-y: auto;
    border-left: var(--border-thin);
    background: var(--lc-panel-solid);
    box-shadow: var(--lc-shadow);
    color: var(--lc-text);
  }

  header {
    position: sticky;
    top: 0;
    z-index: 1;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--lc-space-3);
    border-bottom: var(--border-thin);
    background: var(--lc-panel-solid);
    padding: var(--lc-space-4);
  }

  .settings-tabs {
    position: sticky;
    top: 79px;
    z-index: 1;
    display: flex;
    gap: var(--lc-space-1);
    overflow-x: auto;
    border-bottom: var(--border-thin);
    padding: 0 var(--lc-space-4);
    background: var(--lc-panel-solid);
  }

  .settings-tabs button {
    flex: 0 0 auto;
    min-height: 42px;
    border: 0;
    border-bottom: 2px solid transparent;
    padding: 0 var(--lc-space-3);
    background: transparent;
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 760;
    cursor: pointer;
  }

  .settings-tabs button.active {
    border-bottom-color: var(--lc-accent);
    color: var(--lc-accent);
  }

  .eyebrow {
    color: var(--lc-muted);
    font-size: 11px;
    font-weight: 760;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  h2,
  h3 {
    margin: 0;
  }

  h2 {
    margin-top: var(--lc-space-1);
    font-size: 19px;
  }

  h3 {
    margin-bottom: var(--lc-space-3);
    color: var(--lc-muted);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .close-button {
    display: inline-flex;
    align-items: center;
    gap: var(--lc-space-1);
    min-height: 36px;
    padding: 0 var(--lc-space-2);
    color: var(--lc-muted);
  }

  .settings-content {
    display: grid;
    gap: var(--lc-space-5);
    padding: var(--lc-space-4);
  }

  .settings-content > div:not(.panel-hidden) {
    display: grid;
    gap: var(--lc-space-5);
  }

  .panel-hidden {
    display: none;
  }

  section {
    min-width: 0;
    border-bottom: var(--border-thin);
    padding-bottom: var(--lc-space-5);
  }

  section:last-child {
    border-bottom: 0;
    padding-bottom: 0;
  }

  .choice-grid {
    display: grid;
    gap: var(--lc-space-2);
  }

  .theme-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .language-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .choice-grid button,
  .diagnostics-toggle {
    min-width: 0;
    min-height: 44px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-soft);
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 760;
    cursor: pointer;
  }

  .choice-grid button {
    display: grid;
    place-items: center;
    gap: var(--lc-space-1);
    padding: var(--lc-space-2);
    text-align: center;
  }

  .choice-grid button:hover,
  .diagnostics-toggle:hover {
    border-color: var(--lc-line-strong);
    color: var(--lc-text);
  }

  .choice-grid button.selected,
  .diagnostics-toggle[aria-pressed='true'] {
    border-color: var(--lc-line-strong);
    background: var(--lc-accent-dim);
    color: var(--lc-accent);
  }

  .diagnostics-setting {
    display: grid;
    gap: var(--lc-space-3);
  }

  .connection-state {
    display: grid;
    gap: var(--lc-space-1);
    min-width: 0;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    padding: var(--lc-space-3);
    background: var(--lc-panel-soft);
  }

  .connection-state > span,
  dt {
    color: var(--lc-muted);
    font-size: 11px;
    font-weight: 720;
  }

  output,
  dd {
    min-width: 0;
    overflow-wrap: anywhere;
    color: var(--lc-text);
    font-size: 12px;
    font-weight: 760;
  }

  .capability-summary {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--lc-space-2);
    margin-top: var(--lc-space-3);
  }

  .capability-summary > div {
    min-width: 0;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    padding: var(--lc-space-3);
    background: var(--lc-panel-soft);
  }

  h4 {
    margin: 0 0 var(--lc-space-2);
    color: var(--lc-text);
    font-size: 12px;
  }

  ul {
    display: grid;
    gap: var(--lc-space-1);
    margin: 0;
    padding-left: 18px;
    color: var(--lc-muted);
    font-size: 11px;
  }

  .capability-note {
    margin: var(--lc-space-3) 0 0;
    color: var(--lc-muted);
    font-size: 11px;
    line-height: 1.45;
  }

  .diagnostics-toggle {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--lc-space-2);
    padding: 0 var(--lc-space-3);
  }

  .about-list {
    display: grid;
    gap: var(--lc-space-2);
    margin: 0;
  }

  .about-list div {
    display: grid;
    grid-template-columns: minmax(88px, 0.8fr) minmax(0, 1.2fr);
    gap: var(--lc-space-3);
    align-items: start;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    padding: var(--lc-space-2) var(--lc-space-3);
  }

  dd {
    margin: 0;
    text-align: right;
    font-family: var(--lc-mono);
  }

  @media (max-width: 520px) {
    .settings-panel {
      width: calc(100vw - var(--rail-width));
    }

    .theme-grid {
      grid-template-columns: 1fr;
    }

    .capability-summary {
      grid-template-columns: 1fr;
    }
  }
</style>
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/data/mockData.ts (182 строк, 5734 байт)

````typescript
export type ThemeMode = 'system' | 'light' | 'dark';
export type ResolvedTheme = 'light' | 'dark';
export type ModeOption = 'Chat' | 'Plan' | 'Agent';
export type ModelOption = 'Not configured';
export type MessageRole = 'user' | 'assistant';
export type ChatMessageState = 'accepted' | 'streaming' | 'completed' | 'cancelled' | 'timed_out' | 'failed';
export type InspectorSection = 'Обзор' | 'Телеметрия' | 'События' | 'Политика' | 'Проверка';

export interface MockMessage {
  id: string;
  role: MessageRole;
  body: string;
  requestId?: string;
  state?: ChatMessageState;
  error?: string;
  demo?: boolean;
}

export interface ConversationItem {
  id: string;
  title: string;
  meta: string;
  selected?: boolean;
}

export interface ConversationGroup {
  label: string;
  items: ConversationItem[];
}

export interface ToolCallMock {
  operation: string;
  target: string;
  status: 'PASS' | 'WAITING' | 'SKIPPED';
  elapsed: string;
  detail: string;
  result: string;
}

export interface CodeBlockMock {
  filename: string;
  language: string;
  code: string;
}

export interface VerificationMock {
  label: string;
  status: string;
  detail: string;
}

export interface ApprovalMock {
  title: string;
  detail: string;
}

export const modelOptions: ModelOption[] = ['Not configured'];
export const modeOptions: ModeOption[] = ['Chat', 'Plan', 'Agent'];
export const inspectorSections: InspectorSection[] = ['Обзор', 'Телеметрия', 'События', 'Политика', 'Проверка'];

export const conversationGroups: ConversationGroup[] = [
  {
    label: 'local_chats',
    items: [
      { id: 'local-chat', title: 'new_chat', meta: 'model_not_connected', selected: true },
      { id: 'cancellation-demo', title: 'cancellation_demo', meta: 'model_required' }
    ]
  },
  {
    label: 'reserved',
    items: [{ id: 'audit-placeholder', title: 'audit', meta: 'later' }]
  },
  {
    label: 'disabled',
    items: [{ id: 'documents', title: 'documents', meta: 'later' }]
  }
];

export const pinnedProject = {
  title: 'LocalComet',
  detail: 'Локальный чат с моделью'
};

export const projectLabels = ['v6.84.5.1b', 'Frontend', 'Русский UX'];

export const legacyRegressionAnchors = {
  sanitizedPath: '<PROJECT_ROOT>/modules/example.py',
  deferred: ['Skills — Позже', 'Memory — Позже', 'Artifacts — Позже', 'Channels — Позже']
};

export const initialMessages: MockMessage[] = [
  {
    id: 'seed-user',
    role: 'user',
    body: 'Начать диалог.'
  },
  {
    id: 'seed-assistant',
    role: 'assistant',
    body: 'Модель не подключена. Нажмите «Подключить модель», чтобы начать безопасный диалог.',
    demo: true
  }
];

export const reasoningStatus = {
  title: 'Примечание',
  status: 'ДЕМО',
  detail: 'Этот релиз проверяет только Control Plane. Без подключённой модели ответов нет.'
};

export const mockToolCall: ToolCallMock = {
  operation: 'Инструменты',
  target: 'Не настроено',
  status: 'SKIPPED',
  elapsed: '0',
  detail: 'Выполнение инструментов отключено в v6.84.5.1b.',
  result: 'Инструментов выполнено: 0'
};

export const mockCodeBlock: CodeBlockMock = {
  filename: 'Возможности runtime',
  language: 'text',
  code: [
    'Model Gateway: Не настроен',
    'Provider: Не настроен',
    'Harness: Не настроен',
    'Persistence: Off'
  ].join('\n')
};

export const verificationCard: VerificationMock = {
  label: 'Проверка',
  status: 'Не запускалась',
  detail: 'Исполнение проверки не реализовано в этом релизе.'
};

export const approvalCard: ApprovalMock = {
  title: 'Подтверждения отключены',
  detail: 'Runtime подтверждений отключён; действий нет.'
};

export const inspectorMock = {
  status: 'Отключено',
  autonomy: 'Отключено',
  risk: 'Не оценивалось',
  actionsUsed: '0 / 0',
  runtime: 'Не запускалось',
  killSwitch: 'Отключено',
  planSteps: ['Control Plane demo only', 'No model inference', 'No tool execution'],
  actions: [
    { label: 'Model Gateway', state: 'Не настроен' },
    { label: 'Provider', state: 'Не настроен' },
    { label: 'Verification', state: 'Не запускалась' }
  ],
  reserved: [
    { label: 'Skills', state: 'Позже' },
    { label: 'Memory', state: 'Позже' },
    { label: 'Artifacts', state: 'Позже' },
    { label: 'Channels', state: 'Позже' }
  ]
};

export function conversationTitleById(id: string): string {
  for (const group of conversationGroups) {
    const item = group.items.find((conversation) => conversation.id === id);
    if (item) return item.title;
  }
  return 'new_chat';
}

export function getInitialMessages(lang: 'ru' | 'en'): MockMessage[] {
  if (lang === 'en') {
    return [
      { id: 'seed-user', role: 'user', body: 'Start dialog.' },
      { id: 'seed-assistant', role: 'assistant', body: 'Model is not connected. Click "Connect model" to start a secure conversation.', demo: true }
    ];
  }
  return [
    { id: 'seed-user', role: 'user', body: 'Начать диалог.' },
    { id: 'seed-assistant', role: 'assistant', body: 'Модель не подключена. Нажмите «Подключить модель», чтобы начать безопасный диалог.', demo: true }
  ];
}
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/data/reviewFixtures.ts (354 строк, 13479 байт)

````typescript
import type {
  ProposedNoteContentView,
  ReviewCenterItem
} from '$lib/types/knowledgeReview';

function deepFreeze<T>(value: T): T {
  if (value !== null && typeof value === 'object' && !Object.isFrozen(value)) {
    for (const child of Object.values(value as Record<string, unknown>)) {
      deepFreeze(child);
    }
    Object.freeze(value);
  }
  return value;
}

const REVISION_A = "sha256:db3aa6c2ed8046f6f57fe11178d8529cfda2116cfff7ae01b4b579eee999a61a";
const REVISION_B = "sha256:bc06395bf0601ffe3d4e25b951bd613494b6912d1b9adfd033ebf439fda9c093";
const REVISION_C = "sha256:df62512408de6bd5c196570651c10cfbc4a247247f7e1054c4c717de3e3580e2";

function proposedContent(overrides: Partial<ProposedNoteContentView> = {}): ProposedNoteContentView {
  return {
    title: 'Knowledge review lifecycle',
    body_text: '# Knowledge review lifecycle\n\nReview artifacts stop before authority.\n',
    type: 'architecture',
    status: 'accepted',
    knowledge_layer: 'canonical',
    evidence_class: 'source-grounded',
    authority: 'maintainer-reviewed',
    canonical: true,
    canonical_scope: 'architecture.knowledge-layer',
    aliases: ['Review lifecycle'],
    releases: ['v6.84.5.1e9b'],
    source_paths: ['modules/knowledge_change_review_ru.py'],
    evidence_refs: ['evidence.e9b.focused-tests'],
    supersedes: [],
    superseded_by: [],
    updated: '2026-07-16',
    last_reviewed: '2026-07-16',
    verified_at: '2026-07-16T09:00:00Z',
    ...overrides
  };
}

const metadataOnly: ReviewCenterItem = {
  id: 'review-metadata-only',
  fixture: true,
  fixtureLabel: 'Metadata-only fixture',
  status: 'CLEAR',
  proposalId: 'kprop:39770887b8effed001546e4f8ca3960be0dac8b61f40ebde55ba68895540c37a',
  proposalContentHash: 'sha256:400075069c197bbcb0114c66fdcaefa53e224de63bbe58f67f9af54691c996fa',
  reviewArtifactIdentity: 'kreview:57692c300ea9ff7be50e89b7bf9e8303cdaaa03ab52d4f290c8f8b0e1feabcdf',
  changeIdentity: 'kchange:fb09d978dcca99cc4829f433524865416de42cb0eca5b20eb1052ec3b591e4e7',
  operation: 'UPDATE_EXISTING',
  targetStableId: 'architecture.knowledge-review',
  expectedVaultRevision: REVISION_A,
  observedVaultRevision: REVISION_A,
  validation: {
    outcome: 'VALID',
    contractVersion: 'localcomet.knowledge-change-proposal/1.0',
    proposalContentHash: 'sha256:400075069c197bbcb0114c66fdcaefa53e224de63bbe58f67f9af54691c996fa',
    validatedVaultRevision: REVISION_A,
    sourceFindings: [],
    snapshotTruncated: false,
    snapshotSummary: 'Type-tagged validation snapshot verified.'
  },
  findings: [],
  proposedContent: proposedContent({
    title: 'Human-readable knowledge review lifecycle',
    aliases: ['Review lifecycle', 'Human review boundary']
  }),
  metadataChanges: [
    {
      field: 'title',
      before: 'Knowledge review lifecycle',
      after: 'Human-readable knowledge review lifecycle'
    },
    {
      field: 'aliases',
      before: ['Review lifecycle'],
      after: ['Review lifecycle', 'Human review boundary']
    }
  ],
  beforeSourceByteHash: 'sha256:580e36de86fe5fde24c0d67de903eacf0531bedc5c7e15020580624bf3fbd2f5',
  beforeTextRawHash: 'sha256:f1b639bcb63b3e122acdbf8a2efbe99e45c0491a75767dfaef1d83623bae6b30',
  beforeSemanticTextHash: 'sha256:f1b639bcb63b3e122acdbf8a2efbe99e45c0491a75767dfaef1d83623bae6b30',
  proposedTextRawHash: 'sha256:f1b639bcb63b3e122acdbf8a2efbe99e45c0491a75767dfaef1d83623bae6b30',
  proposedSemanticTextHash: 'sha256:f1b639bcb63b3e122acdbf8a2efbe99e45c0491a75767dfaef1d83623bae6b30',
  textDiff: {
    preview: '',
    previewTruncated: false,
    fullDiffAvailable: true,
    fullDiffHash: 'sha256:48384b29c366033e1b206fc1de04846397400cf4c360816e192739f63b1c7cc6',
    fullDiffUtf8Bytes: 0
  },
  representationDelta: {
    identity: 'sha256:e8fa02b7dfa54f9e1890e6e4fe1cfed03d390bd19d1698c4fbdc72df2735f8fe',
    beforePresent: true,
    afterPresent: true,
    beforeLineEndings: {
      label: 'LF',
      crlfCount: 0,
      lfCount: 3,
      crCount: 0,
      terminalNewline: true
    },
    afterLineEndings: {
      label: 'LF',
      crlfCount: 0,
      lfCount: 3,
      crCount: 0,
      terminalNewline: true
    },
    terminalNewlineChanged: false,
    afterSourceBytesKnown: false,
    sourceBytesChangedTextIdentical: false,
    rawTextChangedSemanticEqual: false,
    semanticContentChanged: false
  },
  humanReviewPreview: {
    text: 'Metadata changed while the semantic body diff remained empty. Review all structured fields.',
    truncated: false
  }
};

const representationOnly: ReviewCenterItem = {
  id: 'review-representation-only',
  fixture: true,
  fixtureLabel: 'Representation-only fixture',
  status: 'REVIEW_REQUIRED',
  proposalId: 'kprop:56f33f21c910d48109c8ece14e4e4b45f3044224f2026e4d29d7cf202fa3b4ff',
  proposalContentHash: 'sha256:580e36de86fe5fde24c0d67de903eacf0531bedc5c7e15020580624bf3fbd2f5',
  reviewArtifactIdentity: 'kreview:94d955f5d8f4cf06ff1044bab1358323fccb4cde8e09db0c48aac28f7419b173',
  changeIdentity: 'kchange:d3a244e82013faa1fd052142affd4df6b84423661e09448735498a0c038b834a',
  operation: 'UPDATE_EXISTING',
  targetStableId: 'canonical.current-state',
  expectedVaultRevision: REVISION_A,
  observedVaultRevision: REVISION_A,
  validation: {
    outcome: 'VALID',
    contractVersion: 'localcomet.knowledge-change-proposal/1.0',
    proposalContentHash: 'sha256:580e36de86fe5fde24c0d67de903eacf0531bedc5c7e15020580624bf3fbd2f5',
    validatedVaultRevision: REVISION_A,
    sourceFindings: [],
    snapshotTruncated: false,
    snapshotSummary: 'Validation is exact; no trusted historical baseline was supplied.'
  },
  findings: [
    {
      code: 'TARGET_STATE_COMPARISON_UNAVAILABLE',
      severity: 'REVIEW',
      message: 'Historical target drift is not claimed without a trusted baseline.',
      details: [['expected_vault_revision', REVISION_A]]
    }
  ],
  proposedContent: proposedContent({
    title: 'Current state',
    body_text: '# Current state\n\nReview artifacts stop before authority.\n',
    canonical_scope: 'canonical.current-state'
  }),
  metadataChanges: [],
  beforeSourceByteHash: 'sha256:48384b29c366033e1b206fc1de04846397400cf4c360816e192739f63b1c7cc6',
  beforeTextRawHash: 'sha256:b6171bd597f888487926af6d62f1275f8d1e07f6dff4d89766ab60a73049d5da',
  beforeSemanticTextHash: 'sha256:4188cb7d894dcd814c8e997f4061b565b3b19dc3b5d9a78daf1a4d9eb3600885',
  proposedTextRawHash: 'sha256:400075069c197bbcb0114c66fdcaefa53e224de63bbe58f67f9af54691c996fa',
  proposedSemanticTextHash: 'sha256:4188cb7d894dcd814c8e997f4061b565b3b19dc3b5d9a78daf1a4d9eb3600885',
  textDiff: {
    preview: '',
    previewTruncated: false,
    fullDiffAvailable: true,
    fullDiffHash: 'sha256:b6171bd597f888487926af6d62f1275f8d1e07f6dff4d89766ab60a73049d5da',
    fullDiffUtf8Bytes: 0
  },
  representationDelta: {
    identity: 'sha256:e976645f880f2e82fe084434ab3a7352ca62cf777b6ddf124e8f54116e3b2da5',
    beforePresent: true,
    afterPresent: true,
    beforeLineEndings: {
      label: 'CRLF',
      crlfCount: 3,
      lfCount: 0,
      crCount: 0,
      terminalNewline: true
    },
    afterLineEndings: {
      label: 'LF',
      crlfCount: 0,
      lfCount: 3,
      crCount: 0,
      terminalNewline: true
    },
    terminalNewlineChanged: false,
    afterSourceBytesKnown: false,
    sourceBytesChangedTextIdentical: false,
    rawTextChangedSemanticEqual: true,
    semanticContentChanged: false
  },
  humanReviewPreview: {
    text: 'Semantic body diff is empty, but line endings change from CRLF to LF.',
    truncated: false
  }
};

const blocked: ReviewCenterItem = {
  id: 'review-blocked-stale',
  fixture: true,
  fixtureLabel: 'Blocked stale fixture',
  status: 'BLOCKED',
  proposalId: 'kprop:3a64d96ee9d7be5db2b308b21ae96adbb589a371afad93a3af50fbfd4669c68b',
  proposalContentHash: 'sha256:f1b639bcb63b3e122acdbf8a2efbe99e45c0491a75767dfaef1d83623bae6b30',
  reviewArtifactIdentity: 'kreview:ee7038ee6bebee660b01f0d4e81ebc2ba0e219e4e38f1dec9cc79644adf1d270',
  changeIdentity: null,
  operation: 'UPDATE_EXISTING',
  targetStableId: 'architecture.control-plane',
  expectedVaultRevision: REVISION_A,
  observedVaultRevision: REVISION_B,
  validation: {
    outcome: 'STALE',
    contractVersion: 'localcomet.knowledge-change-proposal/1.0',
    proposalContentHash: 'sha256:f1b639bcb63b3e122acdbf8a2efbe99e45c0491a75767dfaef1d83623bae6b30',
    validatedVaultRevision: REVISION_A,
    sourceFindings: [['STALE_BASE_REVISION', 'error']],
    snapshotTruncated: false,
    snapshotSummary: 'Validation result is stale relative to the observed Vault revision.'
  },
  findings: [
    {
      code: 'STALE_VAULT_REVISION',
      severity: 'BLOCKING',
      message: 'The proposal or validation result is stale relative to the observed Vault revision.',
      details: [
        ['expected', REVISION_A],
        ['observed', REVISION_B],
        ['validated', REVISION_A]
      ]
    }
  ],
  proposedContent: proposedContent({
    title: 'Control plane boundary',
    canonical_scope: 'architecture.control-plane'
  }),
  metadataChanges: [],
  beforeSourceByteHash: null,
  beforeTextRawHash: null,
  beforeSemanticTextHash: null,
  proposedTextRawHash: 'sha256:48384b29c366033e1b206fc1de04846397400cf4c360816e192739f63b1c7cc6',
  proposedSemanticTextHash: 'sha256:b6171bd597f888487926af6d62f1275f8d1e07f6dff4d89766ab60a73049d5da',
  textDiff: {
    preview: null,
    previewTruncated: false,
    fullDiffAvailable: false,
    fullDiffHash: null,
    fullDiffUtf8Bytes: null
  },
  representationDelta: null,
  humanReviewPreview: {
    text: 'BLOCKED: stale review. Normal change material is suppressed.',
    truncated: false
  }
};

const truncated: ReviewCenterItem = {
  id: 'review-truncated-diff',
  fixture: true,
  fixtureLabel: 'Truncated diff fixture',
  status: 'REVIEW_REQUIRED',
  proposalId: 'kprop:1d96a2b9415ca85f4673cd95b327d625b1802f61bd8070458134b841ceaceca2',
  proposalContentHash: 'sha256:b6171bd597f888487926af6d62f1275f8d1e07f6dff4d89766ab60a73049d5da',
  reviewArtifactIdentity: 'kreview:a44e147813d992edd07d328a3bf056b68cbed059b9f379cdaf67e60f1337085c',
  changeIdentity: 'kchange:03a52db9b90dd1f66ca88064ab5481f72c94c8420a913e355fd5b49671d87e21',
  operation: 'UPDATE_EXISTING',
  targetStableId: 'architecture.review-center',
  expectedVaultRevision: REVISION_C,
  observedVaultRevision: REVISION_C,
  validation: {
    outcome: 'VALID',
    contractVersion: 'localcomet.knowledge-change-proposal/1.0',
    proposalContentHash: 'sha256:b6171bd597f888487926af6d62f1275f8d1e07f6dff4d89766ab60a73049d5da',
    validatedVaultRevision: REVISION_C,
    sourceFindings: [],
    snapshotTruncated: true,
    snapshotSummary: 'Validation snapshot preview is bounded; exact review identity remains available.'
  },
  findings: [
    {
      code: 'TARGET_STATE_COMPARISON_UNAVAILABLE',
      severity: 'REVIEW',
      message: 'Historical target drift is not claimed without a trusted baseline.',
      details: [['expected_vault_revision', REVISION_C]]
    }
  ],
  proposedContent: proposedContent({
    title: 'Review Center user interface',
    body_text: '# Review Center\n\nThe fixture contains a bounded diff preview.\n',
    canonical_scope: 'architecture.review-center',
    releases: ['v6.84.5.1e9b', 'Review Center Phase 1'],
    source_paths: ['desktop/localcomet-desktop/src/lib/components/review/ReviewCenterWorkspace.svelte']
  }),
  metadataChanges: [
    {
      field: 'releases',
      before: ['v6.84.5.1e9b'],
      after: ['v6.84.5.1e9b', 'Review Center Phase 1']
    }
  ],
  beforeSourceByteHash: 'sha256:b6171bd597f888487926af6d62f1275f8d1e07f6dff4d89766ab60a73049d5da',
  beforeTextRawHash: 'sha256:4188cb7d894dcd814c8e997f4061b565b3b19dc3b5d9a78daf1a4d9eb3600885',
  beforeSemanticTextHash: 'sha256:4188cb7d894dcd814c8e997f4061b565b3b19dc3b5d9a78daf1a4d9eb3600885',
  proposedTextRawHash: 'sha256:400075069c197bbcb0114c66fdcaefa53e224de63bbe58f67f9af54691c996fa',
  proposedSemanticTextHash: 'sha256:580e36de86fe5fde24c0d67de903eacf0531bedc5c7e15020580624bf3fbd2f5',
  textDiff: {
    preview: '--- before-body/architecture.review-center\n+++ after-body/architecture.review-center\n@@ -1,4 +1,7 @@\n # Review Center\n+\n+Read-only fixture review queue.\n+No Tauri command is called.\n ... REVIEW_DIFF_PREVIEW_TRUNCATED ...\n',
    previewTruncated: true,
    fullDiffAvailable: true,
    fullDiffHash: 'sha256:4188cb7d894dcd814c8e997f4061b565b3b19dc3b5d9a78daf1a4d9eb3600885',
    fullDiffUtf8Bytes: 8192
  },
  representationDelta: {
    identity: 'sha256:34ec938dfc85d8379000a0fd8225dc13a8975dc4b851c920a1a7377c61bde28f',
    beforePresent: true,
    afterPresent: true,
    beforeLineEndings: {
      label: 'LF',
      crlfCount: 0,
      lfCount: 4,
      crCount: 0,
      terminalNewline: true
    },
    afterLineEndings: {
      label: 'LF',
      crlfCount: 0,
      lfCount: 7,
      crCount: 0,
      terminalNewline: true
    },
    terminalNewlineChanged: false,
    afterSourceBytesKnown: false,
    sourceBytesChangedTextIdentical: false,
    rawTextChangedSemanticEqual: false,
    semanticContentChanged: true
  },
  humanReviewPreview: {
    text: 'Review preview is bounded. The truncation marker is explicit and identities remain exact.\n... REVIEW_DIFF_PREVIEW_TRUNCATED ...',
    truncated: true
  }
};

export const REVIEW_FIXTURES: readonly ReviewCenterItem[] = deepFreeze([
  metadataOnly,
  representationOnly,
  blocked,
  truncated
]);

export const REVIEW_FIXTURE_COUNT = REVIEW_FIXTURES.length;
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/i18n/en.ts (688 строк, 35973 байт)

````typescript
import type { TranslationMap } from './index';

export const en: TranslationMap = {
  // Navigation
  'nav.chat': 'Chat',
  'nav.tasks': 'Tasks',
  'nav.diagnostics': 'Diagnostics',
  'nav.audit': 'Audit',
  'nav.settings': 'Settings',
  'nav.setup': 'Setup',
  'nav.main': 'Main navigation',
  'app.title_bar': 'LocalComet application bar',
  'nav.later': 'later',

  // Sidebar
  'sidebar.label': 'Session sidebar',
  'sidebar.new_thread': 'New thread',
  'sidebar.new_thread_title': 'Thread creation happens when Control Plane demo starts',
  'sidebar.collapse': 'Collapse/expand sidebar',
  'sidebar.toggle': 'Show or hide the chat sidebar',
  'sidebar.pinned_label': 'Pinned Control Plane',
  'sidebar.pinned': 'Pinned',
  'sidebar.project_labels': 'Project labels',

  // Sidebar groups
  'group.local_chats': 'Local chats',
  'group.reserved': 'Reserved',
  'group.disabled': 'Disabled',

  // Sidebar items
  'item.new_chat': 'New chat',
  'item.cancellation_demo': 'Cancellation demo',
  'item.audit': 'Audit',
  'item.documents': 'Documents',
  'item.model_not_connected': 'Model not connected',
  'item.model_required': 'Model required',
  'item.later': 'Later',

  // Chat
  'chat.type_message': 'Type a message…',
  'chat.connect_model_first': 'Connect a model first',
  'chat.send': 'Send',
  'chat.stop': 'Stop',
  'chat.model_responding': 'Model is responding…',
  'chat.tools_unavailable': 'Tools (not yet available)',
  'chat.model_not_connected': 'Model not connected',
  'chat.model_not_connected_detail': 'Connect a local model to start a secure conversation.',
  'chat.model_unavailable': 'Local model unavailable',
  'chat.model_unavailable_detail': 'LocalComet uses a local model. Only explicitly included file text is available; there is no arbitrary file, internet, email, Vault, shell, Computer Use, or external-tool access. Connect the approved local model to begin.',
  'chat.model_loading': 'Preparing the local model',
  'chat.model_loading_detail': 'LocalComet is validating the managed runtime and loading the approved model. Sending remains disabled until readiness is confirmed.',
  'chat.model_loading_status': 'Validation and loading in progress',
  'chat.first_use_ready': 'Local assistant ready',
  'chat.first_use_detail': 'Messages use the ready local model. Text from selected files can be explicitly included; arbitrary file, internet, email, Vault, shell, Computer Use, and external-tool access remain unavailable.',
  'chat.local_only_status': 'Local text conversation only',
  'chat.state_accepted': 'Request accepted',
  'chat.state_streaming': 'Generating locally',
  'chat.state_cancelled': 'Cancelled — partial response preserved',
  'chat.state_timed_out': 'Timed out — you can retry safely',
  'chat.state_failed': 'Request failed — you can retry safely',
  'chat.retry': 'Retry',
  'chat.request_failed_detail': 'The local response failed. Retry when the model is ready; no private path or stack trace is shown.',
  'chat.request_timed_out_detail': 'The local response timed out. The model remains safe to retry when ready.',
  'chat.connect_model': 'Connect model',
  'chat.setup_local_ai': 'Set up local AI',
  'chat.open_models': 'Open models',
  'chat.model_installing': 'Setting up local AI…',
  'chat.model_connecting': 'Connecting model…',
  'chat.user_message': 'User message',
  'chat.model_response': 'Model response',
  'chat.you': 'You',
  'chat.model': 'Model',
  'chat.demo': 'DEMO',
  'chat.message_history': 'Message history',

  // Approval
  'approval.disabled': 'Disabled',
  'approval.section_aria': 'Approvals disabled',
  'approval.confirm': 'Confirm',
  'approval.reject': 'Reject',
  'approval.confirm_aria': 'Confirm disabled, because desktop bridge is not connected',
  'approval.reject_aria': 'Reject disabled, because desktop bridge is not connected',

  // Files
  'files.title': 'Files',
  'files.read_only': 'Explicitly selected local text files only · read-only',
  'files.add': 'Add files',
  'files.selecting': 'Picker open…',
  'files.loading': 'Checking safe file selection availability…',
  'files.unavailable': 'Safe file selection is unavailable in this environment.',
  'files.empty': 'No files selected. LocalComet does not scan drives or directories.',
  'files.selected_list': 'Selected files',
  'files.size': 'Size',
  'files.bytes': 'bytes',
  'files.characters': 'characters',
  'files.added': 'Added',
  'files.location': 'Location',
  'files.include': 'Include in next request',
  'files.preview': 'Preview',
  'files.loading_preview': 'Reading…',
  'files.forget': 'Remove & forget',
  'files.forgetting': 'Forgetting…',
  'files.context_total': 'Next-request context:',
  'files.context_excerpt_notice': 'If text exceeds the model-request limit, a deterministic bounded excerpt is included with exact counts.',
  'files.inclusion.full': 'Full file included in the last request',
  'files.inclusion.excerpt': 'Bounded excerpt included in the last request',
  'files.preview_eyebrow': 'Safe preview',
  'files.close_preview': 'Close file preview',
  'files.preview_truncated': 'bounded excerpt shown',
  'files.dismiss_error': 'Dismiss file error',
  'files.status.ready': 'Readable',
  'files.status.missing': 'Missing',
  'files.status.changed': 'Changed',
  'files.status.reparse_point': 'Link denied',
  'files.status.unreadable': 'Unreadable',
  'files.error.LC_FILE_UNSUPPORTED_TYPE': 'Unsupported type. TXT, MD, JSON, YAML, YML, CSV, and LOG are allowed.',
  'files.error.LC_FILE_TOO_LARGE': 'The file is larger than 2 MiB.',
  'files.error.LC_FILE_BINARY': 'The file appears binary or contains disallowed control characters.',
  'files.error.LC_FILE_INVALID_UTF8': 'The file is not valid UTF-8 text.',
  'files.error.LC_FILE_MISSING': 'The file no longer exists.',
  'files.error.LC_FILE_CHANGED': 'The file changed after selection. Forget it and select it again.',
  'files.error.LC_FILE_ACCESS_DENIED': 'Access to the selected file was safely denied.',
  'files.error.LC_FILE_REPARSE_POINT': 'Symbolic links, junctions, and reparse points are denied.',
  'files.error.LC_FILE_CONTEXT_LIMIT': 'Included files exceed the 5 MiB aggregate or available request limit.',
  'files.error.LC_FILE_UNREADABLE': 'The selected file could not be read safely.',
  'files.error.LC_FILE_SELECTION_LIMIT': 'At most 32 files may be selected in one session.',
  'files.error.LC_FILE_PICKER_UNAVAILABLE': 'The system file picker is unavailable.',
  'files.error.LC_FILE_STATE_UNAVAILABLE': 'Selected-file state is unavailable. Restart LocalComet before selecting files again.',
  'files.error.default': 'The selected-file operation failed closed.',

  // Project Knowledge
  'knowledge.title': 'Project Knowledge',
  'knowledge.unavailable': 'Project context is currently unavailable',
  'knowledge.unavailable_detail': 'No project data is being sent. This is not long-term memory.',
  'knowledge.enabled': 'On for this session',
  'knowledge.disabled': 'Off',
  'knowledge.toggle_label': 'Enable Project Knowledge for the next turn',
  'knowledge.approval_label': 'Project Knowledge approval preview',
  'knowledge.sources': 'sources',
  'knowledge.characters': 'characters',
  'knowledge.vault': 'Vault',
  'knowledge.selected_sections': 'Selected sections',
  'knowledge.lines': 'Lines',
  'knowledge.retrieving': 'Retrieving bounded project knowledge… No model request has been sent.',
  'knowledge.include_send': 'Include knowledge and send',
  'knowledge.send_without': 'Send without knowledge',
  'knowledge.cancel': 'Cancel',
  'knowledge.retry': 'Retry',
  'knowledge.refresh': 'Refresh preview',
  'knowledge.stale_message': 'Project knowledge changed. Refresh the preview.',
  'knowledge.failure_message': 'Project knowledge could not be prepared. Nothing was sent to the model.',
  'knowledge.state_off': 'Off',
  'knowledge.state_retrieving': 'Retrieving',
  'knowledge.state_preview_ready': 'Ready to send',
  'knowledge.state_deciding': 'Recording decision',
  'knowledge.state_dispatching': 'Sending to model',
  'knowledge.state_injected': 'Knowledge sent',
  'knowledge.state_rejected': 'Sent without knowledge',
  'knowledge.state_cancelled': 'Canceled — not sent',
  'knowledge.state_failed': 'Preview failed',
  'knowledge.state_stale': 'Preview changed',

  // Connection states
  'conn.not_connected': 'Not connected',
  'conn.status': 'Connection status',
  'conn.model_connected': 'Model: Connected',
  'conn.connecting': 'Connecting',
  'conn.ready': 'Ready',
  'conn.generating': 'Generating',
  'conn.error': 'Error',
  'conn.request_generating': 'Request: Generating',
  'conn.request_error': 'Request: Error',
  'conn.model_ready': 'Model: Ready',
  'conn.model_loading': 'Model: Loading',
  'conn.model_unavailable': 'Model: Unavailable',
  'conn.model_error': 'Model: Error',
  'conn.runtime_ready': 'Runtime: Ready',

  // Model Setup
  'setup.title': 'Connect model',
  'setup.close': 'Close',
  'setup.external_tab': 'External local server',
  'setup.managed_tab': 'Managed local model',
  'setup.external_desc': 'Connect to an OpenAI-compatible server on localhost',
  'setup.managed_desc': 'Managed llama.cpp model running locally',
  'setup.external_diagnostics_only': 'External loopback binding is diagnostics-only. Chat requires the approved managed model.',
  'setup.step_port': '1. Port',
  'setup.step_model': '2. Model',
  'setup.step_mode': '3. Mode',
  'setup.step_connect': '4. Connect',
  'setup.port': 'Port',
  'setup.check_server': 'Check server',
  'setup.find_models': 'Find models',
  'setup.probing': 'Probing...',
  'setup.server_unavailable': 'Server unavailable',
  'setup.server_ready': 'Server ready',
  'setup.model': 'Model',
  'setup.select_model': 'Select a discovered model',
  'setup.response_mode': 'Response mode',
  'setup.no_system_instruction': 'No system instruction',
  'setup.safe_mode': 'LocalComet safe mode',
  'setup.connect': 'Connect model',
  'setup.binding_id': 'Connection ID',
  'setup.runtime_not_installed': 'Managed runtime is not installed yet.',
  'setup.install_available': 'Installation will be available in a future update.',
  'setup.runtime_status': 'Status',
  'setup.runtime_version': 'Runtime version',
  'setup.runtime_model': 'Local model',
  'setup.runtime_inference': 'Inference',
  'setup.not_installed': 'Not installed',
  'setup.not_checked': 'Not checked',
  'setup.not_selected': 'Not selected',
  'setup.connected': 'Connected',
  'setup.needs_binding': 'Binding required',
  'setup.refresh': 'Refresh',
  'setup.start_runtime': 'Start runtime',
  'setup.stop_runtime': 'Stop runtime',
  'setup.select_local_model': 'Select a local model',
  'setup.external_mode': 'External local server',
  'setup.managed_mode': 'Managed local model',

  // Diagnostics
  'diag.title': 'Diagnostics',
  'diag.toggle': 'Show or hide diagnostics',
  'diag.runtime': 'Runtime',
  'diag.runtime_state': 'Runtime State',
  'diag.close': 'Close',
  'diag.tab_Обзор': 'Overview',
  'diag.tab_Телеметрия': 'Telemetry',
  'diag.tab_События': 'Events',
  'diag.tab_Политика': 'Policy',
  'diag.tab_Проверка': 'Verification',
  'diag.sections_label': 'Diagnostics sections',
  'diag.summary': 'Overview',
  'diag.session': 'Session',
  'diag.thread': 'Thread',
  'diag.turn': 'Turn',
  'diag.turn_state': 'Turn state',
  'diag.current_item': 'Current item',
  'diag.last_event': 'Last event',
  'diag.event_count': 'Events',
  'diag.model_gateway': 'Model gateway',
  'diag.model_called': 'Model called',
  'diag.tools_executed': 'Tools executed',
  'diag.persistence': 'Persistence',
  'diag.provider': 'Provider',
  'diag.response_mode': 'Response mode',
  'diag.autonomous': 'Autonomous actions',
  'diag.confirmation': 'Confirmation',
  'diag.result_check': 'Result check',
  'diag.status': 'Status',
  'diag.event_stream': 'EVENT STREAM',
  'diag.event_stream_label': 'Validated event stream',
  'diag.no_validated_events': 'No validated events received.',
  'diag.policy_decision': 'POLICY DECISION',
  'diag.policy_decision_label': 'Policy decision',
  'diag.not_evaluated': 'Not evaluated',
  'diag.unknown': 'Unknown',
  'diag.not_configured': 'Not configured',
  'diag.probing': 'Probing',
  'diag.unavailable': 'Unavailable',
  'diag.ready': 'Ready',
  'diag.connected': 'Connected',
  'diag.binding_required': 'Binding required',
  'diag.bound': 'Bound',
  'diag.generating': 'Generating',
  'diag.cancelling': 'Cancelling',
  'diag.failed': 'Failed',
  'diag.off': 'Off',
  'diag.disabled': 'Disabled',
  'diag.not_run': 'Not run',
  'diag.result_not_run': 'Not run',
  'diag.yes': 'Yes',
  'diag.no': 'No',
  'diag.running': 'Running',
  'diag.completed': 'Completed',
  'diag.cancelled': 'Cancelled',
  'diag.error': 'Error',
  'diag.not_started': 'Not started',
  'diag.demo_controls': 'Demo controls',
  'diag.start_demo': 'Start cancellation demo',
  'diag.cancel_demo': 'Cancel current demo turn',
  'diag.about_versions': 'About versions',
  'diag.desktop_shell': 'Desktop shell',
  'diag.control_plane_connected': 'Control Plane: Connected',
  'diag.control_plane_starting': 'Control Plane: Starting',
  'diag.control_plane_unavailable': 'Control Plane: Unavailable',
  'diag.control_plane_error': 'Control Plane: Error',
  'diag.control_plane_unknown': 'Control Plane: Unknown',
  'diag.control_plane_not_connected': 'Control Plane must be connected',
  'diag.sidecar_ready': 'Sidecar: Ready',
  'diag.sidecar_unknown': 'Sidecar: Unknown',

  // Common
  'common.skip_link': 'Skip to chat',

  // Command palette
  'commandPalette.label': 'Command palette',
  'commandPalette.search': 'Find a command',
  'commandPalette.placeholder': 'Type a command…',
  'commandPalette.commands': 'Available commands',
  'commandPalette.empty': 'No matching commands',
  'commandPalette.command.chat': 'Open chat',
  'commandPalette.command.settings': 'Open settings',
  'commandPalette.command.setup': 'Open local setup',
  'commandPalette.command.models': 'Open model manager',
  'commandPalette.command.observability': 'Open logs and observability',
  'commandPalette.command.showDiagnostics': 'Show diagnostics',
  'commandPalette.command.hideDiagnostics': 'Hide diagnostics',

  // Theme
  'theme.manage': 'Theme settings',
  'theme.system': 'Use system theme',
  'theme.light': 'Use light theme',
  'theme.dark': 'Use dark theme',

  // Demo messages
  'demo.start_dialog': 'Start dialog.',
  'demo.model_not_connected': 'Model is not connected. Click "Connect model" to start a secure conversation.',

  // Language
  'lang.select': 'Select language',
  'lang.russian': 'Русский',
  'lang.english': 'English',

  // Settings
  'settings.title': 'Settings',
  'settings.sections': 'Settings sections',
  'settings.tab_interface': 'Interface',
  'settings.tab_models': 'Models',
  'settings.tab_observability': 'Logs',
  'settings.tab_about': 'About',
  'settings.close': 'Close settings',
  'settings.appearance': 'Appearance',
  'settings.theme': 'Theme',
  'settings.theme_system': 'System',
  'settings.theme_light': 'Light',
  'settings.theme_dark': 'Dark',
  'settings.language': 'Language',
  'settings.diagnostics': 'Diagnostics',
  'settings.connection_state': 'Control Plane connection',
  'settings.show_diagnostics': 'Show Diagnostics',
  'settings.hide_diagnostics': 'Hide Diagnostics',
  'settings.about': 'About',
  'settings.application': 'Application',
  'settings.version': 'Version',
  'settings.build': 'Build',
  'settings.build_status': 'Build status',
  'settings.capabilities': 'Current capabilities',
  'settings.available': 'Available',
  'settings.unavailable': 'Unavailable',
  'settings.project_context_unavailable': 'Project context is unavailable. Files supplies only text explicitly included in the current request; the assistant does not inspect repositories, directories, other files, or Vault. This is not long-term memory.',
  'capability.local_chat': 'Local chat',
  'capability.local_model_inference': 'Local model inference',
  'capability.approved_model_setup': 'Approved local model setup',
  'capability.internet': 'Internet access for assistant',
  'capability.email': 'Email',
  'capability.browser': 'Browser',
  'capability.files': 'Files',
  'capability.vault': 'Vault',
  'capability.computer_use': 'Computer Use',
  'capability.shell': 'Shell',
  'capability.external_tools': 'External tools',

  // Setup and observability
  'common.ready': 'Ready',
  'common.verified': 'Verified',
  'common.not_determined': 'Not determined',
  'onboarding.eyebrow': 'Local setup',
  'onboarding.skip_link': 'Skip to local setup',
  'onboarding.title': 'Prepare your private workspace',
  'onboarding.subtitle': 'LocalComet checks each available subsystem from live desktop responses. Unknown and unavailable states remain explicit.',
  'onboarding.local_boundary': 'Local by default. Downloads require confirmation.',
  'onboarding.environment': 'Environment check',
  'onboarding.manage': 'Manage',
  'onboarding.control_plane': 'Control Plane',
  'onboarding.sidecar': 'Python sidecar',
  'onboarding.catalog': 'Approved catalog',
  'onboarding.runtime': 'Managed runtime',
  'onboarding.model': 'Approved model',
  'onboarding.inference': 'Inference connection',
  'onboarding.not_installed': 'Not installed',
  'onboarding.not_connected': 'Not connected',
  'onboarding.open_models': 'Open model setup',
  'onboarding.continue_chat': 'Continue to chat',
  'onboarding.boundary': 'This screen does not infer hardware support, application-data health, microphone access, or completion persistence. Only backend-derived states are shown.',
  'observability.eyebrow': 'Live local data',
  'observability.title': 'Logs / Observability Room',
  'observability.subtitle': 'Validated session events and the bounded managed-runtime log tail.',
  'observability.refresh': 'Refresh runtime',
  'observability.refreshing': 'Refreshing',
  'observability.boundary': 'These rows support diagnosis. They are not durable or authoritative evidence, and no diagnostic bundle is claimed.',
  'observability.control_events': 'Validated events',
  'observability.runtime_state': 'Runtime state',
  'observability.runtime_lines': 'Runtime log lines',
  'observability.validated_events': 'Control Plane events',
  'observability.session_only': 'session only',
  'observability.runtime_logs': 'Managed runtime',
  'observability.sanitized_tail': 'sanitized tail',
  'observability.no_runtime_logs': 'No managed-runtime log lines are available.',

  // Approved local model manager
  'models.title': 'Models',
  'models.boundary': 'Only the approved bootstrap engine and model can be installed here. The assistant itself does not gain internet access.',
  'models.refresh': 'Refresh',
  'models.engine': 'Local engine',
  'models.release': 'Release',
  'models.license': 'License',
  'models.size': 'Download size',
  'models.download': 'Download',
  'models.model': 'Local model',
  'models.not_available': 'Not available',
  'models.model_id': 'Model ID',
  'models.format': 'Format',
  'models.connection': 'Connection',
  'models.connected': 'Connected',
  'models.not_connected': 'Not connected',
  'models.current_download': 'Current download',
  'models.setup_progress': 'Local AI setup',
  'models.connecting': 'Validating and connecting the approved local model',
  'models.bytes': 'bytes',
  'models.cancel': 'Cancel',
  'models.actions': 'Model manager actions',
  'models.setup': 'Set up local AI',
  'models.install_engine': 'Install engine',
  'models.retry_engine': 'Retry engine',
  'models.download_model': 'Download model',
  'models.retry_model': 'Retry model',
  'models.connect': 'Connect',
  'models.disconnect': 'Disconnect',
  'models.remove_model': 'Remove model',
  'models.remove_hint': 'Disconnect the active model before removing it.',
  'models.download_error': 'The approved download could not finish. You can retry without changing its source or destination.',
  'models.confirm_title': 'Confirm local AI setup',
  'models.remove_confirm_title': 'Confirm model removal',
  'models.confirm_detail': 'This downloads the listed internal bootstrap artifacts to LocalComet-managed storage.',
  'models.remove_confirm_detail': 'This removes only the validated approved managed model. Chats, settings, the runtime, and your own files are not removed.',
  'models.combined_size': 'Combined download size',
  'models.confirm_boundary': 'The model remains local. This action does not give the assistant internet access.',
  'models.confirm': 'Confirm',
  'models.state.idle': 'Idle',
  'models.state.awaiting_confirmation': 'Awaiting confirmation',
  'models.state.checking_disk': 'Checking storage',
  'models.state.downloading': 'Downloading',
  'models.state.cancelling': 'Cancelling',
  'models.state.cancelled': 'Cancelled',
  'models.state.verifying_size': 'Verifying size',
  'models.state.verifying_hash': 'Verifying integrity',
  'models.state.validating_artifact': 'Validating artifact',
  'models.state.installing': 'Installing',
  'models.state.completed': 'Installed',
  'models.state.failed': 'Download failed',
  'models.state.valid': 'Installed',
  'models.state.not_installed': 'Not installed',
  'models.state.bytes_mismatch': 'Invalid size',
  'models.state.hash_mismatch': 'Invalid integrity',
  'models.state.invalid_path': 'Invalid managed path',
  'models.state.invalid_format': 'Invalid format',
  'models.state.missing_required_file': 'Incomplete engine',
  'models.state.unexpected_file': 'Unexpected engine file',
  'models.state.io_error': 'Validation error',

  // Project
  'project.detail': 'Local chat with model',

  // Project labels
  'project.label_frontend': 'Frontend',
  'project.label_russian_ux': 'Russian UX',

  // Risk
  'risk.read_only': 'Read-only',
  'risk.guarded': 'Requires approval',
  'risk.dangerous': 'Dangerous',

  // Review Center
  "nav.review_center": "Review Center",
  "review.skip_link": "Skip to Review Center",
  "review.workspace_label": "LocalComet Review Center workspace",
  "review.eyebrow": "Read-only local review",
  "review.title": "Review Center",
  "review.subtitle": "Immutable review evidence from the local Control Plane",
  "review.fixture_badge": "FIXTURE",
  "review.source.local_control_plane": "LOCAL CONTROL PLANE",
  "review.state.idle": "Idle",
  "review.state.idle_detail": "The read-only review collection has not been requested yet.",
  "review.state.loading": "Loading review artifacts",
  "review.state.loading_detail": "Requesting a bounded read-only projection through the local Control Plane.",
  "review.state.empty": "No review artifacts",
  "review.state.empty_detail": "The production review collection is truthfully empty. No fixture fallback was used.",
  "review.state.error": "Review Center unavailable",
  "review.state.error_detail": "The read-only review request failed.",
  "review.retry": "Retry",
  "review.refresh": "Refresh",
  "review.unavailable": "Unavailable",
  "review.copy": "Copy",
  "review.copied": "Copied",
  "review.copy_failed": "Copy failed",
  "review.copy_success": "Value copied.",
  "review.copy_failure": "Value could not be copied. Copy it manually.",
  "review.none": "None",
  "review.yes": "Yes",
  "review.no": "No",
  "review.changed": "Changed",
  "review.unchanged": "Unchanged",
  "review.status.CLEAR": "CLEAR",
  "review.status.REVIEW_REQUIRED": "REVIEW REQUIRED",
  "review.status.BLOCKED": "BLOCKED",
  "review.queue_eyebrow": "Review queue",
  "review.queue_title": "Review artifacts",
  "review.queue_label": "Review queue",
  "review.queue_mobile_label": "Select a review artifact",
  "review.queue_help": "Use Arrow keys, Home, and End to move through the bounded review queue.",
  "review.queue_truncated": "The bounded queue is truncated. Next offset:",
  "review.detail_truncated.badge": "BOUNDED DETAIL",
  "review.detail_truncated.title": "Projected detail is bounded",
  "review.detail_truncated.detail": "One or more review fields were truncated by the accepted projection. Displayed values are previews, not complete source material.",
  "review.identity.eyebrow": "Exact binding",
  "review.identity.title": "Review identity",
  "review.identity.proposal_id": "Proposal ID",
  "review.identity.review_identity": "Review artifact identity",
  "review.identity.change_identity": "Change identity",
  "review.identity.expected_revision": "Expected Vault revision",
  "review.identity.observed_revision": "Observed Vault revision",
  "review.identity.target_id": "Target stable ID",
  "review.identity.operation": "Operation",
  "review.validation.eyebrow": "Source validation",
  "review.validation.title": "Validation information",
  "review.validation.contract": "Validation contract",
  "review.validation.content_hash": "Proposal content hash",
  "review.validation.validated_revision": "Validated Vault revision",
  "review.validation.snapshot": "Validation snapshot",
  "review.validation.snapshot_truncated": "The validation snapshot preview is truncated. Exact identities remain visible.",
  "review.validation.source_findings": "Source validation findings",
  "review.validation.outcome.VALID": "VALID",
  "review.validation.outcome.INVALID": "INVALID",
  "review.validation.outcome.STALE": "STALE",
  "review.findings.eyebrow": "Conflict analysis",
  "review.findings.title": "Findings",
  "review.findings.none": "No conflict findings.",
  "review.severity.BLOCKING": "BLOCKING",
  "review.severity.REVIEW": "REVIEW",
  "review.metadata.eyebrow": "Structured content",
  "review.metadata.title": "ProposedNoteContent projection",
  "review.metadata.fields": "fields",
  "review.metadata.projection_note": "All 18 reviewable ProposedNoteContent fields are shown from the bounded projection. This is not a claim about future serialized Vault bytes.",
  "review.metadata.changed": "Metadata field changed",
  "review.metadata.before": "Before",
  "review.metadata.after": "After",
  "review.metadata.field.title": "Title",
  "review.metadata.field.body_text": "Body text",
  "review.metadata.field.type": "Type",
  "review.metadata.field.status": "Status",
  "review.metadata.field.knowledge_layer": "Knowledge layer",
  "review.metadata.field.evidence_class": "Evidence class",
  "review.metadata.field.authority": "Authority",
  "review.metadata.field.canonical": "Canonical",
  "review.metadata.field.canonical_scope": "Canonical scope",
  "review.metadata.field.aliases": "Aliases",
  "review.metadata.field.releases": "Releases",
  "review.metadata.field.source_paths": "Source paths",
  "review.metadata.field.evidence_refs": "Evidence references",
  "review.metadata.field.supersedes": "Supersedes",
  "review.metadata.field.superseded_by": "Superseded by",
  "review.metadata.field.updated": "Updated",
  "review.metadata.field.last_reviewed": "Last reviewed",
  "review.metadata.field.verified_at": "Verified at",
  "review.diff.eyebrow": "Body comparison",
  "review.diff.title": "Text diff",
  "review.diff.preview_label": "Diff preview",
  "review.diff.not_full_diff": "Bounded preview — not the full diff.",
  "review.diff.truncated": "TRUNCATED",
  "review.diff.no_material": "No normal change material",
  "review.diff.blocked_suppression": "BLOCKED reviews suppress diff, representation delta, and change identity.",
  "review.diff.empty": "(semantic body diff is empty)",
  "review.diff.hash": "Complete diff hash",
  "review.diff.bytes": "Complete diff UTF-8 bytes",
  "review.diff.full_available": "Complete diff exists in the source artifact",
  "review.diff.preview_truncated": "Preview truncated",
  "review.representation.eyebrow": "Byte and text representation",
  "review.representation.title": "Representation delta",
  "review.representation.only": "REPRESENTATION-ONLY CHANGE",
  "review.representation.no_material": "Representation delta is unavailable for this BLOCKED review.",
  "review.representation.identity": "Representation identity",
  "review.representation.line_endings": "Line-ending profile",
  "review.representation.terminal_newline": "Terminal newline",
  "review.representation.source_bytes_known": "Proposed source bytes known",
  "review.representation.bytes_same_text": "Source bytes changed with identical decoded text",
  "review.representation.raw_semantic_equal": "Raw text changed with semantic equality",
  "review.representation.semantic_changed": "Semantic body content changed",
  "review.representation.absent": "ABSENT",
  "review.preview.eyebrow": "Bounded output",
  "review.preview.title": "Human review preview",
  "review.preview.truncated": "TRUNCATED",
  "review.decision.eyebrow": "Local decision intent",
  "review.decision.title": "Decision confirmation",
  "review.decision.fixture_only": "FIXTURE ONLY",
  "review.decision.real_read_only": "REAL READ-ONLY",
  "review.decision.unavailable": "Decision artifact integration is not available in this stage. APPROVE, REJECT, and REQUEST CHANGES are disabled for real artifacts.",
  "review.decision.boundary": "These controls record only an in-memory fixture intent. They create no authoritative decision identity and perform no Vault, publication, merge, execution, persistence, or Tauri action.",
  "review.decision.actions": "Fixture decision actions",
  "review.decision.approve": "APPROVE",
  "review.decision.reject": "REJECT",
  "review.decision.request_changes": "REQUEST CHANGES",
  "review.decision.dialog_title": "Confirm fixture decision intent",
  "review.decision.dialog_description": "Review the exact proposal binding before recording a local fixture-only intent.",
  "review.decision.intent": "Decision intent",
  "review.decision.comment": "Comment",
  "review.decision.required": "Required for REQUEST CHANGES",
  "review.decision.comment_placeholder": "Add a bounded local review comment",
  "review.decision.cancel": "Cancel",
  "review.decision.confirm": "Confirm fixture intent",
  "review.decision.blocked_approval": "APPROVE is unavailable for a BLOCKED review.",
  "review.decision.comment_required": "REQUEST CHANGES requires a non-empty comment.",
  "review.decision.hard_stop_title": "HARD STOP",
  "review.decision.hard_stop_detail": "Confirmation ends at a fixture-only UI result. No authoritative decision artifact is created.",
  "review.decision.real_hard_stop_detail": "A genuine e9c decision artifact may be created, but no authoritative action occurs. The Vault remains unchanged; publication, persistence, merge, execution, and automatic approval remain unavailable.",
  "review.decision.fixture_result": "Fixture result:",
  "review.decision.fixture_hard_stop": "Intent recorded in memory only. HARD STOP — no authority, persistence, or Tauri call.",
  "review.phase_boundary.title": "Phase 1 authority boundary",
  "review.phase_boundary.detail": "Real IPC is read-only list/get only. e9c decisions, Vault writes, publication, merge, execution, and persistence remain outside this stage.",

  "review.queue_visible_count": "Visible review artifacts and total inbox count",
  "review.queue_filtered_empty": "No review artifacts match the active filters.",
  "review.stale.badge": "STALE",
  "review.stale.unknown": "FRESHNESS UNKNOWN",
  "review.stale.title": "This review is stale",
  "review.stale.detail": "The current Vault revision no longer matches the immutable review artifact. Create a fresh review before making a decision.",
  "review.stale.unknown_title": "Freshness is unknown",
  "review.stale.unknown_detail": "The current Vault revision is unavailable. Human decisions are disabled until freshness can be proven.",
  "review.command_bar.label": "Knowledge operations command bar",
  "review.command_bar.search": "Search",
  "review.command_bar.search_placeholder": "Search identity, target, operation, or status",
  "review.command_bar.status_filter": "Status",
  "review.command_bar.operation_filter": "Operation",
  "review.command_bar.sort": "Sort",
  "review.command_bar.sort_status": "Status, then identity",
  "review.command_bar.sort_identity": "Identity",
  "review.command_bar.visible": "visible",
  "review.command_bar.clear": "Clear filters",
  "review.command_bar.revalidate": "Refresh and revalidate",
  "review.decision.real_e9c": "REAL e9c DECISION",
  "review.decision.real_boundary": "These controls create one genuine immutable e9c HumanReviewDecision bound to the exact review and current Vault revision. The result is session-only evidence and grants no write, publication, persistence, or execution authority.",
  "review.decision.stale": "This review is stale. Refresh and produce a new review artifact before deciding.",
  "review.decision.freshness_unknown": "Freshness cannot be proven. Decision controls remain disabled.",
  "review.decision.stale_or_unknown": "Decision unavailable until the exact current Vault revision is proven.",
  "review.decision.real_result": "Decision artifact created:",
  "review.decision.decision_identity": "Decision identity",
  "review.decision.vault_modified": "Vault modified",
  "review.decision.dialog_description_fixture": "Review the exact proposal binding before recording a local fixture-only intent.",
  "review.decision.dialog_description_real": "Confirm the exact proposal, review, change, and Vault-revision binding before creating session-only e9c evidence.",
  "review.decision.actor_identifier": "Reviewer identifier",
  "review.decision.actor_display_name": "Reviewer display name",
  "review.decision.actor_evidence_only": "Reviewer metadata is descriptive evidence only. LocalComet does not authenticate human identity in this stage.",
  "review.decision.actor_required": "Reviewer identifier and display name are required.",
  "review.decision.submitting": "Creating decision…",
  "review.decision.policy_blocked": "The decision was rejected by the exact review policy or stale-revision gate.",
  "review.decision.failed": "The decision artifact could not be created.",
  "review.decision.real_hard_stop": "A genuine immutable e9c decision artifact was returned to the UI. HARD STOP — the Vault was not modified and no publication, persistence, merge, execution, or automatic approval occurred.",
  "review.activity.eyebrow": "Session evidence",
  "review.activity.title": "Activity timeline",
  "review.activity.empty": "No session activity yet.",
  "review.activity.boundary": "Bounded in-memory session activity only. It disappears when this application session ends.",
  "review.activity.inbox_refresh": "Inbox refreshed and Vault freshness re-evaluated.",
  "review.activity.connected": "Local Control Plane review channel connected.",
  "review.activity.artifact_opened": "Review artifact opened.",
  "review.activity.stale_review": "Stale review detected.",
  "review.activity.decision_created": "Human review decision artifact created.",
  "review.activity.error": "Bounded review error recorded.",
  "review.activity.snapshot_refresh_failed": "Decision succeeded, but the follow-up diagnostics snapshot could not be refreshed.",
  "review.diagnostics.eyebrow": "Bounded diagnostics",
  "review.diagnostics.title": "Command Center diagnostics",
  "review.diagnostics.command_center": "Command Center",
  "review.diagnostics.frontend_contract": "Frontend projection contract",
  "review.diagnostics.tauri": "Tauri bridge",
  "review.diagnostics.sidecar": "Sidecar",
  "review.diagnostics.python_runtime": "Python sidecar runtime",
  "review.diagnostics.inbox": "Inbox count",
  "review.diagnostics.stale": "Stale count",
  "review.diagnostics.blocked": "Blocked count",
  "review.diagnostics.decisions": "Session decisions",
  "review.diagnostics.last_error": "Last bounded error code",
  "review.diagnostics.boundary": "No environment variables, absolute paths, prompts, secrets, or unselected Vault content are exposed here.",
  "review.connection.IDLE": "IDLE",
  "review.connection.CONNECTING": "CONNECTING",
  "review.connection.CONNECTED": "CONNECTED",
  "review.connection.UNAVAILABLE": "UNAVAILABLE",
  "review.connection.ERROR": "ERROR",
};
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/i18n/index.ts (31 строк, 939 байт)

````typescript
import { writable, derived } from 'svelte/store';
import { ru } from './ru';
import { en } from './en';
import { loadUiPreferences, updateUiPreferences } from '$lib/stores/uiPreferences';

export type Language = 'ru' | 'en';
export type TranslationMap = Record<string, string>;

function getInitialLanguage(): Language {
  return loadUiPreferences().locale;
}

function setDocumentLang(lang: Language): void {
  if (typeof document === 'undefined') return;
  document.documentElement.lang = lang;
}

export const locale = writable<Language>(getInitialLanguage());

export const t = derived(locale, ($locale) => {
  const map: TranslationMap = $locale === 'en' ? en : ru;
  setDocumentLang($locale);
  return (key: string): string => map[key] ?? key;
});

export function setLocale(lang: Language): void {
  if (lang !== 'ru' && lang !== 'en') return;
  locale.set(lang);
  updateUiPreferences({ locale: lang });
  setDocumentLang(lang);
}
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/i18n/ru.ts (688 строк, 52216 байт)

````typescript
import type { TranslationMap } from './index';

export const ru: TranslationMap = {
  // Navigation
  'nav.chat': 'Чат',
  'nav.tasks': 'Задачи',
  'nav.diagnostics': 'Диагностика',
  'nav.audit': 'Аудит',
  'nav.settings': 'Настройки',
  'nav.setup': 'Настройка',
  'nav.main': 'Основная навигация',
  'app.title_bar': 'Панель приложения LocalComet',
  'nav.later': 'позже',

  // Sidebar
  'sidebar.label': 'Боковая панель сессий',
  'sidebar.new_thread': 'Новый тред',
  'sidebar.new_thread_title': 'Создание треда происходит при старте демо Control Plane',
  'sidebar.collapse': 'Свернуть/развернуть боковую панель',
  'sidebar.toggle': 'Показать или скрыть боковую панель чатов',
  'sidebar.pinned_label': 'Закреплённый Control Plane',
  'sidebar.pinned': 'Закреплено',
  'sidebar.project_labels': 'Метки проекта',

  // Sidebar groups
  'group.local_chats': 'Локальные чаты',
  'group.reserved': 'Зарезервировано',
  'group.disabled': 'Отключено',

  // Sidebar items
  'item.new_chat': 'Новый чат',
  'item.cancellation_demo': 'Демо отмены',
  'item.audit': 'Аудит',
  'item.documents': 'Документы',
  'item.model_not_connected': 'Модель не подключена',
  'item.model_required': 'Требуется модель',
  'item.later': 'Позже',

  // Chat
  'chat.type_message': 'Введите сообщение…',
  'chat.connect_model_first': 'Сначала подключите модель',
  'chat.send': 'Отправить',
  'chat.stop': 'Остановить',
  'chat.model_responding': 'Модель отвечает…',
  'chat.tools_unavailable': 'Инструменты (пока недоступны)',
  'chat.model_not_connected': 'Модель не подключена',
  'chat.model_not_connected_detail': 'Подключите локальную модель, чтобы начать безопасный диалог.',
  'chat.model_unavailable': 'Локальная модель недоступна',
  'chat.model_unavailable_detail': 'LocalComet использует локальную модель. Доступен только текст явно включённых файлов; у помощника нет доступа к интернету, произвольным файлам, почте, Vault, shell, Computer Use и внешним инструментам. Подключите одобренную локальную модель, чтобы начать.',
  'chat.model_loading': 'Подготовка локальной модели',
  'chat.model_loading_detail': 'LocalComet проверяет управляемую среду и загружает одобренную модель. Отправка будет недоступна, пока готовность не подтверждена.',
  'chat.model_loading_status': 'Идёт проверка и загрузка',
  'chat.first_use_ready': 'Локальный помощник готов',
  'chat.first_use_detail': 'Сообщения обрабатывает готовая локальная модель. Можно явно включить текст выбранных файлов; произвольный доступ к файлам, интернету, почте, Vault, shell, Computer Use и внешним инструментам недоступен.',
  'chat.local_only_status': 'Только локальный текстовый диалог',
  'chat.state_accepted': 'Запрос принят',
  'chat.state_streaming': 'Локальная генерация',
  'chat.state_cancelled': 'Отменено — частичный ответ сохранён',
  'chat.state_timed_out': 'Время ожидания истекло — можно безопасно повторить',
  'chat.state_failed': 'Запрос завершился ошибкой — можно безопасно повторить',
  'chat.retry': 'Повторить',
  'chat.request_failed_detail': 'Локальный ответ завершился ошибкой. Повторите запрос, когда модель готова; приватный путь и стек не показываются.',
  'chat.request_timed_out_detail': 'Время локального ответа истекло. Когда модель готова, запрос можно безопасно повторить.',
  'chat.connect_model': 'Подключить модель',
  'chat.setup_local_ai': 'Настроить локальный AI',
  'chat.open_models': 'Открыть модели',
  'chat.model_installing': 'Настраивается локальный AI…',
  'chat.model_connecting': 'Подключение модели…',
  'chat.user_message': 'Сообщение пользователя',
  'chat.model_response': 'Ответ модели',
  'chat.you': 'Вы',
  'chat.model': 'Модель',
  'chat.demo': 'ДЕМО',
  'chat.message_history': 'История сообщений',

  // Approval
  'approval.disabled': 'Отключено',
  'approval.section_aria': 'Подтверждения отключены',
  'approval.confirm': 'Подтвердить',
  'approval.reject': 'Отклонить',
  'approval.confirm_aria': 'Подтвердить отключено, так как desktop bridge не подключен',
  'approval.reject_aria': 'Отклонить отключено, так как desktop bridge не подключен',

  // Files
  'files.title': 'Файлы',
  'files.read_only': 'Только явно выбранные локальные текстовые файлы · только чтение',
  'files.add': 'Добавить файлы',
  'files.selecting': 'Открыт выбор…',
  'files.loading': 'Проверяем доступность безопасного выбора файлов…',
  'files.unavailable': 'Безопасный выбор файлов недоступен в этой среде.',
  'files.empty': 'Файлы не выбраны. LocalComet не сканирует диски и каталоги.',
  'files.selected_list': 'Выбранные файлы',
  'files.size': 'Размер',
  'files.bytes': 'байт',
  'files.characters': 'символов',
  'files.added': 'Добавлен',
  'files.location': 'Расположение',
  'files.include': 'Включить в следующий запрос',
  'files.preview': 'Предпросмотр',
  'files.loading_preview': 'Читаем…',
  'files.forget': 'Удалить и забыть',
  'files.forgetting': 'Забываем…',
  'files.context_total': 'Контекст следующего запроса:',
  'files.context_excerpt_notice': 'Если текст не помещается в лимит запроса модели, будет включён детерминированный ограниченный фрагмент с точными счётчиками.',
  'files.inclusion.full': 'В последний запрос включён полный файл',
  'files.inclusion.excerpt': 'В последний запрос включён ограниченный фрагмент',
  'files.preview_eyebrow': 'Безопасный предпросмотр',
  'files.close_preview': 'Закрыть предпросмотр файла',
  'files.preview_truncated': 'показан ограниченный фрагмент',
  'files.dismiss_error': 'Закрыть ошибку файла',
  'files.status.ready': 'Читается',
  'files.status.missing': 'Отсутствует',
  'files.status.changed': 'Изменён',
  'files.status.reparse_point': 'Ссылка запрещена',
  'files.status.unreadable': 'Не читается',
  'files.error.LC_FILE_UNSUPPORTED_TYPE': 'Неподдерживаемый тип. Разрешены TXT, MD, JSON, YAML, YML, CSV и LOG.',
  'files.error.LC_FILE_TOO_LARGE': 'Файл больше 2 МиБ.',
  'files.error.LC_FILE_BINARY': 'Файл похож на бинарный или содержит недопустимые управляющие символы.',
  'files.error.LC_FILE_INVALID_UTF8': 'Файл не является допустимым текстом UTF-8.',
  'files.error.LC_FILE_MISSING': 'Файл больше не существует.',
  'files.error.LC_FILE_CHANGED': 'Файл изменился после выбора. Забудьте его и выберите заново.',
  'files.error.LC_FILE_ACCESS_DENIED': 'Доступ к выбранному файлу безопасно отклонён.',
  'files.error.LC_FILE_REPARSE_POINT': 'Символические ссылки, junction и reparse point запрещены.',
  'files.error.LC_FILE_CONTEXT_LIMIT': 'Общий размер включённых файлов превышает 5 МиБ или доступный лимит запроса.',
  'files.error.LC_FILE_UNREADABLE': 'Не удалось безопасно прочитать выбранный файл.',
  'files.error.LC_FILE_SELECTION_LIMIT': 'За одну сессию можно выбрать не более 32 файлов.',
  'files.error.LC_FILE_PICKER_UNAVAILABLE': 'Системный выбор файлов недоступен.',
  'files.error.LC_FILE_STATE_UNAVAILABLE': 'Состояние выбранных файлов недоступно. Перезапустите LocalComet перед новым выбором файлов.',
  'files.error.default': 'Операция с выбранным файлом завершилась безопасным отказом.',

  // Project Knowledge
  'knowledge.title': 'Знания проекта',
  'knowledge.unavailable': 'Контекст проекта пока недоступен',
  'knowledge.unavailable_detail': 'Данные проекта не отправляются. Это не долговременная память.',
  'knowledge.enabled': 'Включено для этой сессии',
  'knowledge.disabled': 'Отключено',
  'knowledge.toggle_label': 'Включить знания проекта для следующего запроса',
  'knowledge.approval_label': 'Предпросмотр знаний проекта для подтверждения',
  'knowledge.sources': 'источников',
  'knowledge.characters': 'символов',
  'knowledge.vault': 'Хранилище',
  'knowledge.selected_sections': 'Выбранные разделы',
  'knowledge.lines': 'Строки',
  'knowledge.retrieving': 'Подбираем ограниченный контекст проекта… Запрос модели ещё не отправлен.',
  'knowledge.include_send': 'Включить знания и отправить',
  'knowledge.send_without': 'Отправить без знаний',
  'knowledge.cancel': 'Отменить',
  'knowledge.retry': 'Повторить',
  'knowledge.refresh': 'Обновить предпросмотр',
  'knowledge.stale_message': 'Знания проекта изменились. Обновите предпросмотр.',
  'knowledge.failure_message': 'Не удалось подготовить знания проекта. Модели ничего не отправлено.',
  'knowledge.state_off': 'Отключено',
  'knowledge.state_retrieving': 'Подбор знаний',
  'knowledge.state_preview_ready': 'Готово к отправке',
  'knowledge.state_deciding': 'Сохраняем решение',
  'knowledge.state_dispatching': 'Отправляем модели',
  'knowledge.state_injected': 'Знания отправлены',
  'knowledge.state_rejected': 'Отправлено без знаний',
  'knowledge.state_cancelled': 'Отменено — не отправлено',
  'knowledge.state_failed': 'Ошибка предпросмотра',
  'knowledge.state_stale': 'Предпросмотр устарел',

  // Connection states
  'conn.not_connected': 'Не подключено',
  'conn.status': 'Состояние подключения',
  'conn.model_connected': 'Модель: Подключена',
  'conn.connecting': 'Подключение',
  'conn.ready': 'Готово',
  'conn.generating': 'Генерация',
  'conn.error': 'Ошибка',
  'conn.request_generating': 'Запрос: генерация',
  'conn.request_error': 'Запрос: ошибка',
  'conn.model_ready': 'Модель: готова',
  'conn.model_loading': 'Модель: загрузка',
  'conn.model_unavailable': 'Модель: недоступна',
  'conn.model_error': 'Модель: ошибка',
  'conn.runtime_ready': 'Среда: готова',

  // Model Setup
  'setup.title': 'Подключить модель',
  'setup.close': 'Закрыть',
  'setup.external_tab': 'Внешний локальный сервер',
  'setup.managed_tab': 'Управляемая локальная модель',
  'setup.external_desc': 'Подключение к OpenAI-совместимому серверу на localhost',
  'setup.managed_desc': 'Управляемая llama.cpp модель, запускаемая локально',
  'setup.external_diagnostics_only': 'Внешняя loopback-привязка доступна только для диагностики. Для чата нужна одобренная управляемая модель.',
  'setup.step_port': '1. Порт',
  'setup.step_model': '2. Модель',
  'setup.step_mode': '3. Режим',
  'setup.step_connect': '4. Подключить',
  'setup.port': 'Порт',
  'setup.check_server': 'Проверить сервер',
  'setup.find_models': 'Найти модели',
  'setup.probing': 'Проверка...',
  'setup.server_unavailable': 'Сервер недоступен',
  'setup.server_ready': 'Сервер готов',
  'setup.model': 'Модель',
  'setup.select_model': 'Выберите найденную модель',
  'setup.response_mode': 'Режим ответа',
  'setup.no_system_instruction': 'Без системной инструкции',
  'setup.safe_mode': 'Безопасный режим LocalComet',
  'setup.connect': 'Подключить модель',
  'setup.binding_id': 'Идентификатор подключения',
  'setup.runtime_not_installed': 'Управляемый runtime пока не установлен.',
  'setup.install_available': 'Установка появится в следующем обновлении.',
  'setup.runtime_status': 'Статус',
  'setup.runtime_version': 'Версия runtime',
  'setup.runtime_model': 'Локальная модель',
  'setup.runtime_inference': 'Инференс',
  'setup.not_installed': 'Не установлен',
  'setup.not_checked': 'Не проверен',
  'setup.not_selected': 'Не выбрана',
  'setup.connected': 'Подключена',
  'setup.needs_binding': 'Требуется подключение',
  'setup.refresh': 'Обновить',
  'setup.start_runtime': 'Запустить runtime',
  'setup.stop_runtime': 'Остановить runtime',
  'setup.select_local_model': 'Выберите локальную модель',
  'setup.external_mode': 'Внешний локальный сервер',
  'setup.managed_mode': 'Управляемая локальная модель',

  // Diagnostics
  'diag.title': 'Диагностика',
  'diag.toggle': 'Показать или скрыть диагностику',
  'diag.runtime': 'Среда выполнения',
  'diag.runtime_state': 'Состояние системы',
  'diag.close': 'Закрыть',
  'diag.tab_Обзор': 'Обзор',
  'diag.tab_Телеметрия': 'Телеметрия',
  'diag.tab_События': 'События',
  'diag.tab_Политика': 'Политика',
  'diag.tab_Проверка': 'Проверка',
  'diag.sections_label': 'Разделы диагностики',
  'diag.summary': 'Обзор',
  'diag.session': 'Сессия',
  'diag.thread': 'Диалог',
  'diag.turn': 'Запрос',
  'diag.turn_state': 'Состояние запроса',
  'diag.current_item': 'Текущий элемент',
  'diag.last_event': 'Последнее событие',
  'diag.event_count': 'Событий',
  'diag.model_gateway': 'Шлюз модели',
  'diag.model_called': 'Модель вызвана',
  'diag.tools_executed': 'Инструментов выполнено',
  'diag.persistence': 'Хранение данных',
  'diag.provider': 'Провайдер',
  'diag.response_mode': 'Режим ответа',
  'diag.autonomous': 'Автономные действия',
  'diag.confirmation': 'Подтверждение',
  'diag.result_check': 'Проверка результата',
  'diag.status': 'Статус',
  'diag.event_stream': 'ПОТОК СОБЫТИЙ',
  'diag.event_stream_label': 'Поток проверенных событий',
  'diag.no_validated_events': 'Проверенные события пока не получены.',
  'diag.policy_decision': 'РЕШЕНИЕ ПОЛИТИКИ',
  'diag.policy_decision_label': 'Решение политики',
  'diag.not_evaluated': 'Не оценивалось',
  'diag.unknown': 'Неизвестно',
  'diag.not_configured': 'Не настроено',
  'diag.probing': 'Проверка подключения',
  'diag.unavailable': 'Недоступно',
  'diag.ready': 'Готово',
  'diag.connected': 'Подключено',
  'diag.binding_required': 'Требуется подключение модели',
  'diag.bound': 'Подключено',
  'diag.generating': 'Генерация',
  'diag.cancelling': 'Отмена',
  'diag.failed': 'Ошибка',
  'diag.off': 'Отключено',
  'diag.disabled': 'Отключено',
  'diag.not_run': 'Не запускалось',
  'diag.result_not_run': 'Не запускалась',
  'diag.yes': 'Да',
  'diag.no': 'Нет',
  'diag.running': 'Выполняется',
  'diag.completed': 'Завершено',
  'diag.cancelled': 'Отменено',
  'diag.error': 'Ошибка',
  'diag.not_started': 'Не запускалось',
  'diag.demo_controls': 'Демо-контролы',
  'diag.start_demo': 'Запустить демо отмены',
  'diag.cancel_demo': 'Отменить текущий демо-шот',
  'diag.about_versions': 'О версиях',
  'diag.desktop_shell': 'Оболочка приложения',
  'diag.control_plane_connected': 'Контур управления: Подключено',
  'diag.control_plane_starting': 'Контур управления: Запуск',
  'diag.control_plane_unavailable': 'Контур управления: Недоступно',
  'diag.control_plane_error': 'Контур управления: Ошибка',
  'diag.control_plane_unknown': 'Контур управления: Неизвестно',
  'diag.control_plane_not_connected': 'Контур управления должен быть подключен',
  'diag.sidecar_ready': 'Служебный процесс: Готово',
  'diag.sidecar_unknown': 'Служебный процесс: Неизвестно',

  // Common
  'common.skip_link': 'Перейти к чату',

  // Палитра команд
  'commandPalette.label': 'Палитра команд',
  'commandPalette.search': 'Найти команду',
  'commandPalette.placeholder': 'Введите команду…',
  'commandPalette.commands': 'Доступные команды',
  'commandPalette.empty': 'Подходящих команд нет',
  'commandPalette.command.chat': 'Открыть чат',
  'commandPalette.command.settings': 'Открыть настройки',
  'commandPalette.command.setup': 'Открыть локальную настройку',
  'commandPalette.command.models': 'Открыть управление моделями',
  'commandPalette.command.observability': 'Открыть логи и наблюдаемость',
  'commandPalette.command.showDiagnostics': 'Показать диагностику',
  'commandPalette.command.hideDiagnostics': 'Скрыть диагностику',

  // Theme
  'theme.manage': 'Управление темой',
  'theme.system': 'Использовать системную тему',
  'theme.light': 'Использовать светлую тему',
  'theme.dark': 'Использовать тёмную тему',

  // Demo messages
  'demo.start_dialog': 'Начать диалог.',
  'demo.model_not_connected': 'Модель не подключена. Нажмите «Подключить модель», чтобы начать безопасный диалог.',

  // Language
  'lang.select': 'Выбрать язык',
  'lang.russian': 'Русский',
  'lang.english': 'English',

  // Settings
  'settings.title': 'Настройки',
  'settings.sections': 'Разделы настроек',
  'settings.tab_interface': 'Интерфейс',
  'settings.tab_models': 'Модели',
  'settings.tab_observability': 'Логи',
  'settings.tab_about': 'О приложении',
  'settings.close': 'Закрыть настройки',
  'settings.appearance': 'Оформление',
  'settings.theme': 'Тема',
  'settings.theme_system': 'Системная',
  'settings.theme_light': 'Светлая',
  'settings.theme_dark': 'Тёмная',
  'settings.language': 'Язык',
  'settings.diagnostics': 'Диагностика',
  'settings.connection_state': 'Подключение контура управления',
  'settings.show_diagnostics': 'Показать диагностику',
  'settings.hide_diagnostics': 'Скрыть диагностику',
  'settings.about': 'О приложении',
  'settings.application': 'Приложение',
  'settings.version': 'Версия',
  'settings.build': 'Сборка',
  'settings.build_status': 'Статус сборки',
  'settings.capabilities': 'Текущие возможности',
  'settings.available': 'Доступно',
  'settings.unavailable': 'Недоступно',
  'settings.project_context_unavailable': 'Контекст проекта недоступен. Files передаёт только текст файлов, явно включённых в текущий запрос; помощник не просматривает репозитории, каталоги, другие файлы или Vault. Это не долговременная память.',
  'capability.local_chat': 'Локальный чат',
  'capability.local_model_inference': 'Вывод локальной модели',
  'capability.approved_model_setup': 'Настройка одобренной локальной модели',
  'capability.internet': 'Доступ помощника к интернету',
  'capability.email': 'Электронная почта',
  'capability.browser': 'Браузер',
  'capability.files': 'Файлы',
  'capability.vault': 'Vault',
  'capability.computer_use': 'Computer Use',
  'capability.shell': 'Shell',
  'capability.external_tools': 'Внешние инструменты',

  // Настройка и наблюдаемость
  'common.ready': 'Готово',
  'common.verified': 'Проверено',
  'common.not_determined': 'Не определено',
  'onboarding.eyebrow': 'Локальная настройка',
  'onboarding.skip_link': 'Перейти к локальной настройке',
  'onboarding.title': 'Подготовьте приватное рабочее пространство',
  'onboarding.subtitle': 'LocalComet проверяет доступные подсистемы по реальным ответам desktop-бэкенда. Неизвестные и недоступные состояния показаны явно.',
  'onboarding.local_boundary': 'Локально по умолчанию. Загрузки требуют подтверждения.',
  'onboarding.environment': 'Проверка окружения',
  'onboarding.manage': 'Управление',
  'onboarding.control_plane': 'Контур управления',
  'onboarding.sidecar': 'Python sidecar',
  'onboarding.catalog': 'Одобренный каталог',
  'onboarding.runtime': 'Управляемый runtime',
  'onboarding.model': 'Одобренная модель',
  'onboarding.inference': 'Подключение вывода',
  'onboarding.not_installed': 'Не установлено',
  'onboarding.not_connected': 'Не подключено',
  'onboarding.open_models': 'Открыть настройку модели',
  'onboarding.continue_chat': 'Перейти в чат',
  'onboarding.boundary': 'Этот экран не предполагает поддержку оборудования, исправность app-data, доступ к микрофону или сохранённое завершение. Показаны только состояния из бэкенда.',
  'observability.eyebrow': 'Живые локальные данные',
  'observability.title': 'Логи / комната наблюдаемости',
  'observability.subtitle': 'Валидированные события сессии и ограниченный хвост логов управляемого runtime.',
  'observability.refresh': 'Обновить runtime',
  'observability.refreshing': 'Обновление',
  'observability.boundary': 'Эти строки помогают диагностике. Они не являются долговременным или авторитетным доказательством; диагностический пакет не заявляется.',
  'observability.control_events': 'Валидированные события',
  'observability.runtime_state': 'Состояние runtime',
  'observability.runtime_lines': 'Строки runtime-лога',
  'observability.validated_events': 'События контура управления',
  'observability.session_only': 'только сессия',
  'observability.runtime_logs': 'Управляемый runtime',
  'observability.sanitized_tail': 'санитизированный хвост',
  'observability.no_runtime_logs': 'Строки лога управляемого runtime пока недоступны.',

  // Управление одобренной локальной моделью
  'models.title': 'Модели',
  'models.boundary': 'Здесь можно установить только одобренные bootstrap-движок и модель. Сам помощник не получает доступ к интернету.',
  'models.refresh': 'Обновить',
  'models.engine': 'Локальный движок',
  'models.release': 'Релиз',
  'models.license': 'Лицензия',
  'models.size': 'Размер загрузки',
  'models.download': 'Загрузка',
  'models.model': 'Локальная модель',
  'models.not_available': 'Недоступна',
  'models.model_id': 'ID модели',
  'models.format': 'Формат',
  'models.connection': 'Подключение',
  'models.connected': 'Подключена',
  'models.not_connected': 'Не подключена',
  'models.current_download': 'Текущая загрузка',
  'models.setup_progress': 'Настройка локального AI',
  'models.connecting': 'Проверка и подключение одобренной локальной модели',
  'models.bytes': 'байт',
  'models.cancel': 'Отмена',
  'models.actions': 'Действия менеджера моделей',
  'models.setup': 'Настроить локальный AI',
  'models.install_engine': 'Установить движок',
  'models.retry_engine': 'Повторить движок',
  'models.download_model': 'Загрузить модель',
  'models.retry_model': 'Повторить модель',
  'models.connect': 'Подключить',
  'models.disconnect': 'Отключить',
  'models.remove_model': 'Удалить модель',
  'models.remove_hint': 'Перед удалением отключите активную модель.',
  'models.download_error': 'Одобренную загрузку не удалось завершить. Можно повторить её без смены источника или назначения.',
  'models.confirm_title': 'Подтвердите настройку локального AI',
  'models.remove_confirm_title': 'Подтвердите удаление модели',
  'models.confirm_detail': 'Будут загружены перечисленные внутренние bootstrap-артефакты в управляемое хранилище LocalComet.',
  'models.remove_confirm_detail': 'Будет удалена только проверенная одобренная управляемая модель. Чаты, настройки, runtime и ваши файлы не удаляются.',
  'models.combined_size': 'Общий размер загрузки',
  'models.confirm_boundary': 'Модель остаётся локальной. Это действие не даёт помощнику доступ к интернету.',
  'models.confirm': 'Подтвердить',
  'models.state.idle': 'Ожидание',
  'models.state.awaiting_confirmation': 'Ожидание подтверждения',
  'models.state.checking_disk': 'Проверка места',
  'models.state.downloading': 'Загрузка',
  'models.state.cancelling': 'Отмена',
  'models.state.cancelled': 'Отменено',
  'models.state.verifying_size': 'Проверка размера',
  'models.state.verifying_hash': 'Проверка целостности',
  'models.state.validating_artifact': 'Проверка артефакта',
  'models.state.installing': 'Установка',
  'models.state.completed': 'Установлено',
  'models.state.failed': 'Ошибка загрузки',
  'models.state.valid': 'Установлено',
  'models.state.not_installed': 'Не установлено',
  'models.state.bytes_mismatch': 'Неверный размер',
  'models.state.hash_mismatch': 'Неверная целостность',
  'models.state.invalid_path': 'Неверный управляемый путь',
  'models.state.invalid_format': 'Неверный формат',
  'models.state.missing_required_file': 'Неполный движок',
  'models.state.unexpected_file': 'Неожиданный файл движка',
  'models.state.io_error': 'Ошибка проверки',

  // Project
  'project.detail': 'Локальный чат с моделью',

  // Project labels
  'project.label_frontend': 'Frontend',
  'project.label_russian_ux': 'Русский UX',

  // Risk
  'risk.read_only': 'Только чтение',
  'risk.guarded': 'Требует подтверждения',
  'risk.dangerous': 'Опасно',

  // Review Center
  "nav.review_center": "Центр проверки",
  "review.skip_link": "Перейти к Центру проверки",
  "review.workspace_label": "Рабочая область Центра проверки LocalComet",
  "review.eyebrow": "Локальная проверка только для чтения",
  "review.title": "Центр проверки",
  "review.subtitle": "Неизменяемые данные проверки из локального контура управления",
  "review.fixture_badge": "ТЕСТОВЫЕ ДАННЫЕ",
  "review.source.local_control_plane": "ЛОКАЛЬНЫЙ КОНТУР УПРАВЛЕНИЯ",
  "review.state.idle": "Ожидание",
  "review.state.idle_detail": "Запрос коллекции только для чтения ещё не выполнялся.",
  "review.state.loading": "Загрузка артефактов проверки",
  "review.state.loading_detail": "Запрашиваем ограниченную проекцию только для чтения через локальный контур управления.",
  "review.state.empty": "Артефактов проверки нет",
  "review.state.empty_detail": "Рабочая коллекция проверок действительно пуста. Тестовые данные не подставлялись.",
  "review.state.error": "Центр проверки недоступен",
  "review.state.error_detail": "Запрос проверки только для чтения завершился ошибкой.",
  "review.retry": "Повторить",
  "review.refresh": "Обновить",
  "review.unavailable": "Недоступно",
  "review.copy": "Копировать",
  "review.copied": "Скопировано",
  "review.copy_failed": "Не скопировано",
  "review.copy_success": "Значение скопировано.",
  "review.copy_failure": "Не удалось скопировать значение. Скопируйте его вручную.",
  "review.none": "Нет",
  "review.yes": "Да",
  "review.no": "Нет",
  "review.changed": "Изменено",
  "review.unchanged": "Без изменений",
  "review.status.CLEAR": "ЧИСТО",
  "review.status.REVIEW_REQUIRED": "ТРЕБУЕТСЯ ПРОВЕРКА",
  "review.status.BLOCKED": "ЗАБЛОКИРОВАНО",
  "review.queue_eyebrow": "Очередь проверки",
  "review.queue_title": "Артефакты проверки",
  "review.queue_label": "Очередь артефактов проверки",
  "review.queue_mobile_label": "Выберите артефакт проверки",
  "review.queue_help": "Используйте стрелки, Home и End для навигации по ограниченной очереди проверок.",
  "review.queue_truncated": "Ограниченная очередь обрезана. Следующее смещение:",
  "review.detail_truncated.badge": "ОГРАНИЧЕННЫЕ ДЕТАЛИ",
  "review.detail_truncated.title": "Детали проекции ограничены",
  "review.detail_truncated.detail": "Одно или несколько полей проверки были обрезаны принятой проекцией. Показанные значения — это превью, а не полный исходный материал.",
  "review.identity.eyebrow": "Точная привязка",
  "review.identity.title": "Идентичность проверки",
  "review.identity.proposal_id": "ID предложения",
  "review.identity.review_identity": "Идентичность артефакта проверки",
  "review.identity.change_identity": "Идентичность изменения",
  "review.identity.expected_revision": "Ожидаемая ревизия Vault",
  "review.identity.observed_revision": "Наблюдаемая ревизия Vault",
  "review.identity.target_id": "Стабильный ID цели",
  "review.identity.operation": "Операция",
  "review.validation.eyebrow": "Исходная валидация",
  "review.validation.title": "Информация о валидации",
  "review.validation.contract": "Контракт валидации",
  "review.validation.content_hash": "Хэш содержимого предложения",
  "review.validation.validated_revision": "Проверенная ревизия Vault",
  "review.validation.snapshot": "Снимок валидации",
  "review.validation.snapshot_truncated": "Предпросмотр снимка валидации обрезан. Точные идентичности остаются видимыми.",
  "review.validation.source_findings": "Находки исходной валидации",
  "review.validation.outcome.VALID": "ВАЛИДНО",
  "review.validation.outcome.INVALID": "НЕВАЛИДНО",
  "review.validation.outcome.STALE": "УСТАРЕЛО",
  "review.findings.eyebrow": "Анализ конфликтов",
  "review.findings.title": "Находки",
  "review.findings.none": "Конфликтных находок нет.",
  "review.severity.BLOCKING": "БЛОКИРУЮЩАЯ",
  "review.severity.REVIEW": "ТРЕБУЕТ ПРОВЕРКИ",
  "review.metadata.eyebrow": "Структурированное содержимое",
  "review.metadata.title": "Проекция ProposedNoteContent",
  "review.metadata.fields": "полей",
  "review.metadata.projection_note": "Показаны все 18 проверяемых полей ProposedNoteContent из ограниченной проекции. Это не утверждение о будущих сериализованных байтах Vault.",
  "review.metadata.changed": "Поле метаданных изменено",
  "review.metadata.before": "До",
  "review.metadata.after": "После",
  "review.metadata.field.title": "Заголовок",
  "review.metadata.field.body_text": "Текст заметки",
  "review.metadata.field.type": "Тип",
  "review.metadata.field.status": "Статус",
  "review.metadata.field.knowledge_layer": "Слой знаний",
  "review.metadata.field.evidence_class": "Класс доказательств",
  "review.metadata.field.authority": "Полномочия",
  "review.metadata.field.canonical": "Каноническая",
  "review.metadata.field.canonical_scope": "Каноническая область",
  "review.metadata.field.aliases": "Псевдонимы",
  "review.metadata.field.releases": "Релизы",
  "review.metadata.field.source_paths": "Пути источников",
  "review.metadata.field.evidence_refs": "Ссылки на доказательства",
  "review.metadata.field.supersedes": "Заменяет",
  "review.metadata.field.superseded_by": "Заменено",
  "review.metadata.field.updated": "Обновлено",
  "review.metadata.field.last_reviewed": "Последняя проверка",
  "review.metadata.field.verified_at": "Время верификации",
  "review.diff.eyebrow": "Сравнение текста",
  "review.diff.title": "Текстовый diff",
  "review.diff.preview_label": "Предпросмотр diff",
  "review.diff.not_full_diff": "Ограниченный предпросмотр — не полный diff.",
  "review.diff.truncated": "ОБРЕЗАНО",
  "review.diff.no_material": "Обычный материал изменения отсутствует",
  "review.diff.blocked_suppression": "Для BLOCKED-проверки diff, representation delta и change identity подавлены.",
  "review.diff.empty": "(семантический diff текста пуст)",
  "review.diff.hash": "Хэш полного diff",
  "review.diff.bytes": "Байты UTF-8 полного diff",
  "review.diff.full_available": "Полный diff существует в исходном артефакте",
  "review.diff.preview_truncated": "Предпросмотр обрезан",
  "review.representation.eyebrow": "Байтовое и текстовое представление",
  "review.representation.title": "Изменение представления",
  "review.representation.only": "ТОЛЬКО ИЗМЕНЕНИЕ ПРЕДСТАВЛЕНИЯ",
  "review.representation.no_material": "Для этой BLOCKED-проверки representation delta недоступна.",
  "review.representation.identity": "Идентичность представления",
  "review.representation.line_endings": "Профиль окончаний строк",
  "review.representation.terminal_newline": "Конечный перевод строки",
  "review.representation.source_bytes_known": "Байты предлагаемого источника известны",
  "review.representation.bytes_same_text": "Байты источника изменились при одинаковом декодированном тексте",
  "review.representation.raw_semantic_equal": "Сырой текст изменился при семантическом равенстве",
  "review.representation.semantic_changed": "Семантическое содержимое текста изменилось",
  "review.representation.absent": "ОТСУТСТВУЕТ",
  "review.preview.eyebrow": "Ограниченный вывод",
  "review.preview.title": "Предпросмотр для человека",
  "review.preview.truncated": "ОБРЕЗАНО",
  "review.decision.eyebrow": "Локальное намерение решения",
  "review.decision.title": "Подтверждение решения",
  "review.decision.fixture_only": "ТОЛЬКО ТЕСТОВЫЕ ДАННЫЕ",
  "review.decision.real_read_only": "РЕАЛЬНЫЕ ДАННЫЕ — ТОЛЬКО ЧТЕНИЕ",
  "review.decision.unavailable": "Интеграция артефакта решения на этом этапе недоступна. Для реальных артефактов действия APPROVE, REJECT и REQUEST CHANGES отключены.",
  "review.decision.boundary": "Эти элементы записывают только тестовое намерение в памяти. Они не создают авторитетную идентичность решения и не выполняют действий с Vault, публикацией, слиянием, исполнением, сохранением или Tauri.",
  "review.decision.actions": "Тестовые действия решения",
  "review.decision.approve": "ОДОБРИТЬ",
  "review.decision.reject": "ОТКЛОНИТЬ",
  "review.decision.request_changes": "ЗАПРОСИТЬ ИЗМЕНЕНИЯ",
  "review.decision.dialog_title": "Подтвердите тестовое намерение решения",
  "review.decision.dialog_description": "Проверьте точную привязку предложения перед записью локального тестового намерения.",
  "review.decision.intent": "Намерение решения",
  "review.decision.comment": "Комментарий",
  "review.decision.required": "Обязательно для ЗАПРОСИТЬ ИЗМЕНЕНИЯ",
  "review.decision.comment_placeholder": "Добавьте ограниченный локальный комментарий",
  "review.decision.cancel": "Отмена",
  "review.decision.confirm": "Подтвердить тестовое намерение",
  "review.decision.blocked_approval": "ОДОБРИТЬ недоступно для заблокированной проверки.",
  "review.decision.comment_required": "Для ЗАПРОСИТЬ ИЗМЕНЕНИЯ нужен непустой комментарий.",
  "review.decision.hard_stop_title": "ЖЁСТКАЯ ОСТАНОВКА",
  "review.decision.hard_stop_detail": "Подтверждение заканчивается тестовым UI-результатом. Авторитетный артефакт решения не создаётся.",
  "review.decision.real_hard_stop_detail": "Может быть создан подлинный артефакт решения e9c, но никаких полномочных действий не выполняется. Vault остаётся неизменным; публикация, сохранение, merge, исполнение и автоматическое одобрение недоступны.",
  "review.decision.fixture_result": "Тестовый результат:",
  "review.decision.fixture_hard_stop": "Намерение записано только в памяти. ЖЁСТКАЯ ОСТАНОВКА — без полномочий, сохранения и вызова Tauri.",
  "review.phase_boundary.title": "Граница полномочий Phase 1",
  "review.phase_boundary.detail": "Реальный IPC ограничен list/get только для чтения. Решения e9c, запись в Vault, публикация, слияние, выполнение и сохранение остаются вне этого этапа.",

  "review.queue_visible_count": "Количество видимых артефактов и общий размер очереди",
  "review.queue_filtered_empty": "Нет артефактов проверки, соответствующих активным фильтрам.",
  "review.stale.badge": "УСТАРЕЛО",
  "review.stale.unknown": "СВЕЖЕСТЬ НЕИЗВЕСТНА",
  "review.stale.title": "Эта проверка устарела",
  "review.stale.detail": "Текущая ревизия Vault больше не совпадает с неизменяемым артефактом проверки. Перед решением создайте новую проверку.",
  "review.stale.unknown_title": "Свежесть неизвестна",
  "review.stale.unknown_detail": "Текущая ревизия Vault недоступна. Решения отключены, пока свежесть нельзя доказать.",
  "review.command_bar.label": "Панель команд операций со знаниями",
  "review.command_bar.search": "Поиск",
  "review.command_bar.search_placeholder": "Идентичность, цель, операция или статус",
  "review.command_bar.status_filter": "Статус",
  "review.command_bar.operation_filter": "Операция",
  "review.command_bar.sort": "Сортировка",
  "review.command_bar.sort_status": "Статус, затем идентичность",
  "review.command_bar.sort_identity": "Идентичность",
  "review.command_bar.visible": "видимо",
  "review.command_bar.clear": "Сбросить фильтры",
  "review.command_bar.revalidate": "Обновить и перепроверить",
  "review.decision.real_e9c": "РЕАЛЬНОЕ РЕШЕНИЕ e9c",
  "review.decision.real_boundary": "Эти элементы создают настоящий неизменяемый HumanReviewDecision e9c с точной привязкой к проверке и текущей ревизии Vault. Результат — только сессионное доказательство без полномочий на запись, публикацию, сохранение или выполнение.",
  "review.decision.stale": "Проверка устарела. Обновите состояние и создайте новый артефакт проверки.",
  "review.decision.freshness_unknown": "Свежесть нельзя доказать. Элементы решения остаются отключёнными.",
  "review.decision.stale_or_unknown": "Решение недоступно, пока не доказана точная текущая ревизия Vault.",
  "review.decision.real_result": "Создан артефакт решения:",
  "review.decision.decision_identity": "Идентичность решения",
  "review.decision.vault_modified": "Vault изменён",
  "review.decision.dialog_description_fixture": "Проверьте точную привязку предложения перед записью локального тестового намерения.",
  "review.decision.dialog_description_real": "Подтвердите точную привязку предложения, проверки, изменения и ревизии Vault перед созданием сессионного доказательства e9c.",
  "review.decision.actor_identifier": "Идентификатор проверяющего",
  "review.decision.actor_display_name": "Отображаемое имя проверяющего",
  "review.decision.actor_evidence_only": "Метаданные проверяющего — только описательное доказательство. На этом этапе LocalComet не аутентифицирует личность человека.",
  "review.decision.actor_required": "Требуются идентификатор и отображаемое имя проверяющего.",
  "review.decision.submitting": "Создаём решение…",
  "review.decision.policy_blocked": "Решение отклонено точной политикой проверки или защитой от устаревшей ревизии.",
  "review.decision.failed": "Не удалось создать артефакт решения.",
  "review.decision.real_hard_stop": "Настоящий неизменяемый артефакт решения e9c возвращён в UI. ЖЁСТКАЯ ОСТАНОВКА — Vault не изменён; публикация, сохранение, слияние, выполнение и автоматическое одобрение не выполнялись.",
  "review.activity.eyebrow": "Сессионные доказательства",
  "review.activity.title": "Лента активности",
  "review.activity.empty": "Сессионной активности пока нет.",
  "review.activity.boundary": "Только ограниченная активность в памяти текущей сессии. После завершения приложения она исчезнет.",
  "review.activity.inbox_refresh": "Очередь обновлена, свежесть Vault перепроверена.",
  "review.activity.connected": "Канал проверок локального контура управления подключён.",
  "review.activity.artifact_opened": "Артефакт проверки открыт.",
  "review.activity.stale_review": "Обнаружена устаревшая проверка.",
  "review.activity.decision_created": "Создан артефакт решения человека.",
  "review.activity.error": "Записана ограниченная ошибка проверки.",
  "review.activity.snapshot_refresh_failed": "Решение создано, но не удалось обновить последующий диагностический снимок.",
  "review.diagnostics.eyebrow": "Ограниченная диагностика",
  "review.diagnostics.title": "Диагностика командного центра",
  "review.diagnostics.command_center": "Командный центр",
  "review.diagnostics.frontend_contract": "Контракт проекции frontend",
  "review.diagnostics.tauri": "Мост Tauri",
  "review.diagnostics.sidecar": "Sidecar",
  "review.diagnostics.python_runtime": "Среда Python sidecar",
  "review.diagnostics.inbox": "Размер очереди",
  "review.diagnostics.stale": "Устаревших",
  "review.diagnostics.blocked": "Заблокированных",
  "review.diagnostics.decisions": "Решений за сессию",
  "review.diagnostics.last_error": "Последний ограниченный код ошибки",
  "review.diagnostics.boundary": "Здесь нет переменных среды, абсолютных путей, промптов, секретов или несвязанных данных Vault.",
  "review.connection.IDLE": "ОЖИДАНИЕ",
  "review.connection.CONNECTING": "ПОДКЛЮЧЕНИЕ",
  "review.connection.CONNECTED": "ПОДКЛЮЧЕНО",
  "review.connection.UNAVAILABLE": "НЕДОСТУПНО",
  "review.connection.ERROR": "ОШИБКА",
};
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/knowledge/knowledgePreview.ts (97 строк, 2711 байт)

````typescript
export type KnowledgeIntent =
  | 'AUTO'
  | 'CURRENT_STATE'
  | 'ARCHITECTURE'
  | 'SECURITY'
  | 'HISTORY'
  | 'FOUNDER_INTENT'
  | 'ROADMAP'
  | 'RESEARCH'
  | 'OPERATIONAL'
  | 'INCIDENT';

export type KnowledgeAction =
  | 'INCLUDE_AND_SEND'
  | 'REJECT_AND_SEND_WITHOUT_KNOWLEDGE'
  | 'CANCEL';

export type KnowledgeUiState =
  | 'OFF'
  | 'RETRIEVING'
  | 'PREVIEW_READY'
  | 'DECIDING'
  | 'DISPATCHING'
  | 'INJECTED'
  | 'REJECTED'
  | 'CANCELLED'
  | 'FAILED'
  | 'STALE';

export interface KnowledgePreviewSection {
  readonly heading: string;
  readonly line_start: number;
  readonly line_end: number;
  readonly content: string;
}

export interface KnowledgePreviewSource {
  readonly note_id: string;
  readonly title: string;
  readonly relative_path: string;
  readonly knowledge_layer: string;
  readonly evidence_class: string;
  readonly authority: string;
  readonly status: string;
  readonly canonical: boolean;
  readonly selected_sections: readonly KnowledgePreviewSection[];
}

export interface KnowledgePreview {
  readonly state: 'PREVIEW_READY';
  readonly turn_id: string;
  readonly request_id: string;
  readonly injection_id: string;
  readonly bundle_id: string;
  readonly preview_hash: string;
  readonly vault_revision: string;
  readonly resolved_intent: KnowledgeIntent;
  readonly source_count: number;
  readonly total_chars: number;
  readonly truncated: boolean;
  readonly sources: readonly KnowledgePreviewSource[];
  readonly model_dispatched: false;
  readonly tools_executed: 0;
}

export interface KnowledgePreviewFailure {
  readonly state: 'FAILED';
  readonly turn_id: string;
  readonly request_id?: string;
  readonly injection_id: null;
  readonly error: { readonly code: string; readonly safe_message: string };
  readonly model_dispatched: false;
  readonly tools_executed: 0;
}

export interface KnowledgeDecisionResponse {
  readonly state: 'DECIDING' | 'DISPATCHING' | 'INJECTED' | 'REJECTED' | 'STALE';
  readonly turn_id: string;
  readonly injection_id: string;
  readonly action?: KnowledgeAction;
  readonly preview_hash?: string;
  readonly decision_source?: 'USER_APPROVAL';
  readonly model_turn_id?: string | null;
  readonly model_dispatched: boolean;
  readonly knowledge_included?: boolean;
  readonly duplicate?: boolean;
  readonly error?: { readonly code: string; readonly safe_message: string };
}

export const DEFAULT_KNOWLEDGE_INTENT: KnowledgeIntent = 'AUTO';
export const DEFAULT_KNOWLEDGE_CONTEXT_CHARS = 12_000;
export const DEFAULT_KNOWLEDGE_RESULTS = 8;

export function abbreviateKnowledgeHash(value: string): string {
  const hex = value.startsWith('sha256:') ? value.slice(7) : value;
  return `${hex.slice(0, 8)}…`;
}
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/risk.ts (19 строк, 646 байт)

````typescript
export type RiskLevel = 'read_only' | 'guarded' | 'dangerous';

export const RISK_LEVELS: readonly RiskLevel[] = ['read_only', 'guarded', 'dangerous'];

export const RISK_TONE: Record<RiskLevel, 'ready' | 'info' | 'waiting' | 'danger' | 'disabled' | 'unknown'> = {
  'read_only': 'ready',
  'guarded': 'waiting',
  'dangerous': 'danger'
};

export const RISK_LABEL_KEY: Record<RiskLevel, string> = {
  'read_only': 'risk.read_only',
  'guarded': 'risk.guarded',
  'dangerous': 'risk.dangerous'
};

export function isRiskLevel(value: unknown): value is RiskLevel {
  return value === 'read_only' || value === 'guarded' || value === 'dangerous';
}
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/stores/artifactAcquisition.ts (184 строк, 6632 байт)

````typescript
import { derived, get, writable } from 'svelte/store';
import {
  cancelArtifactDownload,
  getArtifactDownloadState,
  listApprovedDownloadableArtifacts,
  normalizeGatewayError,
  removeManagedModel,
  startApprovedArtifactDownload
} from '$lib/bridge/modelGateway';
import {
  connectSelectedManagedModel,
  managedRuntimeStore,
  refreshManagedRuntimeStatus,
  setManagedSelectedModel
} from '$lib/stores/modelGateway';
import type {
  ApprovedDownloadableArtifact,
  ArtifactDownloadState,
  SanitizedGatewayError
} from '$lib/types/modelGateway';

const DOWNLOAD_POLL_MS = 500;

export interface ArtifactAcquisitionPanelState {
  readonly artifacts: readonly ApprovedDownloadableArtifact[];
  readonly downloads: Readonly<Record<string, ArtifactDownloadState>>;
  readonly setup: {
    readonly lifecycle: 'idle' | 'running' | 'completed' | 'cancelled' | 'failed';
    readonly artifact_id: string | null;
  };
  readonly lastError: SanitizedGatewayError | null;
}

const initialState: ArtifactAcquisitionPanelState = {
  artifacts: [],
  downloads: {},
  setup: { lifecycle: 'idle', artifact_id: null },
  lastError: null
};

let lifecycleGeneration = 0;
let initialization: Promise<void> | null = null;

export const artifactAcquisitionStore = writable<ArtifactAcquisitionPanelState>(initialState);
export const acquisitionBusy = derived(artifactAcquisitionStore, (state) =>
  Object.values(state.downloads).some((download) => !isTerminal(download)) || state.setup.lifecycle === 'running'
);

export async function initializeArtifactAcquisition(): Promise<void> {
  if (initialization) return initialization;
  const generation = lifecycleGeneration;
  const pending = (async () => {
    try {
      const artifacts = await listApprovedDownloadableArtifacts();
      if (generation !== lifecycleGeneration) return;
      artifactAcquisitionStore.update((state) => ({ ...state, artifacts, lastError: null }));
    } catch (error) {
      if (generation !== lifecycleGeneration) return;
      artifactAcquisitionStore.update((state) => ({ ...state, lastError: normalizeGatewayError(error) }));
    }
  })();
  initialization = pending;
  try {
    await pending;
  } finally {
    if (initialization === pending) initialization = null;
  }
}

export async function downloadApprovedArtifact(artifactId: string): Promise<ArtifactDownloadState | null> {
  const artifact = get(artifactAcquisitionStore).artifacts.find((candidate) => candidate.artifact_id === artifactId);
  if (!artifact) return null;
  try {
    const started = await startApprovedArtifactDownload(artifact.artifact_id);
    recordDownload(started);
    return await followDownload(started);
  } catch (error) {
    artifactAcquisitionStore.update((state) => ({ ...state, lastError: normalizeGatewayError(error) }));
    return null;
  }
}

export async function cancelApprovedArtifactDownload(artifactId: string): Promise<void> {
  const current = get(artifactAcquisitionStore).downloads[artifactId];
  if (!current || isTerminal(current)) return;
  try {
    recordDownload(await cancelArtifactDownload(current.job_id));
  } catch (error) {
    artifactAcquisitionStore.update((state) => ({ ...state, lastError: normalizeGatewayError(error) }));
  }
}

export async function setUpLocalAi(): Promise<boolean> {
  const artifacts = get(artifactAcquisitionStore).artifacts;
  const runtime = artifacts.find((artifact) => artifact.kind === 'runtime');
  const model = artifacts.find((artifact) => artifact.kind === 'model');
  if (!runtime || !model) return false;
  artifactAcquisitionStore.update((state) => ({
    ...state,
    setup: { lifecycle: 'running', artifact_id: null },
    lastError: null
  }));
  for (const artifact of [runtime, model]) {
    artifactAcquisitionStore.update((state) => ({
      ...state,
      setup: { lifecycle: 'running', artifact_id: artifact.artifact_id }
    }));
    if (isInstalled(artifact.artifact_id)) continue;
    const terminal = await downloadApprovedArtifact(artifact.artifact_id);
    if (terminal?.lifecycle !== 'completed') {
      artifactAcquisitionStore.update((state) => ({
        ...state,
        setup: {
          lifecycle: terminal?.lifecycle === 'cancelled' ? 'cancelled' : 'failed',
          artifact_id: artifact.artifact_id
        }
      }));
      return false;
    }
    await refreshManagedRuntimeStatus();
  }
  await setManagedSelectedModel(model.artifact_id);
  const connected = await connectSelectedManagedModel();
  artifactAcquisitionStore.update((state) => ({
    ...state,
    setup: { lifecycle: connected ? 'completed' : 'failed', artifact_id: model.artifact_id },
    lastError: connected ? null : get(managedRuntimeStore).lastError
  }));
  return connected;
}

export async function removeApprovedManagedModel(modelId: string): Promise<boolean> {
  try {
    await removeManagedModel(modelId);
    await refreshManagedRuntimeStatus();
    artifactAcquisitionStore.update((state) => ({ ...state, lastError: null }));
    return true;
  } catch (error) {
    artifactAcquisitionStore.update((state) => ({ ...state, lastError: normalizeGatewayError(error) }));
    return false;
  }
}

export function resetArtifactAcquisitionStore(): void {
  lifecycleGeneration += 1;
  initialization = null;
  artifactAcquisitionStore.set(initialState);
}

async function followDownload(started: ArtifactDownloadState): Promise<ArtifactDownloadState> {
  const generation = lifecycleGeneration;
  let current = started;
  while (!isTerminal(current) && generation === lifecycleGeneration) {
    await delay(DOWNLOAD_POLL_MS);
    current = await getArtifactDownloadState(current.job_id);
    recordDownload(current);
  }
  if (generation === lifecycleGeneration) await refreshManagedRuntimeStatus();
  return current;
}

function recordDownload(download: ArtifactDownloadState): void {
  artifactAcquisitionStore.update((state) => ({
    ...state,
    downloads: { ...state.downloads, [download.artifact_id]: download },
    lastError: download.lifecycle === 'failed'
      ? { code: download.error_code ?? 'download_failed', message: 'Approved artifact download failed' }
      : state.lastError
  }));
}

function isInstalled(artifactId: string): boolean {
  return get(managedRuntimeStore).installedArtifacts.some((artifact) =>
    artifact.artifact_id === artifactId && artifact.installation_status === 'valid'
  );
}

function isTerminal(download: ArtifactDownloadState): boolean {
  return ['cancelled', 'completed', 'failed'].includes(download.lifecycle);
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}
````

### ПУТЬ: desktop/localcomet-desktop/src/lib/stores/controlPlane.ts (282 строк, 9777 байт)

````typescript
import { get, writable } from 'svelte/store';
import {
  bootstrapControlPlane,
  cancelTurn,
  createSession,
  createThread,
  getTurnStatus,
  normalizeBridgeError,
  startMockTurn,
  subscribeControlPlaneEvents
} from '$lib/bridge/controlPlane';
import type {
  BootstrapResponse,
  BridgeState,
  CancelReason,
  ControlPlaneEvent,
  ControlPlaneItem,
  MockTurnBehavior,
  SanitizedBridgeError,
  SessionSummary,
  ThreadSummary,
  TurnSummary
} from '$lib/types/controlPlane';

export const MAX_RECENT_EVENTS = 100;
export const MAX_ITEMS = 128;
export const MAX_ITEM_TEXT = 65_536;

interface ControlPlaneState {
  readonly bridgeState: BridgeState;
  readonly bootstrap: BootstrapResponse | null;
  readonly currentSession: SessionSummary | null;
  readonly currentThread: ThreadSummary | null;
  readonly currentTurn: TurnSummary | null;
  readonly items: readonly ControlPlaneItem[];
  readonly recentEvents: readonly ControlPlaneEvent[];
  readonly lastError: SanitizedBridgeError | null;
  readonly initialized: boolean;
  readonly eventCount: number;
}

const initialState: ControlPlaneState = {
  bridgeState: 'DISCONNECTED',
  bootstrap: null,
  currentSession: null,
  currentThread: null,
  currentTurn: null,
  items: [],
  recentEvents: [],
  lastError: null,
  initialized: false,
  eventCount: 0
};

const lastSequenceByReplyTo = new Map<string, number>();
let unsubscribeEvents: (() => void) | null = null;
let bootstrapStarted = false;

export const controlPlaneStore = writable<ControlPlaneState>(initialState);

export async function initializeControlPlaneBridge(): Promise<void> {
  if (bootstrapStarted) return;
  bootstrapStarted = true;
  controlPlaneStore.update((state) => ({ ...state, bridgeState: 'CONNECTING', initialized: true }));
  try {
    unsubscribeEvents = await subscribeControlPlaneEvents(applyControlPlaneEvent);
    const bootstrap = await bootstrapControlPlane();
    controlPlaneStore.update((state) => ({ ...state, bridgeState: 'READY', bootstrap, lastError: null }));
  } catch (error) {
    const normalized = normalizeBridgeError(error);
    controlPlaneStore.update((state) => ({
      ...state,
      bridgeState: normalized.code === 'sidecar_unavailable' ? 'UNAVAILABLE' : 'ERROR',
      lastError: normalized
    }));
  }
}

export function shutdownControlPlaneBridge(): void {
  unsubscribeEvents?.();
  unsubscribeEvents = null;
}

export async function submitControlPlaneDemo(prompt: string, behavior: MockTurnBehavior = 'complete'): Promise<boolean> {
  const state = get(controlPlaneStore);
  if (state.bridgeState !== 'READY') return false;
  try {
    let session = state.currentSession;
    if (!session) {
      session = await createSession('LocalComet demo');
      controlPlaneStore.update((current) => ({ ...current, currentSession: session }));
    }
    let thread = get(controlPlaneStore).currentThread;
    if (!thread) {
      thread = await createThread(session.session_id, 'Control Plane demo');
      controlPlaneStore.update((current) => ({ ...current, currentThread: thread }));
    }
    const turn = await startMockTurn(thread.thread_id, prompt, behavior);
    controlPlaneStore.update((current) => ({ ...current, currentTurn: turn, lastError: null }));
    if (turn.state === 'RUNNING') {
      const refreshed = await getTurnStatus(turn.turn_id);
      controlPlaneStore.update((current) => ({ ...current, currentTurn: refreshed }));
    }
    return true;
  } catch (error) {
    controlPlaneStore.update((current) => ({ ...current, bridgeState: 'ERROR', lastError: normalizeBridgeError(error) }));
    return false;
  }
}

export async function createPendingKnowledgeTurn(prompt: string): Promise<TurnSummary | null> {
  const state = get(controlPlaneStore);
  if (state.bridgeState !== 'READY') return null;
  try {
    let session = state.currentSession;
    if (!session) {
      session = await createSession('LocalComet chat');
      controlPlaneStore.update((current) => ({ ...current, currentSession: session }));
    }
    let thread = get(controlPlaneStore).currentThread;
    if (!thread) {
      thread = await createThread(session.session_id, 'Project Knowledge');
      controlPlaneStore.update((current) => ({ ...current, currentThread: thread }));
    }
    const turn = await startMockTurn(thread.thread_id, prompt, 'pending_model');
    controlPlaneStore.update((current) => ({ ...current, currentTurn: turn, lastError: null }));
    return turn;
  } catch (error) {
    controlPlaneStore.update((current) => ({ ...current, lastError: normalizeBridgeError(error) }));
    return null;
  }
}

export async function startCancellationDemo(): Promise<void> {
  await submitControlPlaneDemo('Cancellation demo request', 'wait_for_cancel');
}

export async function cancelCurrentDemoTurn(reason: CancelReason = 'user_requested'): Promise<void> {
  const turn = get(controlPlaneStore).currentTurn;
  if (!turn || turn.state !== 'RUNNING') return;
  try {
    const cancelled = await cancelTurn(turn.turn_id, reason);
    controlPlaneStore.update((state) => ({ ...state, currentTurn: cancelled, lastError: null }));
  } catch (error) {
    controlPlaneStore.update((state) => ({ ...state, lastError: normalizeBridgeError(error) }));
  }
}

export function resetControlPlaneStore(): void {
  lastSequenceByReplyTo.clear();
  bootstrapStarted = false;
  unsubscribeEvents = null;
  controlPlaneStore.set(initialState);
}

export function applyControlPlaneEvent(event: ControlPlaneEvent): void {
  if (!validEventSequence(event)) return;
  controlPlaneStore.update((state) => {
    if (isTerminalLocked(state, event)) {
      return { ...state, lastError: { code: 'invalid_sequence', message: 'Event after terminal turn rejected' } };
    }
    const recentEvents = [...state.recentEvents, event].slice(-MAX_RECENT_EVENTS);
    let next: ControlPlaneState = {
      ...state,
      recentEvents,
      eventCount: state.eventCount + 1,
      lastError: null
    };
    if (event.method === 'session.created' && event.session_id) {
      next = {
        ...next,
        currentSession: {
          session_id: event.session_id,
          state: 'OPEN',
          title: String(event.metadata.title ?? ''),
          thread_count: 0
        }
      };
    }
    if (event.method === 'thread.created' && event.thread_id && event.session_id) {
      next = {
        ...next,
        currentThread: {
          thread_id: event.thread_id,
          session_id: event.session_id,
          state: 'ACTIVE',
          title: String(event.metadata.title ?? ''),
          turn_count: 0,
          active_turn_id: null
        }
      };
    }
    if (event.method === 'turn.started' && event.turn_id) {
      next = {
        ...next,
        currentTurn: {
          turn_id: event.turn_id,
          thread_id: event.thread_id ?? undefined,
          state: 'RUNNING',
          model_called: false,
          tools_executed: 0
        },
        items: []
      };
    }
    if (event.method === 'turn.completed' && next.currentTurn) {
      next = { ...next, currentTurn: { ...next.currentTurn, state: 'COMPLETED', model_called: false, tools_executed: 0 } };
    }
    if (event.method === 'turn.cancelled' && next.currentTurn) {
      next = { ...next, currentTurn: { ...next.currentTurn, state: 'CANCELLED', model_called: false, tools_executed: 0 } };
    }
    if (event.method === 'item.started' && event.item_id && event.kind) {
      next = {
        ...next,
        items: [...next.items, { item_id: event.item_id, kind: event.kind, state: 'STARTED' as const, text: '' }].slice(-MAX_ITEMS)
      };
    }
    if (event.method === 'item.delta' && event.item_id && event.text) {
      next = {
        ...next,
        items: next.items.map((item) =>
          item.item_id === event.item_id
            ? { ...item, state: 'STREAMING', text: `${item.text}${event.text ?? ''}`.slice(0, MAX_ITEM_TEXT) }
            : item
        )
      };
    }
    if (event.method === 'item.completed' && event.item_id) {
      next = {
        ...next,
        items: next.items.map((item) =>
          item.item_id === event.item_id
            ? { ...item, state: 'COMPLETED', text: event.text ? `${item.text}${event.text}`.slice(0, MAX_ITEM_TEXT) : item.text }
            : item
        )
      };
    }
    return next;
  });
}

function validEventSequence(event: ControlPlaneEvent): boolean {
  const last = lastSequenceByReplyTo.get(event.reply_to);
  if (last !== undefined && event.sequence <= last) {
    controlPlaneStore.update((state) => ({ ...state, lastError: { code: 'invalid_sequence', message: 'Duplicate or decreasing event sequence rejected' } }));
    return false;
  }
  if (!isKnownEvent(event.method)) {
    controlPlaneStore.update((state) => ({ ...state, lastError: { code: 'unsupported_method', message: 'Unknown event rejected' } }));
    return false;
  }
  lastSequenceByReplyTo.set(event.reply_to, event.sequence);
  return true;
}

function isTerminalLocked(state: ControlPlaneState, event: ControlPlaneEvent): boolean {
  const turn = state.currentTurn;
  if (!turn || !event.turn_id || turn.turn_id !== event.turn_id) return false;
  return ['COMPLETED', 'CANCELLED', 'FAILED'].includes(turn.state) && !['turn.completed', 'turn.cancelled', 'turn.failed'].includes(event.method);
}

function isKnownEvent(method: string): boolean {
  return [
    'sidecar.status',
    'session.created',
    'session.closed',
    'thread.created',
    'turn.started',
    'turn.completed',
    'turn.cancelled',
    'turn.failed',
    'item.started',
    'item.delta',
    'item.completed',
    'model.turn.started',
    'model.output.delta',
    'model.turn.completed',
    'model.turn.cancelled',
    'model.turn.timed_out',
    'model.turn.failed'
  ].includes(method);
}
````

