<script lang="ts">
  import type { ToolCallMock } from '$lib/data/mockData';

  export let tool: ToolCallMock;

  $: isWebTool = tool.operation === 'web.search' || tool.operation === 'web.fetch';
  $: isError = tool.status === 'WAITING' && tool.result?.includes('error');
</script>

<article class="tool-card tool-surface" aria-label={isWebTool ? `Web ${tool.status}` : 'Tools disabled'}>
  <div class="tool-head">
    <div>
      <span class="eyebrow">{isWebTool ? `WEB ${tool.operation === 'web.search' ? 'SEARCH' : 'FETCH'}` : 'Tool Runtime'}</span>
      <h2>{tool.operation}</h2>
    </div>
    <span class="status-pill"><span class="status-dot" class:disabled={tool.status === 'SKIPPED'}></span>{tool.status}</span>
  </div>
  {#if isWebTool}
    <div class="web-meta">
      <dt>Source</dt>
      <dd class="mono">{tool.target}</dd>
    </div>
  {:else}
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
  {/if}
  <details>
    <summary>{isWebTool ? 'View result' : 'Details'}</summary>
    <p>{tool.detail}</p>
    {#if isWebTool && tool.result}
      <div class="web-result">
        <pre>{tool.result.slice(0, 4000)}</pre>
        {#if tool.result.length > 4000}
          <span class="truncated-note">Truncated — full result available in context</span>
        {/if}
      </div>
    {:else}
    <pre>{tool.result}</pre>
    {/if}
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

  .web-meta {
    margin: var(--lc-space-3) 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .mono {
    font-family: var(--font-mono);
    font-size: 11px;
    overflow-wrap: anywhere;
    color: var(--lc-text);
  }

  .web-result pre {
    max-height: 320px;
    overflow-y: auto;
  }

  .truncated-note {
    display: block;
    margin-top: 6px;
    color: var(--lc-muted);
    font-size: 11px;
  }

  .status-dot.disabled {
    background: var(--lc-muted);
  }
</style>
