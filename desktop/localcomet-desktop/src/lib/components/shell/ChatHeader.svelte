<script lang="ts">
  import Icon from '$lib/components/common/Icon.svelte';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import { activeConversation } from '$lib/stores/conversationStore';
  import { approvedManagedModelInstalled, connectSelectedManagedModel, gatewayStatus, inferenceBusy, inferenceRequestStore, managedConnectionBusy, managedModelReady, managedRuntimeStore, stopSelectedManagedRuntime } from '$lib/stores/modelGateway';
  import { sidebarExpanded, openModelSetup, modelSetupDrawerOpen, inspectorVisible, inspectorDrawerOpen, openSettings, setDiagnosticsPanelOpen } from '$lib/stores/shellStore';
  import { t } from '$lib/i18n';

  $: title = (() => {
    const raw = $activeConversation?.title ?? 'new_chat';
    const v = $t('item.' + raw);
    return v.startsWith('item.') ? raw : v;
  })();

  // Connection summary for header
  $: connectionSummary = (() => {
    if ($inferenceRequestStore.lifecycle === 'awaiting_approval') return { label: $t('conn.awaiting_approval'), tone: 'waiting' as const };
    if ($inferenceRequestStore.lifecycle === 'awaiting_verification') return { label: $t('conn.awaiting_verification'), tone: 'waiting' as const };
    if (['submitted', 'accepted', 'streaming', 'cancelling'].includes($inferenceRequestStore.lifecycle)) return { label: $t('conn.request_generating'), tone: 'info' as const };
    // The header describes the model connection, not the last turn. Keep a
    // failed request visible in the chat bubble/retry action without leaving a
    // stale red badge after the managed model is still ready.
    if ($managedModelReady) return { label: $t('conn.model_ready'), tone: 'ready' as const };
    if ($inferenceRequestStore.lifecycle === 'failed' || $inferenceRequestStore.lifecycle === 'timed_out' || $gatewayStatus === 'Failed') return { label: $t('conn.request_error'), tone: 'danger' as const };
    if ($managedRuntimeStore.lastError || $managedRuntimeStore.status?.last_error || $managedRuntimeStore.status?.state === 'Failed') return { label: $t('conn.model_unavailable'), tone: 'disabled' as const };
    if ($managedConnectionBusy || ['Validating', 'Starting', 'Stopping'].includes($managedRuntimeStore.status?.state ?? '') || ['Validating', 'Loading', 'Unloading'].includes($managedRuntimeStore.status?.model_state ?? '')) return { label: $t('conn.model_loading'), tone: 'info' as const };
    return { label: $t('conn.model_unavailable'), tone: 'disabled' as const };
  })();
  $: safeModelIdentity = $managedRuntimeStore.status?.model_display_name ?? $managedRuntimeStore.status?.model_id ?? '';

  // Disconnect is reachable where the user sees the model status: the header
  // chip area. It mirrors the Settings action (same store call) so the loaded
  // model can be unloaded without opening Settings.
  $: canDisconnect = !$inferenceBusy && !$managedConnectionBusy
    && ['Ready', 'Starting', 'Validating', 'Failed'].includes($managedRuntimeStore.status?.state ?? '');

  async function disconnectManagedModel(): Promise<void> {
    await stopSelectedManagedRuntime();
  }

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
      <button
        type="button"
        class="model-chip"
        aria-label={$t('chat.header_model_open')}
        title={$t('chat.header_model_open')}
        onclick={() => openModelSetup('managed')}
      >
        <span class="model-chip-name">{safeModelIdentity || $t('chat.model_unavailable')}</span>
        <span class="connection-state" aria-live="polite">
          <StatusBadge label={connectionSummary.label} tone={connectionSummary.tone} />
        </span>
      </button>
      {#if canDisconnect}
        <button
          type="button"
          class="disconnect-button"
          aria-label={$t('models.disconnect')}
          title={$t('models.disconnect')}
          onclick={() => void disconnectManagedModel()}
        >
          <Icon name="power" size={14} />
          <span>{$t('models.disconnect')}</span>
        </button>
      {/if}
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
    background: linear-gradient(
      180deg,
      color-mix(in srgb, var(--lc-bg) 82%, transparent),
      color-mix(in srgb, var(--lc-bg) 62%, transparent)
    );
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    padding: 10px 24px;
    min-height: 56px;
    border-bottom: 1px solid color-mix(in srgb, var(--lc-line) 34%, transparent);
    box-shadow: 0 1px 12px color-mix(in srgb, #000 14%, transparent);
    z-index: 10;
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
    width: 32px;
    height: 32px;
    min-height: 32px;
    display: grid;
    place-items: center;
    background: transparent;
    border: none;
    color: var(--lc-muted);
    border-radius: var(--radius-3);
    cursor: pointer;
    transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease;
  }

  .icon-button:hover {
    background: color-mix(in srgb, var(--lc-panel-soft) 80%, transparent);
    color: var(--lc-text);
    transform: translateY(-1px);
  }

  .model-status-block {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }

  .disconnect-button {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    height: 28px;
    padding: 0 10px;
    border: 1px solid color-mix(in srgb, var(--lc-line) 60%, transparent);
    border-radius: 999px;
    background: transparent;
    color: var(--lc-muted);
    font-size: 11.5px;
    font-weight: 650;
    cursor: pointer;
    transition: all 0.2s ease;
    white-space: nowrap;
  }

  .disconnect-button:hover {
    border-color: color-mix(in srgb, var(--lc-danger) 55%, transparent);
    color: var(--lc-danger);
    background: color-mix(in srgb, var(--lc-danger) 8%, transparent);
  }

  .disconnect-button:focus-visible {
    outline: 2px solid color-mix(in srgb, var(--lc-accent) 70%, transparent);
    outline-offset: 2px;
  }

  .model-chip {
    display: flex;
    align-items: center;
    gap: 8px;
    max-width: 320px;
    min-height: 32px;
    padding: 0 14px;
    border: 1px solid color-mix(in srgb, var(--lc-line) 60%, transparent);
    border-radius: 999px;
    background: color-mix(in srgb, var(--lc-panel-soft) 50%, transparent);
    color: var(--lc-text);
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
    box-shadow: inset 0 1px 2px rgba(255, 255, 255, 0.02);
  }

  .model-chip:hover {
    background: color-mix(in srgb, var(--lc-panel-solid) 90%, transparent);
    border-color: color-mix(in srgb, var(--lc-line) 90%, transparent);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1), inset 0 1px 2px rgba(255, 255, 255, 0.05);
  }

  .connection-state {
    display: inline-flex;
    flex: 0 0 auto;
  }

  .connection-state :global(.status-badge) {
    min-height: 22px;
    padding-inline: 8px;
    font-size: 10.5px;
  }

  .model-chip-name {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: -0.01em;
  }
</style>
