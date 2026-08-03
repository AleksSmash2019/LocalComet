<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import { activeConversation } from '$lib/stores/conversationStore';
  import { approvedManagedModelInstalled, connectSelectedManagedModel, inferenceRequestStore, managedConnectionBusy, managedModelReady, managedRuntimeStore, modelGatewayStore } from '$lib/stores/modelGateway';
  import { sidebarExpanded, openModelSetup, modelSetupDrawerOpen, inspectorVisible, inspectorDrawerOpen, openSettings, setDiagnosticsPanelOpen } from '$lib/stores/shellStore';
  import { t } from '$lib/i18n';

  $: title = (() => {
    const raw = $activeConversation?.title ?? 'new_chat';
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
