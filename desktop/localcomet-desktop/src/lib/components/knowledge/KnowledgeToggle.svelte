<script lang="ts">
  import { t } from '$lib/i18n';
</script>

<div class="knowledge-availability" style="display: none;" role="status" aria-label={$t('knowledge.unavailable')}>
  <div>
    <strong>{$t('knowledge.title')}</strong>
    <span>{$t('knowledge.unavailable')}</span>
  </div>
</div>

<style>
  .knowledge-availability { padding: 0 var(--lc-space-2) var(--lc-space-2); }
  .knowledge-availability div { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--lc-space-2); min-width: 0; }
  strong { color: var(--lc-text); font-size: .82rem; }
  span { color: var(--lc-muted); font-size: .72rem; font-weight: 720; }
</style>
