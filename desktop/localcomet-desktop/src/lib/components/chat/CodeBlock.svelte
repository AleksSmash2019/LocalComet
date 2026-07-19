<script lang="ts">
  import type { CodeBlockMock } from '$lib/data/mockData';

  export let block: CodeBlockMock;
</script>

<figure class="code-block" aria-label="Disabled runtime capability summary">
  <figcaption>
    <span>{block.filename}</span>
    <div>
      <span>{block.language}</span>
      <button type="button" disabled aria-label="Copy disabled in this release">Copy</button>
    </div>
  </figcaption>
  <pre><code>{block.code}</code></pre>
</figure>

<style>
  .code-block {
    margin: 0;
    border: var(--border-thin);
    border-radius: var(--lc-radius-md);
    overflow: hidden;
    background: var(--color-code);
  }

  figcaption {
    min-height: 44px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--lc-space-4);
    border-bottom: var(--border-thin);
    padding: 0 var(--lc-space-4);
    color: var(--color-muted);
    font-family: var(--font-mono);
    font-size: 12px;
  }

  figcaption div {
    display: flex;
    align-items: center;
    gap: var(--lc-space-3);
  }

  button {
    min-height: 32px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--color-panel);
    color: var(--color-muted);
    cursor: not-allowed;
  }

  pre {
    margin: 0;
    overflow-x: auto;
    padding: var(--lc-space-4);
    color: var(--color-text);
    font-family: var(--font-mono);
    font-size: 13px;
    line-height: 1.6;
  }
</style>
