<script lang="ts">
  import type { ToolCallMock } from '$lib/data/mockData';

  export let tool: ToolCallMock;

  $: isWebTool = tool.operation === 'web.search' || tool.operation === 'web.fetch';
  $: isCU = tool.operation === 'computer_use';
  $: isError = tool.status === 'WAITING' && tool.result?.includes('error');

  function shot(result: string | undefined): string | null {
    if (!result) return null;
    const s = String(result);
    const dataIdx = s.indexOf('data:image');
    if (dataIdx !== -1) {
      const end = s.indexOf('"', dataIdx);
      return end !== -1 ? s.slice(dataIdx, end) : s.slice(dataIdx, dataIdx + 200000);
    }
    const b64Idx = s.indexOf('base64,');
    if (b64Idx !== -1) {
      const b64 = s.slice(b64Idx + 7).split(/[^A-Za-z0-9+/=]/)[0];
      if (b64.length > 200) return `data:image/png;base64,${b64}`;
    }
    const raw = s.trim();
    if (/^[A-Za-z0-9+/=]{500,}$/.test(raw)) return `data:image/png;base64,${raw}`;
    return null;
  }
  $: src = isCU ? shot(tool.result) : null;
</script>

<article class="tool-card tool-surface" aria-label={isCU ? 'Computer Use' : isWebTool ? `Web ${tool.status}` : 'Tools disabled'}>
  <div class="tool-head">
    <div>
      <span class="eyebrow" class:computer-use={isCU}>{isCU ? 'COMPUTER USE' : isWebTool ? `WEB ${tool.operation === 'web.search' ? 'SEARCH' : 'FETCH'}` : 'Tool Runtime'}</span>
      <h2>{tool.operation}</h2>
    </div>
    <span class="status-pill" class:computer-use={isCU}><span class="status-dot" class:computer-use={isCU} class:disabled={tool.status === 'SKIPPED'}></span>{tool.status}</span>
  </div>
  {#if isCU && src}
    <div class="cu-shot"><img class="cu-img" src={src} alt="Computer Use screenshot preview" loading="lazy" /></div>
  {/if}
  {#if isWebTool}
    <div class="web-meta">
      <dt>Source</dt>
      <dd class="mono">{tool.target}</dd>
    </div>
  {:else if !isCU}
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
    <summary>{isWebTool || isCU ? 'View result' : 'Details'}</summary>
    {#if isCU && src}
      <p class="mono">[screenshot — preview above, {tool.result?.length ?? 0} chars]</p>
    {:else}
      <p>{tool.detail}</p>
    {/if}
    {#if isWebTool && tool.result}
      <div class="web-result">
        <pre>{tool.result.slice(0, 4000)}</pre>
        {#if tool.result.length > 4000}
          <span class="truncated-note">Truncated — full result available in context</span>
        {/if}
      </div>
    {:else if !isCU}
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

  .eyebrow.computer-use {
    color: #15803d;
    background: #dcfce7;
    border-radius: 999px;
    padding: 1px 6px;
  }

  .status-dot.computer-use {
    background: #22c55e;
  }

  .status-pill.computer-use {
    background: #bbf7d0;
    border: 1px solid #86efac;
    border-radius: 999px;
  }

  .cu-shot {
    margin: var(--lc-space-3) 0;
  }

  .cu-img {
    max-height: 240px;
    max-width: 100%;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    object-fit: contain;
    display: block;
  }
</style>
