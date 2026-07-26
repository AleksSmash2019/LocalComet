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
