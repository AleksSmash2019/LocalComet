<script lang="ts">
  import type { ControlPlaneEvent } from '$lib/types/controlPlane';
  import { t } from '$lib/i18n';

  export let events: readonly ControlPlaneEvent[] = [];

  $: visibleEvents = events.slice(-12).map((event) => ({
    sequence: event.sequence,
    method: event.method,
    kind: event.kind ?? 'none',
    state: event.state || $t('diag.unknown')
  }));
</script>

<section class="event-stream" aria-label={$t('diag.event_stream_label')}>
  <header>
    <h3>{$t('diag.event_stream')}</h3>
    <span>{events.length}</span>
  </header>
  {#if visibleEvents.length === 0}
    <p class="empty">{$t('diag.no_validated_events')}</p>
  {:else}
    <ol>
      {#each visibleEvents as event}
        <li>
          <span class="seq">#{event.sequence}</span>
          <span class="event-method" title={event.method}>{event.method}</span>
          <small title={`${event.kind} / ${event.state}`}>{event.kind} / {event.state}</small>
        </li>
      {/each}
    </ol>
  {/if}
</section>

<style>
  .event-stream {
    display: grid;
    min-width: 0;
    gap: var(--lc-space-2);
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--lc-space-3);
  }

  h3 {
    margin: 0;
    font-size: 13px;
    text-transform: uppercase;
    color: var(--lc-muted);
  }

  header span,
  .seq,
  small {
    font-family: var(--lc-mono);
  }

  header span {
    color: var(--lc-faint);
    font-size: 12px;
  }

  ol {
    display: grid;
    min-width: 0;
    gap: var(--lc-space-2);
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: grid;
    min-width: 0;
    gap: 2px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: rgba(255, 255, 255, 0.015);
    padding: var(--lc-space-2) var(--lc-space-3);
  }

  .seq {
    color: var(--lc-accent);
    font-size: 11px;
    font-weight: 800;
  }

  .event-method,
  small {
    min-width: 0;
    max-width: 100%;
    overflow-wrap: anywhere;
  }

  small,
  .empty {
    color: var(--lc-muted);
    font-size: 12px;
  }

  .empty {
    margin: 0;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    padding: var(--lc-space-3);
    overflow-wrap: anywhere;
  }
</style>
