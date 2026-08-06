<script lang="ts">
  /**
   * Shared frame for the review workspace panels.
   *
   * Five panels repeated the same section > header > eyebrow + h2 markup and
   * the same four CSS rules, so a change to the panel chrome had to be made in
   * five places. The accessibility contract is unchanged: each panel still
   * owns a unique heading id and points aria-labelledby at it.
   *
   * `headingId` must stay unique per panel because aria-labelledby resolves
   * document-wide.
   */
  import { t } from '$lib/i18n';

  export let headingId: string;
  export let eyebrowKey: string;
  export let titleKey: string;
</script>

<section class="review-panel" aria-labelledby={headingId}>
  <header class="panel-header">
    <div>
      <p class="panel-eyebrow">{$t(eyebrowKey)}</p>
      <h2 id={headingId}>{$t(titleKey)}</h2>
    </div>
    <slot name="header-aside" />
  </header>

  <slot />
</section>

<style>
  .review-panel {
    border: var(--border-thin);
    border-radius: var(--lc-radius-lg);
    background: var(--lc-panel);
    padding: var(--lc-space-4);
  }

  .panel-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--lc-space-3);
    margin-bottom: var(--lc-space-3);
  }

  .panel-eyebrow {
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

  @media (max-width: 900px) {
    .panel-header {
      flex-direction: column;
    }
  }
</style>
