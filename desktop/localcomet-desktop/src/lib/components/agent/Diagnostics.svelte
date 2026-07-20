<script lang="ts">
  import EventStream from '$lib/components/common/EventStream.svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import TelemetryRow from '$lib/components/common/TelemetryRow.svelte';
  import { controlPlaneStore } from '$lib/stores/controlPlane';
  import { modelGatewayStore } from '$lib/stores/modelGateway';
  import { inspectorVisible } from '$lib/stores/shellStore';
  import { t } from '$lib/i18n';

  export let className = '';
  export let onClose: () => void = () => undefined;

  $: sessionShort = shortId($controlPlaneStore.currentSession?.session_id, $t);
  $: threadShort = shortId($controlPlaneStore.currentThread?.thread_id, $t);
  $: turnShort = shortId($controlPlaneStore.currentTurn?.turn_id, $t);
  $: currentItem = $controlPlaneStore.items[$controlPlaneStore.items.length - 1];
  $: turnState = $controlPlaneStore.currentTurn?.state ?? $t('diag.not_started');
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

<aside id="diagnostics-panel" class="diagnostics {className}" class:hidden={!$inspectorVisible && !className} aria-label={$t('diag.title')}>
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
    </dl>
  </section>

  <section aria-label={$t('diag.tab_События')}>
    <h3>{$t('diag.tab_События')}</h3>
    <EventStream events={$controlPlaneStore.recentEvents} />
  </section>

</aside>

<style>
  .diagnostics {
    --telemetry-row-columns: repeat(2, minmax(0, 1fr));
    --telemetry-row-alignment: start;
    --telemetry-label-display: grid;
    width: var(--inspector-width);
    min-width: var(--inspector-width);
    max-width: 100vw;
    overflow-x: hidden;
    overflow-y: auto;
    scrollbar-gutter: stable;
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
    position: sticky;
    top: 0;
    z-index: 2;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--lc-space-3);
    margin-block-start: calc(0px - var(--lc-space-4));
    margin-inline: calc(0px - var(--lc-space-4));
    border-bottom: var(--border-thin);
    padding: var(--lc-space-4);
    background: var(--lc-panel-solid);
  }

  header > div {
    min-width: 0;
  }

  .eyebrow {
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
    overflow-wrap: anywhere;
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
    flex: 0 0 auto;
    align-items: center;
    gap: var(--lc-space-1);
    min-height: 32px;
    padding: 0 var(--lc-space-2);
    color: var(--lc-muted);
  }

  .close-button:hover {
    color: var(--lc-text);
  }

  .summary {
    display: flex;
    flex-wrap: wrap;
    gap: var(--lc-space-2);
  }

  dl {
    display: grid;
    gap: var(--lc-space-1);
    margin: 0;
  }

  .summary {
    margin-bottom: var(--lc-space-3);
    padding-bottom: var(--lc-space-3);
    border-bottom: var(--border-thin);
  }

  .summary :global(.status-badge) {
    max-width: 100%;
    white-space: normal;
    overflow-wrap: anywhere;
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
      min-width: 0;
      max-width: 100vw;
      height: calc(100vh - 56px);
      box-shadow: var(--lc-shadow);
    }
  }

  @media (max-width: 680px) {
    .diagnostics.drawer-open {
      width: 100vw;
      min-width: 0;
      max-width: 100vw;
      right: 0;
    }
  }
</style>
