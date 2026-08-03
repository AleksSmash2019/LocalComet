<script lang="ts">
  import { t } from '$lib/i18n';
  import type { KnowledgePreviewSource } from '$lib/knowledge/knowledgePreview';
  export let source: KnowledgePreviewSource;
  export let expanded = false;
  export let onToggle: () => void;
</script>

<article class="source-card">
  <button type="button" aria-expanded={expanded} onclick={onToggle}>
    <span class="source-title">{source.title}</span>
    <span class="source-id">{source.note_id}</span>
    <span class="chevron" aria-hidden="true">{expanded ? '−' : '+'}</span>
  </button>
  <div class="provenance">
    <span class="path">{source.relative_path}</span>
    <span>{source.knowledge_layer}</span><span>{source.evidence_class}</span><span>{source.authority}</span>
  </div>
  <div class="headings" aria-label={$t('knowledge.selected_sections')}>
    {#each source.selected_sections as section}
      <span>{section.heading}</span>
    {/each}
  </div>
  {#if expanded}
    <div class="sections">
      {#each source.selected_sections as section}
        <section>
          <h4>{section.heading}</h4>
          <span class="lines">{$t('knowledge.lines')} {section.line_start}–{section.line_end}</span>
          <pre>{section.content}</pre>
        </section>
      {/each}
    </div>
  {/if}
</article>

<style>
  .source-card { min-width: 0; border: 1px solid var(--lc-border); border-radius: var(--lc-radius-sm); background: var(--lc-panel-soft); overflow: hidden; }
  button { width: 100%; display: grid; grid-template-columns: minmax(0, 1fr) minmax(90px, auto) 20px; gap: var(--lc-space-2); align-items: center; padding: var(--lc-space-3); border: 0; background: transparent; color: var(--lc-text); text-align: left; cursor: pointer; }
  button:focus-visible { outline: 2px solid var(--lc-accent); outline-offset: -3px; }
  .source-title, .source-id, .path { min-width: 0; overflow-wrap: anywhere; }
  .source-title { font-weight: 760; }
  .source-id, .provenance, .headings, .lines { color: var(--lc-muted); font-family: var(--lc-mono); font-size: .68rem; }
  .chevron { color: var(--lc-accent); font-size: 1.05rem; text-align: center; }
  .provenance, .headings { display: flex; flex-wrap: wrap; gap: 6px 12px; padding: 0 var(--lc-space-3) var(--lc-space-2); }
  .path { flex-basis: 100%; color: var(--lc-text-soft); }
  .headings span { padding: 2px 6px; border: 1px solid var(--lc-border); border-radius: 999px; }
  .sections { display: grid; gap: var(--lc-space-3); padding: var(--lc-space-3); border-top: 1px solid var(--lc-border); }
  section { min-width: 0; }
  h4 { display: inline; margin: 0 var(--lc-space-2) 0 0; color: var(--lc-text); font-size: .8rem; }
  pre { max-width: 100%; margin: var(--lc-space-2) 0 0; white-space: pre-wrap; overflow-wrap: anywhere; color: var(--lc-text-soft); font: .72rem/1.55 var(--lc-mono); }
  @media (max-width: 620px) { button { grid-template-columns: minmax(0, 1fr) 20px; } .source-id { grid-column: 1; grid-row: 2; } .chevron { grid-column: 2; grid-row: 1 / span 2; } }
</style>
