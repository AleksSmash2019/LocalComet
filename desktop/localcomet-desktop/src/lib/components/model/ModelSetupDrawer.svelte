<script lang="ts">
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
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
  import { selectManagedSetupModelId } from '$lib/stores/modelDefault';
  import { scanHardwareSnapshot, systemDiskFreeBytes } from '$lib/bridge/hardware';
  import { t } from '$lib/i18n';

  export let onClose: () => void = () => {};

  let portInput = '';
  $: portValid = /^\d+$/.test(portInput) && Number(portInput) >= 1024 && Number(portInput) <= 65535;

  // Free space on the system disk (null = probe failed; cards stay neutral).
  let systemFreeBytes: number | null = null;
  const DISK_RESERVE_BYTES = 2 * 1024 * 1024 * 1024;

  type FitVerdict = 'installed' | 'fits' | 'tight' | 'wont_fit' | 'unknown';

  function fitVerdict(model: ManagedModelChoice): FitVerdict {
    if (model.installed) return 'installed';
    if (systemFreeBytes === null || model.size_bytes === null) return 'unknown';
    const required = model.size_bytes + DISK_RESERVE_BYTES;
    if (systemFreeBytes < required) return 'wont_fit';
    if (systemFreeBytes < required * 2) return 'tight';
    return 'fits';
  }

  function fitLabel(model: ManagedModelChoice): string {
    switch (fitVerdict(model)) {
      case 'installed': return $t('setup.fit_installed');
      case 'fits': return $t('setup.fit_fits');
      case 'tight': return $t('setup.fit_tight');
      case 'wont_fit': return $t('setup.fit_wont');
      default: return '';
    }
  }

  // External flow state
  $: canBindExternal = !$inferenceBusy && portValid && Boolean($modelGatewayStore.selectedModelId);
  $: externalStep = !$modelGatewayStore.catalog ? 0 : portValid ? 1 : $modelGatewayStore.models.length ? 2 : 3;

  // Managed flow state
  $: managedState = $managedRuntimeStore.status?.state ?? 'NotInstalled';
  $: managedSelectedModel = $managedRuntimeStore.catalog.find((m) => m.model_id === $managedRuntimeStore.selectedModelId) ?? null;
  $: managedSetupRunning = $artifactAcquisitionStore.setup.lifecycle === 'running' || $acquisitionBusy;

  type ManagedModelChoice = {
    readonly model_id: string;
    readonly display_name: string;
    readonly installed: boolean;
    readonly source: 'catalog' | 'custom';
    readonly size_bytes: number | null;
  };

  function isForbiddenModel(modelId: string, displayName: string): boolean {
    return /qwen2\.5[- _]?1\.5b/i.test(`${modelId} ${displayName}`);
  }

  const GB = 1024 * 1024 * 1024;

  function modelLabel(model: ManagedModelChoice): string {
    const suffix = model.installed ? $t('setup.model_installed_suffix') : '';
    const size = model.size_bytes
      ? ` · ${(model.size_bytes / GB).toFixed(1)} GB`
      : '';
    return `${model.display_name}${size}${suffix}`;
  }

  // The drawer must use the same union as Settings: approved catalog models
  // plus custom/user-supplied models. The old implementation only looked at
  // managedRuntimeStore.catalog and then hid the selector unless >1 installed
  // entries existed, which made a valid custom Qwen3 model disappear behind
  // the one-click setup hero.
  // Grouping: the flat union read as "каша" (screenshot) — catalog entries and
  // raw user .gguf filenames sat in one unsorted list. Each choice now carries
  // its source and size so the <select> can render labelled optgroups with the
  // installed models on top.
  $: visibleManagedModels = (() => {
    const byId = new Map<string, ManagedModelChoice>();
    const isInstalled = (modelId: string) => $managedRuntimeStore.installedArtifacts.some((artifact) =>
      artifact.kind === 'model' && artifact.artifact_id === modelId && artifact.installation_status === 'valid'
    );
    for (const model of $managedRuntimeStore.catalog) {
      if (isForbiddenModel(model.model_id, model.display_name)) continue;
      byId.set(model.model_id, {
        model_id: model.model_id,
        display_name: model.display_name,
        installed: isInstalled(model.model_id),
        source: 'catalog',
        size_bytes: model.asset_bytes ?? null
      });
    }
    const normalizeName = (name: string): string =>
      name.toLowerCase().replace(/\.gguf$/, '').replace(/[-_\s.]+/g, '-');
    const catalogNames = new Set(
      [...byId.values()].map((choice) => normalizeName(choice.display_name))
    );
    for (const artifact of $artifactAcquisitionStore.artifacts) {
      if (artifact.kind !== 'model' || isForbiddenModel(artifact.artifact_id, artifact.display_name)) continue;
      // A custom .gguf that names an existing catalog model is the same file
      // to the user; showing both read as "каша". The catalog entry wins.
      if (artifact.trust_kind !== 'approved_catalog' && catalogNames.has(normalizeName(artifact.display_name))) {
        continue;
      }
      byId.set(artifact.artifact_id, {
        model_id: artifact.artifact_id,
        display_name: artifact.display_name,
        installed: isInstalled(artifact.artifact_id),
        source: artifact.trust_kind === 'approved_catalog' ? 'catalog' : 'custom',
        size_bytes: artifact.expected_bytes ?? null
      });
    }
    const choices = [...byId.values()];
    const rank = (choice: ManagedModelChoice): number =>
      (choice.installed ? 0 : 1) * 10 + (choice.source === 'catalog' ? 0 : 1);
    return choices.sort((a, b) => rank(a) - rank(b) || a.display_name.localeCompare(b.display_name));
  })();
  $: recommendedChoices = visibleManagedModels.filter((model) => model.installed && model.source === 'catalog');
  $: catalogChoices = visibleManagedModels.filter((model) => model.source === 'catalog');
  $: customChoices = visibleManagedModels.filter((model) => model.source === 'custom');
  $: selectedAvailableModel = visibleManagedModels.find((model) => model.model_id === $managedRuntimeStore.selectedModelId) ?? null;
  $: managedModelLaunchable = $managedRuntimeStore.readiness?.model_id === selectedAvailableModel?.model_id && $managedRuntimeStore.readiness?.launchable === true;
  $: canBindManaged = !$inferenceBusy && !$managedConnectionBusy && !managedSetupRunning && !$managedModelReady && Boolean(setupTargetModelId);
  $: managedTone = managedState === 'Ready' ? 'ready' : managedState === 'Failed' ? 'danger' : managedState === 'Starting' || managedState === 'Validating' || managedState === 'Stopping' ? 'info' : 'disabled';
  $: selectedModelIdIsAvailable = visibleManagedModels.some((model) => model.model_id === $managedRuntimeStore.selectedModelId);
  $: setupTargetModelId = selectManagedSetupModelId(visibleManagedModels, $managedRuntimeStore.selectedModelId);
  $: setupTargetLabel = visibleManagedModels.find((model) => model.model_id === setupTargetModelId)?.display_name ?? $t('setup.select_local_model');
  $: canSetupManaged = !$inferenceBusy && !$managedConnectionBusy && !managedSetupRunning && !$managedModelReady && Boolean(setupTargetModelId);
  $: activeDownload = Object.values($artifactAcquisitionStore.downloads).find(d => !['cancelled', 'completed', 'failed'].includes(d.lifecycle)) ?? null;

  $: synthesizedPhase = (() => {
    if (managedState === 'Validating') return $t('models.phase.validating_runtime');
    if (managedState === 'Starting' && $managedRuntimeStore.status?.model_state === 'Validating') return $t('models.phase.validating_runtime');
    if (managedState === 'Starting' && $managedRuntimeStore.status?.model_state === 'Loading') return $t('models.phase.loading_model');
    if (managedState === 'Starting') return $t('models.phase.gpu_init');
    if (managedState === 'Ready' && !$managedRuntimeStore.status?.inference_ready) return $t('models.phase.connecting');
    if (managedState === 'Stopping') return $t('models.phase.stopping');
    return '';
  })();

  function displayState(state: string): string {
    return $t(`models.state.${state}`);
  }

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
    const targetModelId = selectedModelIdIsAvailable ? $managedRuntimeStore.selectedModelId : setupTargetModelId;
    if (!targetModelId) return;
    if ($managedRuntimeStore.selectedModelId !== targetModelId) {
      await setManagedSelectedModel(targetModelId);
    }
    const currentReadiness = get(managedRuntimeStore).readiness;
    const isLaunchable = currentReadiness?.model_id === targetModelId && currentReadiness?.launchable === true;
    if (isLaunchable || managedModelLaunchable) {
      const connected = await connectSelectedManagedModel();
      if (connected) {
        closeModelSetup();
      }
    } else {
      const connected = await downloadAndSetupManagedModel(targetModelId);
      if (connected) {
        closeModelSetup();
      }
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
    // The drawer can open before the shell's initial refresh settles. Refresh
    // here so installed custom models are visible instead of presenting an
    // empty first-run state.
    void refreshManagedRuntimeStatus();
    void initializeArtifactAcquisition();
    // Fit verdicts need the real free space on the system disk (audit finding:
    // a 20 GB disk must warn before a 5 GB download, not after).
    void scanHardwareSnapshot()
      .then((hardware) => {
        systemFreeBytes = systemDiskFreeBytes(hardware);
      })
      .catch(() => {
        systemFreeBytes = null;
      });
  });

  // Close drawer on Escape handled by shellStore
