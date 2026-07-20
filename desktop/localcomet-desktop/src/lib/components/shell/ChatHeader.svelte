<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import { conversationTitleById } from '$lib/data/mockData';
  import { controlPlaneStore } from '$lib/stores/controlPlane';
  import { approvedManagedModelInstalled, inferenceRequestStore, managedModelReady, managedRuntimeStore, modelGatewayStore } from '$lib/stores/modelGateway';
  import { selectedConversationId, sidebarExpanded, openModelSetup, modelSetupDrawerOpen, inspectorVisible, inspectorDrawerOpen, setDiagnosticsPanelOpen } from '$lib/stores/shellStore';
  import { t } from '$lib/i18n';

  $: title = (() => {
    const raw = conversationTitleById($selectedConversationId);
    const v = $t('item.' + raw);
    return v.startsWith('item.') ? raw : v;
  })();

  // Connection summary for header
  $: connectionSummary = (() => {
    if (['submitted', 'accepted', 'streaming', 'cancelling'].includes($inferenceRequestStore.lifecycle)) return { label: $t('conn.generating'), tone: 'info' as const };
    if ($inferenceRequestStore.lifecycle === 'failed' || $inferenceRequestStore.lifecycle === 'timed_out' || $modelGatewayStore.status === 'Failed') return { label: $t('conn.error'), tone: 'danger' as const };
    if ($managedModelReady) return { label: $t('conn.ready'), tone: 'ready' as const };
    if (['Validating', 'Starting'].includes($managedRuntimeStore.status?.state ?? '') || ['Validating', 'Loading'].includes($managedRuntimeStore.status?.model_state ?? '')) return { label: $t('conn.connecting'), tone: 'info' as const };
    return { label: $t('conn.not_connected'), tone: 'disabled' as const };
  })();

  $: bridgeLabel =
    $controlPlaneStore.bridgeState === 'READY'
      ? 'Control Plane: Connected'
      : $controlPlaneStore.bridgeState === 'CONNECTING'
        ? 'Control Plane: Starting'
        : $controlPlaneStore.bridgeState === 'UNAVAILABLE'
          ? 'Control Plane: Unavailable'
          : $controlPlaneStore.bridgeState === 'ERROR'
            ? 'Control Plane: Error'
            : 'Control Plane: Unknown';
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
</script>

<header class="chat-header">
  <button
    type="button"
    class="icon-button sidebar-toggle"
    aria-label="Toggle session sidebar"
    aria-expanded={$sidebarExpanded}
    onclick={() => sidebarExpanded.update((value) => !value)}
  >
    <Icon name="menu" />
  </button>

  <div class="title-block">
    <h1>{title}</h1>
  </div>

  <div class="connection-summary" aria-label="Connection status">
    <StatusBadge label={connectionSummary.label} tone={connectionSummary.tone} />
  </div>

  <div class="header-actions">
    {#if !$managedModelReady}
      <button
        type="button"
        class="primary-button"
        onclick={() => openModelSetup($approvedManagedModelInstalled ? 'managed' : 'external')}
        aria-expanded={$modelSetupDrawerOpen}
        aria-controls="model-setup-drawer"
      >
        <Icon name="link" size={16} />
        <span>{$t('chat.connect_model')}</span>
      </button>
    {:else}
      <StatusBadge label={$t('conn.model_connected')} tone="ready" />
    {/if}

    <button
      type="button"
      class="icon-button"
      aria-label="Toggle Diagnostics"
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
    min-height: 56px;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto auto;
    align-items: center;
    gap: var(--lc-space-2);
    border-bottom: var(--border-thin);
    background: var(--lc-bg-elevated);
    padding: var(--lc-space-2) var(--lc-space-4);
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
  }

  .icon-button:hover {
    background: var(--lc-panel-soft);
    border-color: var(--lc-line);
    color: var(--lc-text);
  }

  .sidebar-toggle {
    display: grid;
  }

  .title-block {
    min-width: 0;
  }

  h1 {
    margin: 0;
    overflow-wrap: anywhere;
    font-size: 16px;
    font-weight: 700;
    color: var(--lc-text);
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

  .primary-button {
    display: inline-flex;
    align-items: center;
    gap: var(--lc-space-2);
    min-height: 36px;
    padding: 0 var(--lc-space-4);
    border: none;
    border-radius: var(--lc-radius-sm);
    background: var(--lc-accent);
    color: var(--lc-logo-cut);
    font-weight: 800;
    font-size: 13px;
    cursor: pointer;
  }

  .primary-button:hover {
    background: var(--lc-accent-strong);
  }

  .primary-button:focus-visible {
    outline: none;
    box-shadow: var(--focus-ring);
  }

  @media (max-width: 680px) {
    .chat-header {
      grid-template-columns: auto minmax(0, 1fr) auto;
      min-height: 48px;
      padding-inline: var(--lc-space-3);
    }

    .primary-button span {
      display: none;
    }

    .primary-button {
      padding: 0 var(--lc-space-2);
    }
  }
</style>
