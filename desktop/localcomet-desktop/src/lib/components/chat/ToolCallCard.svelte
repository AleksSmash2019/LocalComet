<script lang="ts">
  import type { ToolCallMock } from '$lib/data/mockData';

  export let tool: ToolCallMock;
</script>

<article class="tool-card tool-surface" aria-label="Tools disabled">
  <div class="tool-head">
    <div>
      <span class="eyebrow">Tool Runtime</span>
      <h2>{tool.operation}</h2>
    </div>
    <span class="status-pill"><span class="status-dot disabled"></span>{tool.status}</span>
  </div>
  <dl>
    <div>
      <dt>Target</dt>
      <dd>{tool.target}</dd>
    </div>
    <div>
      <dt>Elapsed</dt>
      <dd>{tool.elapsed}</dd>
    </div>
  </dl>
  <details>
    <summary>Details</summary>
    <p>{tool.detail}</p>
    <pre>{tool.result}</pre>
  </details>
</article>

<style>
  .tool-card {
    padding: var(--lc-space-4);
  }

  .tool-head {
    display: flex;
    justify-content: space-between;
    gap: var(--lc-space-4);
  }

  .eyebrow,
  dt {
    color: var(--color-muted);
    font-size: 12px;
    font-weight: 700;
  }

  h2 {
    margin: var(--lc-space-1) 0 0;
    font-size: 16px;
  }

  dl {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: var(--lc-space-4);
    margin: var(--lc-space-4) 0;
  }

  dd {
    margin: var(--lc-space-1) 0 0;
    font-family: var(--font-mono);
    overflow-wrap: anywhere;
  }

  summary {
    cursor: pointer;
    color: var(--color-muted);
    font-weight: 700;
  }

  p,
  pre {
    margin: var(--lc-space-3) 0 0;
  }

  pre {
    overflow-x: auto;
    border-radius: var(--lc-radius-sm);
    background: var(--color-code);
    color: var(--color-text);
    padding: var(--lc-space-3);
    font-family: var(--font-mono);
  }
</style>
