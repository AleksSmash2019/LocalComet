<script lang="ts">
  import { t } from '$lib/i18n';
</script>

<div class="knowledge-availability" role="status" aria-label={$t('knowledge.unavailable')}>
  <div>
    <strong>{$t('knowledge.title')}</strong>
    <span>{$t('knowledge.unavailable')}</span>
    <p>{$t('knowledge.unavailable_detail')}</p>
  </div>
</div>

<style>
  .knowledge-availability { padding: 0 var(--lc-space-2) var(--lc-space-2); }
  .knowledge-availability div { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--lc-space-2); min-width: 0; }
  strong { color: var(--lc-text); font-size: .82rem; }
  span { color: var(--lc-muted); font-size: .72rem; font-weight: 720; }
  p { flex-basis: 100%; margin: 0; color: var(--lc-faint); font-size: .7rem; line-height: 1.4; }
</style>
