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
  $: setupComplete = controlReady && sidecarReady && runtimeInstalled && modelInstalled && $managedModelReady;
  $: nextActionLabel = setupComplete ? $t('onboarding.open_chat') : $t('onboarding.setup_model');
  $: nextActionDetail = setupComplete ? $t('onboarding.ready_to_chat') : $t('onboarding.status_detail');

  function tone(ready: boolean, pending = false): string {
    if (ready) return 'ready';
    return pending ? 'info' : 'unknown';
  }

  function continueSetup(): void {
    if (setupComplete) {
      setActiveWorkspace('chat');
      return;
    }
    openSettings('models');
  }
</script>

<main id="setup-workspace" class="onboarding" aria-labelledby="onboarding-title">
  <div class="onboarding-card">
    <div class="mark"><LocalCometLogo size={58} /></div>
    <span class="eyebrow">{$t('onboarding.eyebrow')}</span>
    <h1 id="onboarding-title">{$t('onboarding.title')}</h1>
    <p class="lead">{$t('onboarding.subtitle')}</p>
    <div class="privacy"><Icon name="shield" size={16} /> {$t('onboarding.local_boundary')}</div>

    <section class="readiness-card" aria-labelledby="environment-title">
      <div class="section-heading">
        <div>
          <span class="step">{$t('onboarding.next_step')}</span>
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

    <div class="next-action">
      <div class="next-action-copy">
        <span class="step">{$t('onboarding.next_step')}</span>
        <strong>{nextActionDetail}</strong>
      </div>
      <button type="button" class="primary" onclick={continueSetup}>
        <Icon name={setupComplete ? 'chat' : 'model'} size={18} />
        {nextActionLabel}
      </button>
    </div>
    <p class="boundary">{$t('onboarding.boundary')}</p>
  </div>
</main>

<style>
  .onboarding { min-width: 0; min-height: 0; overflow-y: auto; padding: clamp(24px, 5vw, 64px); background: radial-gradient(ellipse 62% 46% at 50% 0%, color-mix(in srgb, var(--lc-accent) 13%, transparent), transparent 76%); }
  .onboarding-card { width: min(100%, 760px); display: grid; justify-items: center; gap: var(--lc-space-3); margin: 0 auto; }
  .mark { display: grid; place-items: center; width: 76px; height: 76px; border: var(--border-thin); border-radius: 22px; background: color-mix(in srgb, var(--lc-panel-solid) 82%, transparent); box-shadow: var(--lc-shadow-e2); }
  .eyebrow, .step { color: var(--lc-accent); font-family: var(--lc-mono); font-size: 11px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
  h1, h2, p { margin: 0; }
  h1 { font-size: clamp(25px, 4vw, 34px); letter-spacing: -.04em; text-align: center; }
  .lead { max-width: 600px; color: var(--lc-muted); line-height: 1.6; text-align: center; }
  .privacy { display: inline-flex; align-items: center; gap: var(--lc-space-2); color: var(--lc-accent); font-size: 12px; font-weight: 760; }
  section { width: 100%; display: grid; gap: var(--lc-space-3); margin-top: var(--lc-space-4); border: var(--border-thin); border-radius: var(--lc-radius-lg); padding: clamp(18px, 3vw, 28px); background: color-mix(in srgb, var(--lc-panel-solid) 90%, transparent); box-shadow: var(--lc-shadow-e1); }
  .section-heading, .section-heading > div, .checks > div { display: flex; align-items: center; }
  .section-heading { justify-content: space-between; gap: var(--lc-space-3); }
  .section-heading > div { gap: var(--lc-space-2); }
  h2 { font-size: 16px; }
  button { border: var(--border-thin); border-radius: var(--lc-radius-sm); padding: 0 var(--lc-space-3); background: var(--lc-panel-soft); cursor: pointer; }
  button:hover { border-color: var(--lc-line-strong); }
  .refresh { min-height: 34px; color: var(--lc-muted); font-size: 12px; }
  .checks { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--lc-space-2); }
  .checks > div { min-width: 0; justify-content: space-between; gap: var(--lc-space-2); border: 1px solid color-mix(in srgb, var(--lc-line) 72%, transparent); border-radius: var(--lc-radius-sm); padding: var(--lc-space-3); background: color-mix(in srgb, var(--lc-panel-soft) 72%, transparent); font-size: 12px; font-weight: 700; }
  .next-action { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: var(--lc-space-4); padding: var(--lc-space-4) var(--lc-space-5); border: 1px solid color-mix(in srgb, var(--lc-accent) 28%, var(--lc-line)); border-radius: var(--lc-radius-md); background: linear-gradient(90deg, color-mix(in srgb, var(--lc-accent) 10%, transparent), transparent); }
  .next-action-copy { display: grid; gap: 3px; min-width: 0; }
  .next-action-copy strong { font-size: 14px; line-height: 1.35; }
  .primary { display: inline-flex; flex: 0 0 auto; align-items: center; gap: var(--lc-space-2); min-height: 42px; border-color: var(--lc-accent); background: var(--lc-accent); color: var(--lc-logo-cut); font-weight: 800; }
  .boundary { max-width: 620px; color: var(--lc-faint); font-size: 11px; line-height: 1.5; text-align: center; }
  @media (max-width: 620px) { .checks { grid-template-columns: 1fr; } .section-heading, .next-action { align-items: flex-start; } .next-action { flex-direction: column; } .next-action .primary { width: 100%; justify-content: center; } }
</style>
