<script lang="ts">
  import { DESKTOP_SHELL_VERSION } from '$lib/version';
  import EventStream from '$lib/components/common/EventStream.svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import PolicyDecision from '$lib/components/common/PolicyDecision.svelte';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import TelemetryRow from '$lib/components/common/TelemetryRow.svelte';
  import { controlPlaneStore, cancelCurrentDemoTurn, startCancellationDemo } from '$lib/stores/controlPlane';
  import { modelGatewayStore } from '$lib/stores/modelGateway';
  import { activeInspectorSection, inspectorVisible, setActiveInspectorSection } from '$lib/stores/shellStore';
  import type { InspectorSection } from '$lib/data/mockData';
  import { inspectorSections } from '$lib/data/mockData';
  import { t } from '$lib/i18n';

  export let className = '';
  export let onClose: () => void = () => undefined;

  $: sessionShort = shortId($controlPlaneStore.currentSession?.session_id, $t);
  $: threadShort = shortId($controlPlaneStore.currentThread?.thread_id, $t);
  $: turnShort = shortId($controlPlaneStore.currentTurn?.turn_id, $t);
  $: currentItem = $controlPlaneStore.items[$controlPlaneStore.items.length - 1];
  $: turnState = $controlPlaneStore.currentTurn?.state ?? $t('diag.not_started');
  $: cancelEnabled = $controlPlaneStore.currentTurn?.state === 'RUNNING';
  $: startEnabled = $controlPlaneStore.bridgeState === 'READY';

  $: bridgeLabel =
    $controlPlaneStore.bridgeState === 'READY'
      ? $t('diag.control_plane_connected')
      : $controlPlaneStore.bridgeState === 'CONNECTING'
        ? $t('diag.control_plane_starting')
        : $controlPlaneStore.bridgeState === 'UNAVAILABLE'
          ? $t('diag.control_plane_unavailable')
          : $controlPlaneStore.bridgeState === 'ERROR'
            ? $t('diag.control_plane_error')
            : $t('diag.control_plane_unknown');
  $: bridgeTone =
    $controlPlaneStore.bridgeState === 'READY'
      ? 'ready'
      : $controlPlaneStore.bridgeState === 'CONNECTING'
        ? 'info'
        : $controlPlaneStore.bridgeState === 'ERROR'
          ? 'danger'
          : $controlPlaneStore.bridgeState === 'UNAVAILABLE'
            ? 'disabled'
            : 'unknown';
  $: sidecarLabel = $controlPlaneStore.bootstrap?.sidecar_ready ? $t('diag.sidecar_ready') : $t('diag.sidecar_unknown');
  $: sidecarTone = $controlPlaneStore.bootstrap?.sidecar_ready ? 'ready' : 'unknown';

  type Translate = (key: string) => string;

  function shortId(value: string | undefined, translate: Translate): string {
    return value ? `${value.slice(0, 6)}...${value.slice(-4)}` : translate('diag.unknown');
  }

  function translateTurnState(state: string, translate: Translate): string {
    switch (state) {
      case 'RUNNING': return translate('diag.running');
      case 'COMPLETED': return translate('diag.completed');
      case 'CANCELLED': return translate('diag.cancelled');
      case 'FAILED': return translate('diag.error');
      case 'Not run': return translate('diag.not_run');
      default: return state;
    }
  }

  function translateModelCalled(called: boolean, translate: Translate): string {
    return called ? translate('diag.yes') : translate('diag.no');
  }

  function translateGatewayStatus(status: string, translate: Translate): string {
    switch (status) {
      case 'Not configured': return translate('diag.not_configured');
      case 'Probing': return translate('diag.probing');
      case 'Unavailable': return translate('diag.unavailable');
      case 'Ready': return translate('diag.ready');
      case 'Binding required': return translate('diag.binding_required');
      case 'Bound': return translate('diag.bound');
      case 'Generating': return translate('diag.generating');
      case 'Cancelling': return translate('diag.cancelling');
      case 'Completed': return translate('diag.completed');
      case 'Cancelled': return translate('diag.cancelled');
      case 'Failed': return translate('diag.failed');
      default: return status;
    }
  }

  function translatePersistence(value: string, translate: Translate): string {
    return value === 'Off' ? translate('diag.off') : value;
  }
