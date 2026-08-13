<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import DownloadProgress from '$lib/components/model/DownloadProgress.svelte';
  import {
    confirmBinding,
    connectSelectedManagedModel,
    discoverModels,
    inferenceBusy,
    managedConnectionBusy,
    managedModelReady,
    managedRuntimeStore,
    modelGatewayStore,
    probeGateway,
    refreshManagedRuntimeStatus,
    setGatewayHarness,
    setGatewayPortText,
    setManagedHarness,
    setManagedSelectedModel,
    setSelectedModel
  } from '$lib/stores/modelGateway';
  import { closeModelSetup, modelSetupDrawerOpen, modelSetupMode, setActiveWorkspace, openSettings } from '$lib/stores/shellStore';

  import {
    acquisitionBusy,
    artifactAcquisitionStore,
    cancelApprovedArtifactDownload,
    downloadAndSetupManagedModel,
    initializeArtifactAcquisition
  } from '$lib/stores/artifactAcquisition';
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
  $: canBindManaged = !$inferenceBusy && !$managedConnectionBusy && managedModelLaunchable && ['Stopped', 'Failed', 'Ready'].includes(managedState) && Boolean($managedRuntimeStore.selectedModelId);
  $: managedTone = managedState === 'Ready' ? 'ready' : managedState === 'Failed' ? 'danger' : managedState === 'Starting' || managedState === 'Validating' || managedState === 'Stopping' ? 'info' : 'disabled';
  $: managedSetupRunning = $artifactAcquisitionStore.setup.lifecycle === 'running' || $acquisitionBusy;
  $: approvedSetupModels = $artifactAcquisitionStore.artifacts.filter((artifact) => artifact.kind === 'model' && artifact.trust_kind === 'approved_catalog');
  $: setupTargetModel = approvedSetupModels.find((artifact) => artifact.artifact_id === $managedRuntimeStore.selectedModelId) ?? approvedSetupModels[0] ?? null;
  $: canSetupManaged = !$inferenceBusy && !$managedConnectionBusy && !managedSetupRunning && !$managedModelReady && Boolean(setupTargetModel);
  $: activeDownload = Object.values($artifactAcquisitionStore.downloads).find(d => !['cancelled', 'completed', 'failed'].includes(d.lifecycle)) ?? null;

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

  async function onConfirmManagedBinding() {
    const connected = await connectSelectedManagedModel();
    if (connected) {
      closeModelSetup();
    }
  }

  async function onGoToHfCatalog() {
    setActiveWorkspace('hf_browser');
    closeModelSetup();
  }

  function onOpenModelSettings() {
    closeModelSetup();
    openSettings('models');
  }

  onMount(() => {
    portInput = $modelGatewayStore.portText;
    void initializeArtifactAcquisition();
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

    {#if $modelSetupMode === 'external'}
      <div class="drawer-content" role="tabpanel" aria-label={$t('setup.external_tab')}>
        <button class="text-button back-button" onclick={() => modelSetupMode.set('managed')}>
          <Icon name="chevron_left" size={16} />
          <span>Назад</span>
        </button>
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
      <div class="drawer-content managed-view" role="tabpanel" aria-label={$t('setup.managed_tab')}>
        <section class="setup-section" aria-labelledby="managed-title">

          {#if managedState === 'NotInstalled'}
            <div class="hero-empty-state">
              <div class="hero-icon">
                <Icon name="spark" size={48} />
              </div>
              <p class="empty-title">Встроенный искусственный интеллект</p>
              <p class="empty-desc">LocalComet может работать полностью автономно. Скачайте встроенный движок, чтобы общаться с нейросетями без интернета.</p>
              
              {#if managedSetupRunning}
                <DownloadProgress
                  title={$t('models.setup_progress')}
                  detail={activeDownload ? `${(activeDownload.received_bytes / 1024 / 1024).toFixed(1)} / ${(activeDownload.expected_bytes / 1024 / 1024).toFixed(1)} MiB` : 'Пожалуйста, подождите...'}
                  percent={activeDownload?.percent ?? null}
                  onCancel={activeDownload ? () => void cancelApprovedArtifactDownload(activeDownload.artifact_id) : null}
                />
              {:else}
                <div class="setup-actions">
                  <button
                    type="button"
                    class="primary-button hero-button"
                    aria-label="Из каталога HF"
                    disabled={!canSetupManaged}
                    onclick={onGoToHfCatalog}
                  >
                    <Icon name="search" size={24} />
                    <div class="hero-btn-text">
                      <span class="btn-title">Из каталога HF</span>
                      <span class="btn-sub">Найти модель</span>
                    </div>
                  </button>
                  <button
                    type="button"
                    class="secondary-button hero-button"
                    aria-label="Загрузить локальную модель gguf"
                    onclick={onOpenModelSettings}
                  >
                    <Icon name="folder" size={24} />
                    <div class="hero-btn-text">
                      <span class="btn-title">Свой .gguf</span>
                      <span class="btn-sub">Локальный файл</span>
                    </div>
                  </button>
                  <button
                    type="button"
                    class="secondary-button hero-button"
                    aria-label="Внешний сервер"
                    onclick={() => modelSetupMode.set('external')}
                  >
                    <Icon name="plug" size={24} />
                    <div class="hero-btn-text">
                      <span class="btn-title">Внешний сервер</span>
                      <span class="btn-sub">Подключить API</span>
                    </div>
                  </button>
                </div>
              {/if}
            </div>
          {:else}
            {#if $managedRuntimeStore.catalog.length > 1}
              <label class="form-field">
                <span>Выбор модели</span>
                <select disabled={$inferenceBusy} value={$managedRuntimeStore.selectedModelId} onchange={(e) => void setManagedSelectedModel((e.currentTarget as HTMLSelectElement).value)}>
                  <option value="">{$t('setup.select_local_model')}</option>
                  {#each $managedRuntimeStore.catalog as model}
                    <option value={model.model_id}>{model.display_name}</option>
                  {/each}
                </select>
              </label>
            {/if}

            <div class="hero-empty-state connected-state">
              <div class="hero-icon ready-icon">
                <Icon name="check" size={48} />
              </div>
              <p class="empty-title">ИИ готов к работе</p>
              <p class="empty-desc">Встроенный движок установлен и готов к запуску.</p>

              {#if managedSetupRunning}
                <DownloadProgress
                  title={$t('models.setup_progress')}
                  detail={activeDownload ? `${(activeDownload.received_bytes / 1024 / 1024).toFixed(1)} / ${(activeDownload.expected_bytes / 1024 / 1024).toFixed(1)} MiB` : 'Пожалуйста, подождите...'}
                  percent={activeDownload?.percent ?? null}
                  onCancel={activeDownload ? () => void cancelApprovedArtifactDownload(activeDownload.artifact_id) : null}
                />
              {:else}
                <div class="setup-actions">
                  <button
                    type="button"
                    class="primary-button hero-button run-model-btn"
                    aria-label="Запустить ИИ"
                    disabled={!canBindManaged}
                    onclick={onConfirmManagedBinding}
                  >
                    <Icon name="play" size={24} />
                    <div class="hero-btn-text">
                      <span class="btn-title">{$t($managedConnectionBusy ? 'chat.model_connecting' : 'setup.connect')}</span>
                      <span class="btn-sub">Запустить выбранную</span>
                    </div>
                  </button>
                  <button
                    type="button"
                    class="secondary-button hero-button"
                    aria-label="Из каталога HF"
                    onclick={onGoToHfCatalog}
                  >
                    <Icon name="search" size={24} />
                    <div class="hero-btn-text">
                      <span class="btn-title">Из каталога HF</span>
                      <span class="btn-sub">Найти модель</span>
                    </div>
                  </button>
                  <button
                    type="button"
                    class="secondary-button hero-button"
                    aria-label="Загрузить локальную модель gguf"
                    onclick={onOpenModelSettings}
                  >
                    <Icon name="folder" size={24} />
                    <div class="hero-btn-text">
                      <span class="btn-title">Свой .gguf</span>
                      <span class="btn-sub">Локальный файл</span>
                    </div>
                  </button>
                  <button
                    type="button"
                    class="secondary-button hero-button"
                    aria-label="Внешний сервер"
                    onclick={() => modelSetupMode.set('external')}
                  >
                    <Icon name="plug" size={24} />
                    <div class="hero-btn-text">
                      <span class="btn-title">Внешний сервер</span>
                      <span class="btn-sub">Подключить API</span>
                    </div>
                  </button>
                </div>
              {/if}
            </div>

            {#if $managedConnectionBusy}
              <p class="connection-progress hero-progress" role="status">{$t('chat.model_loading_detail')}</p>
            {/if}
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
    backdrop-filter: blur(12px);
    animation: fadeIn 0.4s ease;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  .drawer-panel {
    position: relative;
    width: min(540px, 100vw);
    height: 100%;
    max-height: 100vh;
    background: rgba(18, 20, 24, 0.85);
    backdrop-filter: blur(32px);
    border-left: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: -20px 0 60px rgba(0, 0, 0, 0.6);
    animation: slideIn 0.5s cubic-bezier(0.16, 1, 0.3, 1);
  }

  @keyframes slideIn {
    from { transform: translateX(100%); }
    to { transform: translateX(0); }
  }

  .drawer-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 24px 32px;
    background: linear-gradient(180deg, rgba(255,255,255,0.03) 0%, transparent 100%);
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  }

  .drawer-header h2 {
    margin: 0;
    font-size: 20px;
    font-weight: 700;
    background: linear-gradient(90deg, #fff 0%, #a1a1aa 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.01em;
  }

  .icon-button {
    width: 36px;
    height: 36px;
    display: grid;
    place-items: center;
    border: none;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.05);
    color: #a1a1aa;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .icon-button:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #fff;
    transform: rotate(90deg) scale(1.1);
  }

  .drawer-content {
    flex: 1;
    overflow-y: auto;
    padding: 32px;
    display: flex;
    flex-direction: column;
  }
  
  .drawer-content::-webkit-scrollbar {
    width: 6px;
  }
  .drawer-content::-webkit-scrollbar-thumb {
    background: rgba(255,255,255,0.1);
    border-radius: 10px;
  }

  .setup-section {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 24px;
  }

  .setup-section h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 700;
  }

  .section-desc {
    margin: 0;
    color: #a1a1aa;
    font-size: 14px;
    line-height: 1.5;
  }

  /* Form Fields */
  .form-field {
    display: grid;
    gap: 8px;
    min-width: 0;
  }

  .form-field span {
    color: #a1a1aa;
    font-size: 13px;
    font-weight: 600;
  }

  .form-field input,
  .form-field select {
    min-height: 44px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    background: rgba(0, 0, 0, 0.2);
    color: #fff;
    font: inherit;
    padding: 0 16px;
    transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
  }
  
  .form-field input:focus,
  .form-field select:focus {
    outline: none;
    background: rgba(0,0,0,0.4);
    border-color: rgba(34, 197, 94, 0.5);
    box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.15);
  }

  .form-field input[aria-invalid="true"] {
    border-color: rgba(239, 68, 68, 0.5);
    box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.15);
  }

  .field-hint {
    margin: 0;
    color: #71717a;
    font-size: 12px;
    line-height: 1.5;
  }

  /* Buttons */
  .action-row {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
  }

  .action-row button {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-height: 40px;
    padding: 0 16px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.03);
    color: #e4e4e7;
    font-weight: 600;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .action-row button:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.2);
    transform: translateY(-1px);
  }

  .action-row button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  /* Step Indicator */
  .step-indicator {
    display: flex;
    gap: 8px;
    font-size: 12px;
    font-weight: 700;
    color: #52525b;
    font-family: ui-monospace, monospace;
    margin-bottom: 8px;
  }

  .step-indicator span {
    padding: 4px 10px;
    border-radius: 6px;
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.05);
    transition: all 0.3s;
  }

  .step-indicator span.active {
    color: #22c55e;
    background: rgba(34, 197, 94, 0.1);
    border-color: rgba(34, 197, 94, 0.3);
    box-shadow: 0 0 12px rgba(34, 197, 94, 0.1);
  }

  /* Primary Button */
  .primary-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    min-height: 44px;
    padding: 0 24px;
    border: none;
    border-radius: 12px;
    background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
    box-shadow: 0 4px 14px rgba(22, 163, 74, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.2);
    color: #fff;
    font-weight: 800;
    font-size: 14px;
    text-shadow: 0 1px 2px rgba(0,0,0,0.3);
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  }

  .primary-button.full-width {
    width: 100%;
  }

  .primary-button:hover:not(:disabled) {
    background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
    box-shadow: 0 6px 20px rgba(34, 197, 94, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.3);
    transform: translateY(-2px) scale(1.02);
  }

  .primary-button:active:not(:disabled) {
    transform: translateY(0) scale(1);
    box-shadow: 0 2px 8px rgba(22, 163, 74, 0.3);
  }

  .primary-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    background: #3f3f46;
    box-shadow: none;
  }

  /* Hero AI State */
  .managed-view {
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
  }
  
  .hero-empty-state {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 48px 32px;
    background: linear-gradient(145deg, rgba(34, 197, 94, 0.08) 0%, rgba(255, 255, 255, 0.02) 100%);
    backdrop-filter: blur(12px);
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 24px 48px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.05);
    margin-bottom: 32px;
    overflow: hidden;
  }

  .hero-empty-state::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle at center, rgba(34, 197, 94, 0.1) 0%, transparent 60%);
    animation: rotateSlow 20s linear infinite;
    z-index: -1;
  }

  @keyframes rotateSlow {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  .hero-empty-state.connected-state {
    background: linear-gradient(145deg, rgba(34, 197, 94, 0.12) 0%, rgba(255, 255, 255, 0.03) 100%);
    border-color: rgba(34, 197, 94, 0.2);
  }

  @keyframes pulseGlow {
    0% { box-shadow: 0 0 20px rgba(34, 197, 94, 0.2), inset 0 0 15px rgba(34, 197, 94, 0.1); transform: scale(1); }
    50% { box-shadow: 0 0 40px rgba(34, 197, 94, 0.4), inset 0 0 25px rgba(34, 197, 94, 0.2); transform: scale(1.05); }
    100% { box-shadow: 0 0 20px rgba(34, 197, 94, 0.2), inset 0 0 15px rgba(34, 197, 94, 0.1); transform: scale(1); }
  }

  .hero-icon {
    display: grid;
    place-items: center;
    width: 88px;
    height: 88px;
    border-radius: 50%;
    background: linear-gradient(135deg, rgba(34, 197, 94, 0.2), rgba(34, 197, 94, 0.05));
    border: 1px solid rgba(34, 197, 94, 0.3);
    color: #4ade80;
    margin-bottom: 24px;
    animation: pulseGlow 4s infinite ease-in-out;
  }

  .ready-icon {
    background: linear-gradient(135deg, rgba(34, 197, 94, 0.25), rgba(34, 197, 94, 0.1));
    border: 1px solid rgba(34, 197, 94, 0.4);
    color: #4ade80;
  }

  .empty-title {
    font-size: 24px;
    font-weight: 800;
    margin-bottom: 12px;
    background: linear-gradient(to right, #fff, rgba(255, 255, 255, 0.7));
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.01em;
    line-height: 1.2;
  }

  .empty-desc {
    color: #a1a1aa;
    font-size: 15px;
    line-height: 1.6;
    margin-bottom: 32px;
    max-width: 90%;
  }

  .setup-actions {
    width: 100%;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
  }

  .run-model-btn {
    grid-column: 1 / -1;
  }

  .hero-button {
    height: auto;
    padding: 20px 16px;
    font-size: 15px;
    border-radius: 16px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    text-align: center;
    transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  }

  .primary-button.hero-button {
    background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
    box-shadow: 0 6px 20px rgba(34, 197, 94, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.3);
  }
  
  .secondary-button.hero-button {
    background: linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(34, 197, 94, 0.02) 100%);
    border: 1px solid rgba(34, 197, 94, 0.3);
    color: #4ade80;
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
  }

  .secondary-button.hero-button:hover:not(:disabled) {
    background: linear-gradient(135deg, rgba(34, 197, 94, 0.15) 0%, rgba(34, 197, 94, 0.05) 100%);
    border-color: rgba(34, 197, 94, 0.6);
    transform: translateY(-2px) scale(1.02);
    box-shadow: 0 8px 24px rgba(34, 197, 94, 0.25), inset 0 0 16px rgba(34, 197, 94, 0.15);
    color: #86efac;
  }

  .secondary-button.hero-button:active:not(:disabled) {
    transform: translateY(0) scale(1);
    box-shadow: 0 2px 8px rgba(34, 197, 94, 0.1);
    border-color: rgba(34, 197, 94, 0.4);
  }
  
  .secondary-button.hero-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    background: rgba(255, 255, 255, 0.02);
    border-color: rgba(255, 255, 255, 0.05);
    color: #71717a;
  }

  .hero-btn-text {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .btn-title {
    font-weight: 700;
    line-height: 1.1;
  }

  .btn-sub {
    font-size: 12px;
    font-weight: 500;
    opacity: 0.8;
  }

  /* Errors & Diagnostics */
  .fingerprint {
    display: grid;
    gap: 4px;
    padding-top: 16px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    color: #a1a1aa;
    font-size: 12px;
    font-weight: 600;
  }

  .fingerprint code {
    background: rgba(0,0,0,0.3);
    padding: 6px 10px;
    border-radius: 6px;
    font-family: ui-monospace, monospace;
    font-size: 11px;
    color: #d4d4d8;
    word-break: break-all;
  }

  .back-button {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: none;
    border: none;
    color: #a1a1aa;
    margin-bottom: 24px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: color 0.2s, transform 0.2s;
    padding: 0;
  }

  .back-button:hover {
    color: #fff;
    transform: translateX(-4px);
  }
  
  @media (max-width: 680px) {
    .drawer-panel {
      width: 100vw;
      border-left: none;
      border-radius: 0;
    }
  }
</style>
