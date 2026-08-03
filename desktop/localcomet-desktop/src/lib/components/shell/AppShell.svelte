<script lang="ts">
  import { onMount, tick } from 'svelte';
  import '../../../app.css';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import CommandPalette from '$lib/components/common/CommandPalette.svelte';
  import Diagnostics from '$lib/components/agent/Diagnostics.svelte';
  import ChatHeader from './ChatHeader.svelte';
  import ConversationSidebar from './ConversationSidebar.svelte';
  import NavigationRail from './NavigationRail.svelte';
  import SettingsPanel from './SettingsPanel.svelte';
  import MessageComposer from '$lib/components/chat/MessageComposer.svelte';
  import MessageList from '$lib/components/chat/MessageList.svelte';
  import ModelSetupDrawer from '$lib/components/model/ModelSetupDrawer.svelte';
  import ReviewCenterWorkspace from '$lib/components/review/ReviewCenterWorkspace.svelte';
  import OnboardingScreen from '$lib/components/onboarding/OnboardingScreen.svelte';
  import {
    activeWorkspace,
    chatMessages,
    closeDiagnosticsPanel,
    closeModelSetup,
    closeSettings,
    handleGlobalEscape,
    inspectorDrawerOpen,
    inspectorVisible,
    modelSetupDrawerOpen,
    openCommandPalette,
    openSettings,
    settingsPanelOpen,
    sidebarExpanded,
    themeMode
  } from '$lib/stores/shellStore';
  import { controlPlaneStore, initializeControlPlaneBridge, shutdownControlPlaneBridge } from '$lib/stores/controlPlane';
  import { initializeModelGateway, shutdownModelGateway } from '$lib/stores/modelGateway';
  import { initializeArtifactAcquisition, resetArtifactAcquisitionStore } from '$lib/stores/artifactAcquisition';
  import { initializeKnowledgePreviewEvents, shutdownKnowledgePreviewEvents } from '$lib/stores/knowledgePreview';
  import { locale, t } from '$lib/i18n';
  import type { ResolvedTheme } from '$lib/data/mockData';
  import { followTranscriptToEnd, isTranscriptNearBottom } from '$lib/components/chat/transcriptScroll';

  let systemDark = false;
  let resolvedTheme: ResolvedTheme = 'light';
  let transcriptViewport: HTMLDivElement;
  let followTranscript = true;
  let transcriptRevision = 0;

  $: document.documentElement.lang = $locale;

  function recordTranscriptPosition(): void {
    if (!transcriptViewport) return;
    followTranscript = isTranscriptNearBottom(transcriptViewport);
  }

  function handleTranscriptKeydown(event: KeyboardEvent): void {
    if (!transcriptViewport) return;
    const page = Math.max(40, Math.floor(transcriptViewport.clientHeight * 0.9));
    if (event.key === 'PageUp') {
      event.preventDefault();
      transcriptViewport.scrollTop = Math.max(0, transcriptViewport.scrollTop - page);
    } else if (event.key === 'PageDown') {
      event.preventDefault();
      transcriptViewport.scrollTop = Math.min(
        transcriptViewport.scrollHeight,
        transcriptViewport.scrollTop + page
      );
    } else if (event.key === 'Home') {
      event.preventDefault();
      transcriptViewport.scrollTop = 0;
    } else if (event.key === 'End') {
      event.preventDefault();
      transcriptViewport.scrollTop = transcriptViewport.scrollHeight;
    } else {
      return;
    }
    recordTranscriptPosition();
  }

  async function revealLatestTranscriptContent(): Promise<void> {
    if (!transcriptViewport || !followTranscript) return;
    await tick();
    if (!transcriptViewport || !followTranscript) return;
    followTranscriptToEnd(transcriptViewport, true);
  }

  function closeSettingsAndRestoreFocus(): void {
    closeSettings();
    queueMicrotask(() => {
      document.querySelector<HTMLButtonElement>('[data-settings-trigger]')?.focus();
    });
  }

  $: resolvedTheme = $themeMode === 'system' ? (systemDark ? 'dark' : 'light') : $themeMode;
  $: transcriptRevision = $chatMessages.reduce(
    (revision, message) => revision + message.body.length + (message.state?.length ?? 0),
    $chatMessages.length
  );
  $: if (transcriptViewport && transcriptRevision >= 0) {
    void revealLatestTranscriptContent();
  }

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
      if ((event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        openCommandPalette();
        return;
      }
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
        event.preventDefault();
        event.stopPropagation();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  });

  onMount(() => {
    void initializeControlPlaneBridge();
    void initializeModelGateway();
    void initializeArtifactAcquisition();
    void initializeKnowledgePreviewEvents();
    document.documentElement.lang = $locale;
    return () => {
      shutdownModelGateway();
      resetArtifactAcquisitionStore();
      shutdownKnowledgePreviewEvents();
      shutdownControlPlaneBridge();
    };
  });

  $: controlPlaneLabel =
    $controlPlaneStore.bridgeState === 'READY'
      ? $t('diag.control_plane_connected')
      : $controlPlaneStore.bridgeState === 'CONNECTING'
        ? $t('diag.control_plane_starting')
        : $controlPlaneStore.bridgeState === 'UNAVAILABLE'
          ? $t('diag.control_plane_unavailable')
          : $controlPlaneStore.bridgeState === 'ERROR'
            ? $t('diag.control_plane_error')
            : $t('diag.control_plane_unknown');
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
    href={$activeWorkspace === 'review' ? '#review-workspace' : $activeWorkspace === 'setup' ? '#setup-workspace' : '#chat-workspace'}
  >
    {$activeWorkspace === 'review' ? $t('review.skip_link') : $activeWorkspace === 'setup' ? $t('onboarding.skip_link') : $t('common.skip_link')}
  </a>
  <NavigationRail />
  <header class="title-bar" aria-label={$t('app.title_bar')}>
    <div class="palette-hint" aria-hidden="true">
      <kbd>Ctrl</kbd><kbd>K</kbd><span>{$t('commandPalette.search')}</span>
    </div>
    <StatusBadge label={controlPlaneLabel} tone={controlPlaneTone} />
  </header>

  <div
    class:focused-mode={$activeWorkspace !== 'chat'}
    class:diagnostics-open={$activeWorkspace === 'chat' && $inspectorVisible}
    class="shell-body"
  >
    {#if $activeWorkspace === 'chat'}
      <ConversationSidebar />
      <main id="chat-workspace" class="main-workspace" aria-label="LocalComet chat workspace">
        <ChatHeader />
        <!-- svelte-ignore a11y_no_noninteractive_tabindex a11y_no_noninteractive_element_interactions (the transcript viewport must receive native scroll keys) -->
        <div
          class="chat-scroll"
          bind:this={transcriptViewport}
          role="region"
          tabindex="0"
          aria-label={$t('chat.message_history')}
          onscroll={recordTranscriptPosition}
          onkeydown={handleTranscriptKeydown}
        >
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
    {:else if $activeWorkspace === 'review'}
      <ReviewCenterWorkspace />
    {:else}
      <OnboardingScreen />
    {/if}
  </div>

  {#if $settingsPanelOpen}
    <SettingsPanel onClose={closeSettingsAndRestoreFocus} />
  {/if}
  <CommandPalette />
</div>

<style>
  .app-shell {
    height: 100dvh;
    max-height: 100dvh;
    overflow: hidden;
  }

  .shell-body {
    min-width: 0;
    min-height: 0;
    overflow: hidden;
  }

  .main-workspace {
    min-width: 0;
    min-height: 0;
    height: 100%;
    grid-template-rows: auto minmax(0, 1fr) auto;
    overflow: hidden;
  }

  .chat-scroll {
    min-width: 0;
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
    overscroll-behavior: contain;
    scrollbar-gutter: stable;
  }

  .content-column {
    min-width: 0;
  }

  .shell-body.focused-mode {
    grid-template-columns: minmax(0, 1fr);
  }
</style>
