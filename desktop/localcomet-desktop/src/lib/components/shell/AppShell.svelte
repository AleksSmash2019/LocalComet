<script lang="ts">
  import { onMount } from 'svelte';
  import '../../../app.css';
  import LocalCometLogo from '$lib/components/common/LocalCometLogo.svelte';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import Diagnostics from '$lib/components/agent/Diagnostics.svelte';
  import ChatHeader from './ChatHeader.svelte';
  import ConversationSidebar from './ConversationSidebar.svelte';
  import NavigationRail from './NavigationRail.svelte';
  import SettingsPanel from './SettingsPanel.svelte';
  import MessageComposer from '$lib/components/chat/MessageComposer.svelte';
  import MessageList from '$lib/components/chat/MessageList.svelte';
  import ModelSetupDrawer from '$lib/components/model/ModelSetupDrawer.svelte';
  import ReviewCenterWorkspace from '$lib/components/review/ReviewCenterWorkspace.svelte';
  import {
    activeWorkspace,
    closeDiagnosticsPanel,
    closeModelSetup,
    closeSettings,
    handleGlobalEscape,
    inspectorDrawerOpen,
    inspectorVisible,
    modelSetupDrawerOpen,
    openSettings,
    settingsPanelOpen,
    sidebarExpanded,
    themeMode
  } from '$lib/stores/shellStore';
  import { controlPlaneStore, initializeControlPlaneBridge, shutdownControlPlaneBridge } from '$lib/stores/controlPlane';
  import { initializeModelGateway, shutdownModelGateway } from '$lib/stores/modelGateway';
  import { initializeKnowledgePreviewEvents, shutdownKnowledgePreviewEvents } from '$lib/stores/knowledgePreview';
  import { locale, t } from '$lib/i18n';
  import type { ResolvedTheme } from '$lib/data/mockData';
  import { DESKTOP_BUILD_LABEL } from '$lib/version';

  let systemDark = false;
  let resolvedTheme: ResolvedTheme = 'light';

  function closeSettingsAndRestoreFocus(): void {
    closeSettings();
    queueMicrotask(() => {
      document.querySelector<HTMLButtonElement>('[data-settings-trigger]')?.focus();
    });
  }

  $: resolvedTheme = $themeMode === 'system' ? (systemDark ? 'dark' : 'light') : $themeMode;

  onMount(() => {
    const media = window.matchMedia?.('(prefers-color-scheme: dark)');
    if (media) {
      systemDark = media.matches;
      const update = (event: MediaQueryListEvent) => {
        systemDark = event.matches;
      };
      media.addEventListener('change', update);
      return () => media.removeEventListener('change', update);
    }
    return undefined;
  });

  onMount(() => {
    const media = window.matchMedia?.('(max-width: 920px)');
    if (!media) return undefined;
    const update = (matches: boolean) => {
      if (matches) sidebarExpanded.set(false);
    };
    update(media.matches);
    const listener = (event: MediaQueryListEvent) => update(event.matches);
    media.addEventListener('change', listener);
    return () => media.removeEventListener('change', listener);
  });

  onMount(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.ctrlKey && !event.altKey && !event.shiftKey && event.key === ',') {
        event.preventDefault();
        openSettings();
        return;
      }
      if (event.key === 'Escape' && $settingsPanelOpen) {
        event.preventDefault();
        closeSettingsAndRestoreFocus();
        return;
      }
      if (handleGlobalEscape(event.key)) {
        event.stopPropagation();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  });

  onMount(() => {
    void initializeControlPlaneBridge();
    void initializeModelGateway();
    void initializeKnowledgePreviewEvents();
    document.documentElement.lang = $locale;
    return () => {
      shutdownModelGateway();
      shutdownKnowledgePreviewEvents();
      shutdownControlPlaneBridge();
    };
  });

  $: controlPlaneLabel =
    $controlPlaneStore.bridgeState === 'READY'
      ? 'Control Plane: Connected'
      : $controlPlaneStore.bridgeState === 'CONNECTING'
        ? 'Control Plane: Starting'
        : $controlPlaneStore.bridgeState === 'UNAVAILABLE'
          ? 'Control Plane: Unavailable'
          : $controlPlaneStore.bridgeState === 'ERROR'
            ? 'Control Plane: Error'
            : 'Control Plane: Unknown';
  $: controlPlaneTone =
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

<div class="app-shell" data-theme={resolvedTheme}>
  <a
    class="skip-link"
    href={$activeWorkspace === 'review' ? '#review-workspace' : '#chat-workspace'}
  >
    {$activeWorkspace === 'review' ? $t('review.skip_link') : $t('common.skip_link')}
  </a>
  <header class="title-bar" aria-label="LocalComet title bar">
    <div class="brand">
      <LocalCometLogo size={26} />
      <span class="wordmark"><span class="wordmark-local">Local</span><span class="wordmark-comet">Comet</span></span>
    </div>
    <StatusBadge label={controlPlaneLabel} tone={controlPlaneTone} />
    <span class="title-version">{DESKTOP_BUILD_LABEL}</span>
  </header>

  <div
    class:review-mode={$activeWorkspace === 'review'}
    class:diagnostics-open={$activeWorkspace === 'chat' && $inspectorVisible}
    class="shell-body"
  >
    <NavigationRail />

    {#if $activeWorkspace === 'chat'}
      <ConversationSidebar />
      <main id="chat-workspace" class="main-workspace" aria-label="LocalComet chat workspace">
        <ChatHeader />
        <div class="chat-scroll">
          <div class="content-column">
            <MessageList />
          </div>
        </div>
        <MessageComposer />
      </main>
      <Diagnostics className={$inspectorDrawerOpen ? 'drawer-open' : ''} onClose={closeDiagnosticsPanel} />
      {#if $modelSetupDrawerOpen}
        <ModelSetupDrawer onClose={closeModelSetup} />
      {/if}
    {:else}
      <ReviewCenterWorkspace />
    {/if}
  </div>

  {#if $settingsPanelOpen}
    <SettingsPanel onClose={closeSettingsAndRestoreFocus} />
  {/if}
</div>

<style>
  .shell-body.review-mode {
    grid-template-columns: var(--rail-width) minmax(0, 1fr);
  }
</style>
