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
  <div class="header-left">
    <button
      type="button"
      class="icon-button sidebar-toggle"
      aria-label={$t('sidebar.toggle')}
      title={$t('sidebar.toggle')}
      aria-expanded={$sidebarExpanded}
      onclick={() => sidebarExpanded.update((value) => !value)}
    >
      <Icon name="menu" size={16} />
    </button>
    
    <div class="model-status-block">
      <!-- Removed as per user request -->
    </div>
  </div>

  <div class="header-right">
    <!--
      The model connect action moved next to the composer: it belongs where the
      user is blocked from typing, not in the far corner of the header.
      The non-functional "Think" button was removed with it.
    -->
    <button
      type="button"
      class="icon-button"
      aria-label={$t('diag.toggle')}
      title={$t('diag.toggle')}
      aria-expanded={$inspectorVisible || $inspectorDrawerOpen}
      onclick={() => setDiagnosticsPanelOpen(!($inspectorVisible || $inspectorDrawerOpen))}
    >
      <Icon name="inspector" size={16} />
    </button>
  </div>
</header>

<style>
  .chat-header {
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
    background: transparent;
    padding: 12px 24px;
    height: 56px;
  }

  .header-left,
  .header-right {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .sidebar-toggle {
    display: none;
  }

  @media (max-width: 920px) {
    .sidebar-toggle {
      display: grid;
    }
    .chat-header {
      padding-left: 16px;
    }
  }

  .icon-button {
    width: 28px;
    height: 28px;
    min-height: 28px;
    display: grid;
    place-items: center;
    background: transparent;
    border: none;
    color: var(--lc-muted);
    border-radius: 4px;
    cursor: pointer;
  }

  .icon-button:hover {
    background: var(--lc-panel-soft);
    color: var(--lc-text);
  }
</style>