</script>

<div class="model-setup-drawer" id="model-setup-drawer" data-testid="model-setup-drawer" data-managed-state={managedState} role="dialog" aria-modal="true" aria-labelledby="model-setup-title">
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
          <span>{$t('setup.btn_back')}</span>
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
              {#if visibleManagedModels.length > 0}
                <fieldset class="model-picker" disabled={managedSetupRunning}>
                  <legend>{$t('setup.pick_title')}</legend>
                  {#each visibleManagedModels.slice(0, 8) as model (model.model_id)}
                    {@const verdict = fitVerdict(model)}
                    <button
                      type="button"
                      class="model-card"
                      class:selected={$managedRuntimeStore.selectedModelId === model.model_id}
                      class:card-wont-fit={verdict === 'wont_fit'}
                      aria-pressed={$managedRuntimeStore.selectedModelId === model.model_id}
                      onclick={() => void setManagedSelectedModel(model.model_id)}
                    >
                      <span class="model-card-main">
                        <span class="model-card-name">
                          {model.display_name}
                          {#if model.source === 'catalog' && model.model_id === 'qwen3.5-4b-q4-k-m'}
                            <span class="model-card-tag tag-recommended">{$t('setup.badge_recommended')}</span>
                          {/if}
                        </span>
                        <span class="model-card-meta">
                          {#if model.size_bytes}<span>{(model.size_bytes / GB).toFixed(1)} GB</span>{/if}
                          <span class="model-card-tag" class:tag-installed={model.installed}>
                            {model.installed ? $t('setup.badge_installed') : $t('setup.badge_download')}
                          </span>
                          {#if verdict !== 'installed' && fitLabel(model)}
                            <span class="fit-verdict" class:fit-bad={verdict === 'wont_fit'} class:fit-tight={verdict === 'tight'}>
                              {fitLabel(model)}
                            </span>
                          {/if}
                        </span>
                      </span>
                      {#if $managedRuntimeStore.selectedModelId === model.model_id}
                        <Icon name="check" size={18} />
                      {/if}
                    </button>
                  {/each}
                </fieldset>
                <button
                  type="button"
                  class="model-fit-link"
                  onclick={() => { closeModelSetup(); setActiveWorkspace('modelfit'); }}
                >
                  <Icon name="diag" size={15} />
                  <span>{$t('setup.not_sure_fit')}</span>
                </button>
              {/if}
              <span class="setup-kicker">{$t('setup.recommended_path')}</span>
              <p class="empty-title">{$t('setup.hero_title')}</p>
              <p class="empty-desc">{$t('setup.hero_desc')}</p>
              
              {#if managedSetupRunning}
                <DownloadProgress
                  title={$t('models.setup_progress')}
                  detail={activeDownload ? `${(activeDownload.received_bytes / 1024 / 1024).toFixed(1)} / ${(activeDownload.expected_bytes / 1024 / 1024).toFixed(1)} MiB` : $t('setup.please_wait')}
                  phase={activeDownload ? displayState(activeDownload.lifecycle) : synthesizedPhase}
                  percent={activeDownload?.percent ?? null}
                  onCancel={activeDownload ? () => void cancelApprovedArtifactDownload(activeDownload.artifact_id) : null}
                />
              {:else}
                <div class="setup-actions">
                  <button
                    type="button"
                    class="primary-button hero-button run-model-btn"
                    data-testid="managed-model-primary-action"
                    aria-label={$t('models.setup')}
                    disabled={!canSetupManaged}
                    onclick={onConfirmManagedBinding}
                  >
                      <Icon name="spark" size={24} />
                      <div class="hero-btn-text">
                        <span class="btn-title">{$t('models.setup')}</span>
                      <span class="btn-sub">{setupTargetLabel}</span>
                      </div>
                  </button>
                  <button
                    type="button"
                    class="secondary-button hero-button"
                    aria-label={$t('setup.btn_hf_catalog')}
                    onclick={onGoToHfCatalog}
                  >
                    <Icon name="search" size={24} />
                    <div class="hero-btn-text">
                      <span class="btn-title">{$t('setup.btn_hf_catalog')}</span>
                      <span class="btn-sub">{$t('setup.btn_hf_sub')}</span>
                    </div>
                  </button>
                  <button
                    type="button"
                    class="secondary-button hero-button"
                    aria-label={$t('setup.btn_gguf')}
                    onclick={onOpenModelSettings}
                  >
                    <Icon name="folder" size={24} />
                    <div class="hero-btn-text">
                      <span class="btn-title">{$t('setup.btn_gguf')}</span>
                      <span class="btn-sub">{$t('setup.btn_gguf_sub')}</span>
                    </div>
                  </button>
                  <button
                    type="button"
                    class="secondary-button hero-button"
                    aria-label={$t('setup.btn_external')}
                    onclick={() => modelSetupMode.set('external')}
                  >
                    <Icon name="plug" size={24} />
                    <div class="hero-btn-text">
                      <span class="btn-title">{$t('setup.btn_external')}</span>
                      <span class="btn-sub">{$t('setup.btn_external_sub')}</span>
                    </div>
                  </button>
                </div>
              {/if}
            </div>
          {:else}
            {#if visibleManagedModels.length > 0}
              <label class="form-field">
                <span>{$t('setup.model')}</span>
                <select disabled={$inferenceBusy} value={$managedRuntimeStore.selectedModelId} onchange={(e) => void setManagedSelectedModel((e.currentTarget as HTMLSelectElement).value)}>
                  <option value="">{$t('setup.select_local_model')}</option>
                  {#if recommendedChoices.length > 0}
                    <optgroup label={$t('setup.group_installed')}>
                      {#each recommendedChoices as model}
                        <option value={model.model_id}>{modelLabel(model)}</option>
                      {/each}
                    </optgroup>
                  {/if}
                  {#if catalogChoices.length > recommendedChoices.length}
                    <optgroup label={$t('setup.group_catalog')}>
                      {#each catalogChoices.filter((model) => !model.installed) as model}
                        <option value={model.model_id}>{modelLabel(model)}</option>
                      {/each}
                    </optgroup>
                  {/if}
                  {#if customChoices.length > 0}
                    <optgroup label={$t('setup.group_custom')}>
                      {#each customChoices as model}
                        <option value={model.model_id}>{modelLabel(model)}</option>
                      {/each}
                    </optgroup>
                  {/if}
                </select>
              </label>
            {/if}

            <div class="hero-empty-state connected-state">
              <div class="hero-icon ready-icon">
                <Icon name="check" size={48} />
              </div>
              <span class="setup-kicker">{$t('setup.ready_to_launch')}</span>
              <p class="empty-title">{$t('setup.hero_ready_title')}</p>
              <p class="empty-desc">{$t('setup.hero_ready_desc')}</p>

              {#if managedSetupRunning}
                <DownloadProgress
                  title={$t('models.setup_progress')}
                  detail={activeDownload ? `${(activeDownload.received_bytes / 1024 / 1024).toFixed(1)} / ${(activeDownload.expected_bytes / 1024 / 1024).toFixed(1)} MiB` : $t('setup.please_wait')}
                  phase={activeDownload ? displayState(activeDownload.lifecycle) : synthesizedPhase}
                  percent={activeDownload?.percent ?? null}
                  onCancel={activeDownload ? () => void cancelApprovedArtifactDownload(activeDownload.artifact_id) : null}
                />
              {:else}
                <div class="setup-actions">
                  <button
                    type="button"
                    class="primary-button hero-button run-model-btn"
                    data-testid="managed-model-primary-action"
                    aria-label={$t('setup.btn_run')}
                    disabled={!canBindManaged}
                    onclick={onConfirmManagedBinding}
                  >
                    <Icon name="play" size={24} />
                    <div class="hero-btn-text">
                      <span class="btn-title">{$t($managedConnectionBusy ? 'chat.model_connecting' : 'setup.connect')}</span>
                      <span class="btn-sub">{$t('setup.selected_model')}: {setupTargetLabel}</span>
                    </div>
                  </button>
                  <p class="auto-engine-hint">{$t('setup.auto_engine_hint')}</p>
                  <button
                    type="button"
                    class="secondary-button hero-button"
                    aria-label={$t('setup.btn_hf_catalog')}
                    onclick={onGoToHfCatalog}
                  >
                    <Icon name="search" size={24} />
                    <div class="hero-btn-text">
                      <span class="btn-title">{$t('setup.btn_hf_catalog')}</span>
                      <span class="btn-sub">{$t('setup.btn_hf_sub')}</span>
                    </div>
                  </button>
                  <button
                    type="button"
                    class="secondary-button hero-button"
                    aria-label={$t('setup.btn_gguf')}
                    onclick={onOpenModelSettings}
                  >
                    <Icon name="folder" size={24} />
                    <div class="hero-btn-text">
                      <span class="btn-title">{$t('setup.btn_gguf')}</span>
                      <span class="btn-sub">{$t('setup.btn_gguf_sub')}</span>
                    </div>
                  </button>
                  <button
                    type="button"
                    class="secondary-button hero-button"
                    aria-label={$t('setup.btn_external')}
                    onclick={() => modelSetupMode.set('external')}
                  >
                    <Icon name="plug" size={24} />
                    <div class="hero-btn-text">
                      <span class="btn-title">{$t('setup.btn_external')}</span>
                      <span class="btn-sub">{$t('setup.btn_external_sub')}</span>
                    </div>
                  </button>
                </div>
              {/if}
            </div>

            {#if $managedConnectionBusy}
              <DownloadProgress
                title={$t('models.connecting')}
                detail={$managedRuntimeStore.status?.loading_phase || $t('chat.model_loading_detail')}
                phase={synthesizedPhase}
                percent={null}
                onCancel={null}
              />
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
    background: var(--lc-bg-elevated);
    backdrop-filter: blur(32px);
    border-left: 1px solid var(--lc-line);
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
    background: linear-gradient(180deg, color-mix(in srgb, var(--lc-text) 3%, transparent) 0%, transparent 100%);
    border-bottom: 1px solid var(--lc-line);
  }

  .drawer-header h2 {
    margin: 0;
    font-size: 20px;
    font-weight: 700;
    color: var(--lc-text);
    letter-spacing: -0.01em;
  }

  .icon-button {
    width: 36px;
    height: 36px;
    display: grid;
    place-items: center;
    border: none;
    border-radius: 50%;
    background: color-mix(in srgb, var(--lc-text) 5%, transparent);
    color: var(--lc-muted);
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .icon-button:hover {
    background: color-mix(in srgb, var(--lc-text) 10%, transparent);
    color: var(--lc-text);
    transform: rotate(90deg) scale(1.1);
  }

  .drawer-content {
    flex: 1;
    overflow-y: auto;
    padding: 28px;
    display: flex;
    flex-direction: column;
  }
  
  .drawer-content::-webkit-scrollbar {
    width: 6px;
  }
  .drawer-content::-webkit-scrollbar-thumb {
    background: color-mix(in srgb, var(--lc-line) 80%, transparent);
    border-radius: 10px;
  }

  .setup-section {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .setup-section h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 700;
    color: var(--lc-text);
  }

  .section-desc {
    margin: 0;
    color: var(--lc-muted);
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
    color: var(--lc-muted);
    font-size: 13px;
    font-weight: 600;
  }

  .form-field input,
  .form-field select {
    min-height: 44px;
    border: 1px solid var(--lc-line);
    border-radius: var(--radius-2);
    background: color-mix(in srgb, var(--lc-bg) 60%, transparent);
    color: var(--lc-text);
    font: inherit;
    padding: 0 16px;
    transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
  }
  
  .form-field input:focus,
  .form-field select:focus {
    outline: none;
    background: var(--lc-panel-soft);
    border-color: var(--lc-accent);
    box-shadow: 0 0 0 3px var(--lc-accent-dim);
  }

  .form-field input[aria-invalid="true"] {
    border-color: var(--lc-danger);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--lc-danger) 20%, transparent);
  }

  .field-hint {
    margin: 0;
    color: var(--lc-faint);
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
    border: 1px solid var(--lc-line);
    border-radius: var(--radius-1);
    background: color-mix(in srgb, var(--lc-text) 3%, transparent);
    color: var(--lc-text);
    font-weight: 600;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .action-row button:hover:not(:disabled) {
    background: color-mix(in srgb, var(--lc-text) 8%, transparent);
    border-color: var(--lc-accent);
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
    color: var(--lc-faint);
    font-family: var(--lc-mono);
    margin-bottom: 8px;
  }

  .step-indicator span {
    padding: 4px 10px;
    border-radius: var(--radius-1);
    background: color-mix(in srgb, var(--lc-bg) 50%, transparent);
    border: 1px solid var(--lc-line);
    transition: all 0.3s;
  }

  .step-indicator span.active {
    color: var(--lc-accent-strong);
    background: var(--lc-accent-dim);
    border-color: var(--lc-accent);
    box-shadow: 0 0 12px var(--lc-accent-dim);
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
    border-radius: var(--radius-2);
    background: var(--lc-accent);
    box-shadow: 0 4px 14px color-mix(in srgb, var(--lc-accent) 30%, transparent);
    color: var(--lc-logo-cut);
    font-weight: 800;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  }

  .primary-button.full-width {
    width: 100%;
  }

  .primary-button:hover:not(:disabled) {
    background: var(--lc-accent-strong);
    box-shadow: 0 6px 20px color-mix(in srgb, var(--lc-accent) 45%, transparent);
    transform: translateY(-2px) scale(1.02);
  }

  .primary-button:active:not(:disabled) {
    transform: translateY(0) scale(1);
    box-shadow: 0 2px 8px color-mix(in srgb, var(--lc-accent) 30%, transparent);
  }

  .primary-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    background: var(--lc-panel-soft);
    color: var(--lc-muted);
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
    padding: 32px 24px 24px;
    background: linear-gradient(145deg, var(--lc-accent-dim) 0%, transparent 100%);
    backdrop-filter: blur(12px);
    border-radius: var(--radius-3);
    border: 1px solid var(--lc-line);
    box-shadow: var(--lc-shadow);
    margin-bottom: 20px;
    overflow: hidden;
  }

  .hero-empty-state::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle at center, var(--lc-accent-dim) 0%, transparent 60%);
    opacity: 0.7;
    z-index: -1;
  }

  .hero-empty-state.connected-state {
    background: linear-gradient(145deg, color-mix(in srgb, var(--lc-accent) 15%, transparent) 0%, transparent 100%);
    border-color: color-mix(in srgb, var(--lc-accent) 30%, transparent);
  }

  @keyframes pulseGlow {
    0% { box-shadow: 0 0 20px color-mix(in srgb, var(--lc-accent) 20%, transparent); transform: scale(1); }
    50% { box-shadow: 0 0 40px color-mix(in srgb, var(--lc-accent) 40%, transparent); transform: scale(1.05); }
    100% { box-shadow: 0 0 20px color-mix(in srgb, var(--lc-accent) 20%, transparent); transform: scale(1); }
  }

  .hero-icon {
    display: grid;
    place-items: center;
    width: 64px;
    height: 64px;
    border-radius: 50%;
    background: linear-gradient(135deg, color-mix(in srgb, var(--lc-accent) 20%, transparent), color-mix(in srgb, var(--lc-accent) 5%, transparent));
    border: 1px solid color-mix(in srgb, var(--lc-accent) 35%, transparent);
    color: var(--lc-accent-strong);
    margin-bottom: 14px;
  }

  .ready-icon {
    background: linear-gradient(135deg, color-mix(in srgb, var(--lc-accent) 25%, transparent), color-mix(in srgb, var(--lc-accent) 10%, transparent));
    border: 1px solid color-mix(in srgb, var(--lc-accent) 40%, transparent);
    color: var(--lc-accent-strong);
  }

  .empty-title {
    font-size: 22px;
    font-weight: 800;
    margin-bottom: 8px;
    color: var(--lc-text);
    letter-spacing: -0.01em;
    line-height: 1.2;
  }

  .empty-desc {
    color: var(--lc-muted);
    font-size: 15px;
    line-height: 1.6;
    margin-bottom: 22px;
    max-width: 460px;
  }

  .setup-actions {
    width: 100%;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
  }

  .model-picker {
    width: 100%;
    border: none;
    margin: 0 0 14px;
    padding: 0;
    display: grid;
    gap: 8px;
  }

  .model-picker legend {
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 8px;
    padding: 0;
  }

  .model-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    width: 100%;
    padding: 11px 14px;
    border-radius: 12px;
    border: 1px solid color-mix(in srgb, var(--lc-line) 70%, transparent);
    background: color-mix(in srgb, var(--lc-panel) 60%, transparent);
    color: var(--lc-text);
    text-align: left;
    cursor: pointer;
    transition: border-color 0.16s ease, background 0.16s ease, transform 0.16s ease;
  }

  .model-card:hover {
    border-color: color-mix(in srgb, var(--lc-accent) 55%, var(--lc-line));
    transform: translateY(-1px);
  }

  .model-card.selected {
    border-color: var(--lc-accent);
    background: color-mix(in srgb, var(--lc-accent) 10%, transparent);
  }

  .model-card-main {
    display: grid;
    gap: 3px;
    min-width: 0;
  }

  .model-card-name {
    font-size: 14px;
    font-weight: 620;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .model-card-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--lc-muted);
    font-size: 12px;
  }

  .model-card-tag {
    padding: 1px 8px;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--lc-line) 80%, transparent);
  }

  .model-card-tag.tag-installed {
    color: var(--lc-accent);
    border-color: color-mix(in srgb, var(--lc-accent) 45%, transparent);
  }

  .fit-verdict {
    color: var(--lc-accent);
  }

  .fit-verdict.fit-tight {
    color: var(--lc-warning);
  }

  .fit-verdict.fit-bad {
    color: var(--lc-danger);
  }

  .model-card-tag.tag-recommended {
    color: var(--lc-accent);
    border-color: color-mix(in srgb, var(--lc-accent) 50%, transparent);
    background: color-mix(in srgb, var(--lc-accent) 10%, transparent);
  }

  .model-card.card-wont-fit {
    opacity: 0.55;
  }

  .model-fit-link {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    margin-bottom: 16px;
    padding: 0;
    border: none;
    background: transparent;
    color: var(--lc-accent);
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
  }

  .model-fit-link:hover {
    text-decoration: underline;
  }

  .run-model-btn {
    grid-column: 1 / -1;
  }

  .hero-button {
    min-height: 72px;
    padding: 12px;
    font-size: 13px;
    border-radius: var(--radius-2);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    text-align: center;
    transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  }

  .primary-button.hero-button {
    background: var(--lc-accent);
    color: var(--lc-logo-cut);
    box-shadow: 0 6px 20px color-mix(in srgb, var(--lc-accent) 30%, transparent);
  }
  
  .secondary-button.hero-button {
    background: color-mix(in srgb, var(--lc-panel-soft) 80%, transparent);
    border: 1px solid var(--lc-line);
    color: var(--lc-text);
    box-shadow: var(--lc-shadow-e1);
  }

  .secondary-button.hero-button:hover:not(:disabled) {
    background: color-mix(in srgb, var(--lc-accent) 15%, transparent);
    border-color: var(--lc-accent);
    transform: translateY(-2px) scale(1.02);
    box-shadow: 0 8px 24px var(--lc-accent-dim);
    color: var(--lc-accent-strong);
  }

  .secondary-button.hero-button:active:not(:disabled) {
    transform: translateY(0) scale(1);
    box-shadow: 0 2px 8px color-mix(in srgb, var(--lc-accent) 15%, transparent);
    border-color: var(--lc-accent);
  }
  
  .secondary-button.hero-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    background: color-mix(in srgb, var(--lc-text) 2%, transparent);
    border-color: var(--lc-line);
    color: var(--lc-faint);
  }

  .setup-kicker {
    margin-bottom: 8px;
    color: var(--lc-accent);
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .auto-engine-hint {
    grid-column: 1 / -1;
    margin: 0;
    color: var(--lc-faint);
    font-size: 12px;
    line-height: 1.5;
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
    border-top: 1px solid var(--lc-line);
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 600;
  }

  .fingerprint code {
    background: color-mix(in srgb, var(--lc-bg) 60%, transparent);
    padding: 6px 10px;
    border-radius: var(--radius-1);
    font-family: var(--lc-mono);
    font-size: 11px;
    color: var(--lc-text);
    word-break: break-all;
  }

  .back-button {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: none;
    border: none;
    color: var(--lc-muted);
    margin-bottom: 24px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: color 0.2s, transform 0.2s;
    padding: 0;
  }

  .back-button:hover {
    color: var(--lc-text);
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