</script>

<aside class="diagnostics {className}" class:hidden={!$inspectorVisible && !className} aria-label={$t('diag.title')}>
  <header>
    <div>
      <span class="eyebrow">{$t('diag.title')}</span>
      <h2>{$t('diag.runtime_state')}</h2>
    </div>
    <button type="button" class="plain-button close-button" aria-label={$t('diag.close')} onclick={onClose}>
      <Icon name="cancel" size={16} />
      <span>{$t('diag.close')}</span>
    </button>
  </header>

  <div class="tabs" role="tablist" aria-label={$t('diag.sections_label')}>
    {#each inspectorSections as section}
      <button
        type="button"
        class="section-tab"
        role="tab"
        aria-selected={$activeInspectorSection === section}
        onclick={() => setActiveInspectorSection(section as InspectorSection)}
      >
        {$t('diag.tab_' + section)}
      </button>
    {/each}
  </div>

  <section class="summary" aria-label={$t('diag.summary')}>
    <StatusBadge label={bridgeLabel} tone={bridgeTone} />
    <StatusBadge label={sidecarLabel} tone={sidecarTone} />
  </section>

  <section aria-label={$t('diag.summary')}>
    <h3>{$t('diag.summary')}</h3>
    <dl>
      <TelemetryRow label={$t('diag.session')} value={sessionShort} tone={$controlPlaneStore.currentSession ? 'ready' : 'unknown'} mono />
      <TelemetryRow label={$t('diag.thread')} value={threadShort} tone={$controlPlaneStore.currentThread ? 'ready' : 'unknown'} mono />
      <TelemetryRow label={$t('diag.turn')} value={turnShort} tone={$controlPlaneStore.currentTurn ? 'info' : 'unknown'} mono />
      <TelemetryRow label={$t('diag.turn_state')} value={translateTurnState(turnState, $t)} tone={$controlPlaneStore.currentTurn ? 'info' : 'unknown'} />
      <TelemetryRow label={$t('diag.current_item')} value={currentItem?.kind ?? $t('diag.unknown')} tone={currentItem ? 'info' : 'unknown'} />
      <TelemetryRow label={$t('diag.last_event')} value={$controlPlaneStore.currentTurn?.last_sequence ?? $t('diag.unknown')} tone={$controlPlaneStore.currentTurn?.last_sequence !== undefined ? 'info' : 'unknown'} mono />
      <TelemetryRow label={$t('diag.event_count')} value={$controlPlaneStore.eventCount} tone={$controlPlaneStore.eventCount > 0 ? 'info' : 'unknown'} mono />
    </dl>
  </section>

  <section aria-label={$t('diag.tab_Телеметрия')}>
    <h3>{$t('diag.tab_Телеметрия')}</h3>
    <dl>
      <TelemetryRow label={$t('diag.model_gateway')} value={translateGatewayStatus($modelGatewayStore.status, $t)} tone={$modelGatewayStore.binding ? 'ready' : 'disabled'} />
      <TelemetryRow label={$t('diag.model_called')} value={translateModelCalled($modelGatewayStore.modelCalled, $t)} tone={$modelGatewayStore.modelCalled ? 'ready' : 'disabled'} />
      <TelemetryRow label={$t('diag.tools_executed')} value={$modelGatewayStore.toolsExecuted} tone="disabled" mono />
      <TelemetryRow label={$t('diag.persistence')} value={translatePersistence($modelGatewayStore.persistence, $t)} tone="disabled" />
      <TelemetryRow label={$t('diag.provider')} value={$modelGatewayStore.binding?.provider_id ?? $t('diag.not_configured')} tone={$modelGatewayStore.binding ? 'ready' : 'disabled'} mono />
      <TelemetryRow label={$t('diag.response_mode')} value={$modelGatewayStore.binding?.harness_id ?? $t('diag.not_configured')} tone={$modelGatewayStore.binding ? 'ready' : 'disabled'} mono />
      <TelemetryRow label={$t('diag.autonomous')} value={$t('diag.disabled')} tone="disabled" />
      <TelemetryRow label={$t('diag.confirmation')} value={$t('diag.disabled')} tone="disabled" />
      <TelemetryRow label={$t('diag.result_check')} value={$t('diag.result_not_run')} tone="disabled" />
    </dl>
  </section>

  <section aria-label={$t('diag.tab_События')}>
    <h3>{$t('diag.tab_События')}</h3>
    <EventStream events={$controlPlaneStore.recentEvents} />
  </section>

  <PolicyDecision />

  <section aria-label={$t('diag.tab_Проверка')}>
    <h3>{$t('diag.tab_Проверка')}</h3>
    <dl>
      <TelemetryRow label={$t('diag.status')} value={$t('diag.not_run')} tone="disabled" />
    </dl>
  </section>

  <section aria-label={$t('diag.demo_controls')}>
    <h3>{$t('diag.demo_controls')}</h3>
    <div class="control-row">
      <button
        type="button"
        onclick={() => void startCancellationDemo()}
        disabled={!startEnabled}
        title={startEnabled ? $t('diag.start_demo') : $t('diag.control_plane_not_connected')}
      >
        {$t('diag.start_demo')}
      </button>
      <button type="button" onclick={() => void cancelCurrentDemoTurn()} disabled={!cancelEnabled}>
        {$t('diag.cancel_demo')}
      </button>
    </div>
  </section>

  <footer aria-label={$t('diag.about_versions')}>
    <span>{$t('diag.desktop_shell')} {DESKTOP_SHELL_VERSION}</span>
  </footer>
</aside>

<style>
  .diagnostics {
    width: var(--inspector-width);
    min-width: var(--inspector-width);
    overflow-y: auto;
    border-left: var(--border-thin);
    border-right: 0;
    padding: var(--lc-space-4);
    background: var(--lc-panel);
    backdrop-filter: blur(18px);
  }

  .diagnostics.hidden {
    display: none;
  }

  header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--lc-space-3);
  }

  .eyebrow,
  footer {
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 760;
  }

  h2,
  h3 {
    margin: 0;
  }

  h2 {
    margin-top: var(--lc-space-1);
    font-size: 17px;
  }

  h3 {
    margin: var(--lc-space-5) 0 var(--lc-space-2);
    color: var(--lc-muted);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .close-button {
    display: inline-flex;
    align-items: center;
    gap: var(--lc-space-1);
    min-height: 32px;
    padding: 0 var(--lc-space-2);
    color: var(--lc-muted);
  }

  .close-button:hover {
    color: var(--lc-text);
  }

  .tabs,
  .summary,
  .control-row {
    display: flex;
    flex-wrap: wrap;
    gap: var(--lc-space-2);
  }

  .tabs {
    margin: var(--lc-space-3) 0;
    border-bottom: var(--border-thin);
    padding-bottom: var(--lc-space-2);
  }

  .section-tab,
  .control-row button {
    min-height: 32px;
    padding: 0 var(--lc-space-3);
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 700;
    background: transparent;
    border: none;
  }

  .section-tab:hover {
    color: var(--lc-text);
  }

  .section-tab[aria-selected='true'] {
    color: var(--lc-accent);
    border-bottom: 2px solid var(--lc-accent);
    margin-bottom: -1px;
  }

  dl {
    display: grid;
    gap: var(--lc-space-1);
    margin: 0;
  }

  .control-row button {
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-solid);
  }

  .control-row button:hover:not(:disabled) {
    background: var(--lc-panel-soft);
    border-color: var(--lc-line);
  }

  .control-row button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .summary {
    margin-bottom: var(--lc-space-3);
    padding-bottom: var(--lc-space-3);
    border-bottom: var(--border-thin);
  }

  footer {
    margin-top: var(--lc-space-6);
    border-top: var(--border-thin);
    padding-top: var(--lc-space-4);
  }

  @media (max-width: 1199px) {
    .diagnostics:not(.drawer-open) {
      display: none;
    }

    .diagnostics.drawer-open {
      position: fixed;
      top: 56px;
      right: 0;
      z-index: 40;
      display: block;
      width: min(var(--inspector-width), calc(100vw - var(--rail-width)));
      height: calc(100vh - 56px);
      box-shadow: var(--lc-shadow);
    }
  }

  @media (max-width: 680px) {
    .diagnostics.drawer-open {
      width: 100vw;
      right: 0;
    }
  }
</style>
