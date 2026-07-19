<script lang="ts">
  import { t } from '$lib/i18n';
  import { reviewDiagnostics } from '$lib/stores/reviewCenter';
</script>

<section class="diagnostics review-panel" aria-labelledby="review-diagnostics-title">
  <header>
    <div>
      <p>{$t('review.diagnostics.eyebrow')}</p>
      <h2 id="review-diagnostics-title">{$t('review.diagnostics.title')}</h2>
    </div>
    <span class="connection-state state-{$reviewDiagnostics.sidecarConnectionState.toLowerCase()}">
      {$t(`review.connection.${$reviewDiagnostics.sidecarConnectionState}`)}
    </span>
  </header>

  <dl>
    <div>
      <dt>{$t('review.diagnostics.command_center')}</dt>
      <dd><code>{$reviewDiagnostics.commandCenterVersion}</code></dd>
    </div>
    <div>
      <dt>{$t('review.diagnostics.frontend_contract')}</dt>
      <dd><code>{$reviewDiagnostics.frontendContractVersion}</code></dd>
    </div>
    <div>
      <dt>{$t('review.diagnostics.tauri')}</dt>
      <dd>{$t(`review.connection.${$reviewDiagnostics.tauriBridgeStatus}`)}</dd>
    </div>
    <div>
      <dt>{$t('review.diagnostics.sidecar')}</dt>
      <dd>{$t(`review.connection.${$reviewDiagnostics.sidecarConnectionState}`)}</dd>
    </div>
    <div>
      <dt>{$t('review.diagnostics.python_runtime')}</dt>
      <dd><code>{$reviewDiagnostics.pythonRuntimeContractVersion ?? $t('review.unavailable')}</code></dd>
    </div>
    <div>
      <dt>{$t('review.diagnostics.inbox')}</dt>
      <dd>{$reviewDiagnostics.inboxCount}</dd>
    </div>
    <div>
      <dt>{$t('review.diagnostics.stale')}</dt>
      <dd>{$reviewDiagnostics.staleCount}</dd>
    </div>
    <div>
      <dt>{$t('review.diagnostics.blocked')}</dt>
      <dd>{$reviewDiagnostics.blockedCount}</dd>
    </div>
    <div>
      <dt>{$t('review.diagnostics.decisions')}</dt>
      <dd>{$reviewDiagnostics.sessionDecisionCount}</dd>
    </div>
    <div>
      <dt>{$t('review.diagnostics.last_error')}</dt>
      <dd><code>{$reviewDiagnostics.lastErrorCode ?? $t('review.none')}</code></dd>
    </div>
  </dl>

  <p class="boundary">{$t('review.diagnostics.boundary')}</p>
</section>

<style>
  .review-panel {
    border: var(--border-thin);
    border-radius: var(--lc-radius-lg);
    background: var(--lc-panel);
    padding: var(--lc-space-4);
  }

  header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--lc-space-3);
    margin-bottom: var(--lc-space-3);
  }

  header p {
    margin: 0 0 4px;
    color: var(--lc-accent);
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.11em;
    text-transform: uppercase;
  }

  h2 {
    margin: 0;
    font-size: 16px;
  }

  .connection-state {
    border: var(--border-thin);
    border-radius: 999px;
    padding: 4px 9px;
    font-family: var(--lc-mono);
    font-size: 10px;
    font-weight: 800;
  }

  .state-connected {
    color: var(--lc-accent);
  }

  .state-error,
  .state-unavailable {
    color: var(--lc-danger);
  }

  .state-connecting {
    color: var(--lc-warning);
  }

  dl {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--lc-space-2);
    margin: 0;
  }

  dl > div {
    min-width: 0;
    border-top: var(--border-thin);
    padding-top: var(--lc-space-2);
  }

  dt {
    color: var(--lc-muted);
    font-size: 10px;
    text-transform: uppercase;
  }

  dd {
    margin: 4px 0 0;
    overflow-wrap: anywhere;
    font-size: 12px;
  }

  code {
    font-family: var(--lc-mono);
  }

  .boundary {
    margin: var(--lc-space-3) 0 0;
    color: var(--lc-muted);
    font-size: 11px;
    line-height: 1.5;
  }

  @media (max-width: 760px) {
    dl {
      grid-template-columns: 1fr;
    }
  }
</style>
