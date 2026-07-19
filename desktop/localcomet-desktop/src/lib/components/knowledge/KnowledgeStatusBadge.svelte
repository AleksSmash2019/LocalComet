<script lang="ts">
  import { t } from '$lib/i18n';
  import type { KnowledgeUiState } from '$lib/knowledge/knowledgePreview';
  export let state: KnowledgeUiState;
  $: tone = ['FAILED', 'STALE'].includes(state) ? 'danger' : ['PREVIEW_READY', 'INJECTED'].includes(state) ? 'ready' : 'neutral';
</script>

<span class:danger={tone === 'danger'} class:ready={tone === 'ready'}>{$t(`knowledge.state_${state.toLowerCase()}`)}</span>

<style>
  span { display: inline-flex; align-items: center; min-height: 24px; padding: 2px 8px; border: 1px solid var(--lc-border); border-radius: 999px; color: var(--lc-muted); font-size: .7rem; font-weight: 760; letter-spacing: .03em; }
  span.ready { border-color: rgb(120 255 152 / 52%); color: #78ff98; }
  span.danger { border-color: rgb(255 112 112 / 52%); color: #ff9292; }
</style>
