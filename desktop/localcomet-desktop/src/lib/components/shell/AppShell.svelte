<script lang="ts">
    import { onMount, tick } from 'svelte';
  import '../../../app.css';

  import CommandPalette from '$lib/components/common/CommandPalette.svelte';
  import ApprovalModal from './ApprovalModal.svelte';
  import Diagnostics from '$lib/components/agent/Diagnostics.svelte';
  import ChatHeader from './ChatHeader.svelte';
  import AppMenuBar from './AppMenuBar.svelte';
  import ConversationSidebar from './ConversationSidebar.svelte';
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
    themeMode,
    resetShellStores
  } from '$lib/stores/shellStore';
  import { initializeControlPlaneBridge, shutdownControlPlaneBridge } from '$lib/stores/controlPlane';
  import { initializeModelGateway, resetModelGatewayStore, shutdownModelGateway } from '$lib/stores/modelGateway';
  import { initializeArtifactAcquisition, resetArtifactAcquisitionStore } from '$lib/stores/artifactAcquisition';
  import { initializeKnowledgePreviewEvents, shutdownKnowledgePreviewEvents } from '$lib/stores/knowledgePreview';
  import { rejectActiveApproval, resetApprovalStore } from '$lib/stores/approvalStore';
  import { locale, t } from '$lib/i18n';
  import type { ResolvedTheme } from '$lib/data/mockData';
  import { followTranscriptToEnd, isTranscriptNearBottom } from '$lib/components/chat/transcriptScroll';
  import { installModelFitBridge } from '$lib/bridge/modelfit';

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
  $: transcriptRevision =
    $chatMessages.length + ($chatMessages[$chatMessages.length - 1]?.body.length ?? 0);
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

  onMount(() => installModelFitBridge());

  onMount(() => {
    // A mounted frontend is a new UI session. Never inherit an approval prompt
    // or an in-flight local lifecycle from a previous WebView/remount.
    void rejectActiveApproval();
    resetShellStores();
    resetApprovalStore();
    resetModelGatewayStore();
    void initializeControlPlaneBridge();

    void initializeModelGateway();
    void initializeArtifactAcquisition();
    void initializeKnowledgePreviewEvents();
    document.documentElement.lang = $locale;
    return () => {
      void rejectActiveApproval();
      shutdownModelGateway();
      resetModelGatewayStore();
      resetApprovalStore();
      resetArtifactAcquisitionStore();
      shutdownKnowledgePreviewEvents();
      shutdownControlPlaneBridge();
    };
  });

</script>

<div class="app-shell" data-theme={resolvedTheme}>
  <AppMenuBar />

  <ConversationSidebar />

  <div
    class:focused-mode={$activeWorkspace !== 'chat'}
    class:diagnostics-open={$activeWorkspace === 'chat' && $inspectorVisible}
    class="shell-body"
  >
    {#if $activeWorkspace === 'chat'}
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
      {#if $inspectorVisible || $inspectorDrawerOpen}
        <Diagnostics className={$inspectorDrawerOpen ? 'drawer-open' : ''} onClose={closeDiagnosticsPanel} />
      {/if}
      {#if $modelSetupDrawerOpen}
        <ModelSetupDrawer onClose={closeModelSetup} />
      {/if}
    {:else if $activeWorkspace === 'review'}
      <ReviewCenterWorkspace />
    {:else if $activeWorkspace === 'hf_browser'}
      {#await import('$lib/components/model/HuggingFaceBrowser.svelte') then mod}
        <svelte:component this={mod.default} />
      {:catch error}
        <p class="hf-lazy-error">{error?.message ?? 'Failed to load'}</p>
      {/await}
    {:else if $activeWorkspace === 'modelfit'}
      <iframe src="/modelfit.html" title={$t('modelfit.title')} class="modelfit-frame"></iframe>
    {:else}
      <OnboardingScreen />
    {/if}
  </div>

  <ApprovalModal />

  {#if $settingsPanelOpen}
    <SettingsPanel onClose={closeSettingsAndRestoreFocus} />
  {/if}
  <CommandPalette />
</div>

<style>
  .app-shell {
    position: relative;
    height: 100dvh;
    max-height: 100dvh;
    overflow: hidden;
    background:
      radial-gradient(ellipse 84% 66% at 2% -22%, color-mix(in srgb, var(--lc-accent) 13%, transparent), transparent 64%),
      radial-gradient(ellipse 70% 58% at 104% 116%, color-mix(in srgb, var(--lc-accent) 10%, transparent), transparent 66%),
      radial-gradient(ellipse 52% 48% at 52% 48%, color-mix(in srgb, var(--lc-accent) 4%, transparent), transparent 78%),
      linear-gradient(140deg, color-mix(in srgb, var(--lc-bg) 92%, #052e24) 0%, color-mix(in srgb, var(--lc-bg) 98%, #0b1814) 48%, color-mix(in srgb, var(--lc-bg) 94%, #062e21) 100%);
    box-shadow: inset 0 0 156px color-mix(in srgb, #000 48%, transparent);
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
    background: transparent;
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
    display: flex;
    flex-direction: column;
  }

  .hf-lazy-error {
    padding: var(--lc-space-4);
    color: var(--lc-danger);
    font-size: 12px;
  }

  .modelfit-frame {
    width: 100%;
    height: 100%;
    border: none;
    display: block;
  }
</style>
