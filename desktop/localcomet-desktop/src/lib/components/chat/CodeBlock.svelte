<script lang="ts">
  import type { CodeBlockMock } from '$lib/data/mockData';

  export let block: CodeBlockMock;
  
  let copied = false;
  let copyTimeout: ReturnType<typeof setTimeout>;
  
  async function copyCode() {
    try {
      await navigator.clipboard.writeText(block.code);
      copied = true;
      clearTimeout(copyTimeout);
      copyTimeout = setTimeout(() => {
        copied = false;
      }, 2000);
    } catch (err) {
      console.error('Failed to copy code', err);
    }
  }
</script>

<figure class="code-block" aria-label="Code block">
  <figcaption>
    <span>{block.filename}</span>
    <div>
      <span>{block.language}</span>
      <button type="button" aria-label="Copy code" onclick={copyCode}>{copied ? 'Copied!' : 'Copy'}</button>
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
    cursor: pointer;
    padding: 0 var(--lc-space-2);
  }
  
  button:hover {
    background: var(--color-surface);
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
