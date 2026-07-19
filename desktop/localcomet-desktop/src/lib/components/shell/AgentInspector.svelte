<script lang="ts">
  import { DESKTOP_SHELL_VERSION } from '$lib/version';
  import { inspectorMock, inspectorSections } from '$lib/data/mockData';
  import { activeInspectorSection, inspectorVisible, setActiveInspectorSection } from '$lib/stores/shellStore';
  import type { InspectorSection } from '$lib/data/mockData';

  export let className = '';
  export let onClose: () => void = () => undefined;
</script>

<aside class="inspector {className}" class:hidden={!$inspectorVisible && !className} aria-label="Agent Inspector">
  <header>
    <div>
      <span class="eyebrow">Agent Inspector</span>
      <h2>{inspectorMock.status}</h2>
    </div>
    <button type="button" class="plain-button close-button" aria-label="Close Agent Inspector" onclick={onClose}>Close</button>
  </header>

  <div class="tabs" role="tablist" aria-label="Inspector sections">
    {#each inspectorSections as section}
      <button
        type="button"
        class="section-tab"
        role="tab"
        aria-selected={$activeInspectorSection === section}
        onclick={() => setActiveInspectorSection(section as InspectorSection)}
      >
        {section}
      </button>
    {/each}
  </div>

  <section class="overview" aria-label="Agent status overview">
    <dl>
      <div><dt>Status</dt><dd>{inspectorMock.status}</dd></div>
      <div><dt>Autonomy</dt><dd>{inspectorMock.autonomy}</dd></div>
      <div><dt>Risk</dt><dd class="risk">{inspectorMock.risk}</dd></div>
      <div><dt>Actions used</dt><dd>{inspectorMock.actionsUsed}</dd></div>
      <div><dt>Runtime</dt><dd>{inspectorMock.runtime}</dd></div>
      <div><dt>Kill switch</dt><dd>{inspectorMock.killSwitch}</dd></div>
    </dl>
  </section>

  <section aria-label="Plan">
    <h3>Plan</h3>
    <ol>
      {#each inspectorMock.planSteps as step}
        <li>{step}</li>
      {/each}
    </ol>
  </section>

  <section aria-label="Actions">
    <h3>Actions</h3>
    {#each inspectorMock.actions as action}
      <div class="action-row">
        <span>{action.label}</span>
        <strong>{action.state}</strong>
      </div>
    {/each}
  </section>

  <section aria-label="Deferred entries">
    <h3>Reserved</h3>
    <div class="reserved-grid">
      {#each inspectorMock.reserved as item}
        <div class="reserved-item">
          <strong>{item.label}</strong>
          <span>{item.state}</span>
        </div>
      {/each}
    </div>
  </section>

  <footer aria-label="About desktop shell">
    <span>Desktop shell {DESKTOP_SHELL_VERSION}</span>
  </footer>
</aside>

<style>
  .inspector {
    width: var(--inspector-width);
    min-width: var(--inspector-width);
    overflow-y: auto;
    border-left: var(--border-thin);
    border-right: 0;
    padding: var(--space-4);
  }

  .inspector.hidden {
    display: none;
  }

  header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
  }

  .eyebrow,
  dt,
  footer {
    color: var(--color-muted);
    font-size: 12px;
    font-weight: 700;
  }

  h2,
  h3 {
    margin: var(--space-1) 0 0;
  }

  h2 {
    font-size: 18px;
  }

  h3 {
    margin-top: var(--space-5);
    font-size: 14px;
  }

  .close-button {
    padding: 0 var(--space-3);
  }

  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin: var(--space-4) 0;
  }

  .section-tab {
    min-height: 34px;
    padding: 0 var(--space-3);
    color: var(--color-muted);
  }

  .section-tab[aria-selected='true'] {
    background: var(--color-accent-soft);
    color: var(--color-accent);
  }

  dl {
    display: grid;
    gap: var(--space-2);
    margin: 0;
  }

  dl div,
  .action-row,
  .reserved-item {
    display: flex;
    justify-content: space-between;
    gap: var(--space-3);
    border: var(--border-thin);
    border-radius: var(--radius-2);
    background: var(--color-elevated);
    padding: var(--space-3);
  }

  dd {
    margin: 0;
    font-weight: 800;
  }

  .risk {
    color: var(--risk-medium);
  }

  ol {
    margin: var(--space-3) 0 0;
    padding-left: var(--space-5);
  }

  li + li {
    margin-top: var(--space-2);
  }

  .action-row + .action-row {
    margin-top: var(--space-2);
  }

  .action-row strong,
  .reserved-item span {
    color: var(--color-muted);
    font-size: 12px;
  }

  .reserved-grid {
    display: grid;
    gap: var(--space-2);
  }

  footer {
    margin-top: var(--space-6);
    border-top: var(--border-thin);
    padding-top: var(--space-4);
  }
</style>
