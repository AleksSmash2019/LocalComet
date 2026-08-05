<script lang="ts">
  import { t } from '$lib/i18n';
  import { downloadArbitraryHuggingFaceArtifact } from '$lib/stores/artifactAcquisition';
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';

  interface HfModel {
    id: string;
    downloads: number;
    tags: string[];
    lastModified: string;
    pipeline_tag?: string;
  }

  interface HfSibling {
    rfilename: string;
    size?: number;
  }

  interface ExpandedRepo {
    id: string;
    siblings: HfSibling[];
    loading: boolean;
    error: string | null;
  }

  let query = '';
  let results: HfModel[] = [];
  let searching = false;
  let searchError: string | null = null;
  let expandedRepos: Record<string, ExpandedRepo> = {};
  let downloadingUrls: Record<string, 'pending' | 'started' | 'error'> = {};

  async function search(): Promise<void> {
    const trimmed = query.trim();
    if (trimmed.length === 0) return;
    searching = true;
    searchError = null;
    results = [];
    try {
      const params = new URLSearchParams({
        search: trimmed,
        filter: 'gguf',
        sort: 'downloads',
        direction: '-1',
        limit: '30'
      });
      const response = await fetch(`https://huggingface.co/api/models?${params.toString()}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data: Array<{ modelId?: string; id?: string; downloads?: number; tags?: string[]; lastModified?: string; pipeline_tag?: string }> = await response.json();
      results = data.map((item) => ({
        id: item.modelId ?? item.id ?? '',
        downloads: item.downloads ?? 0,
        tags: item.tags ?? [],
        lastModified: item.lastModified ?? '',
        pipeline_tag: item.pipeline_tag
      }));
    } catch (err) {
      searchError = err instanceof Error ? err.message : String(err);
    } finally {
      searching = false;
    }
  }

  function handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter') void search();
  }

  async function toggleRepo(modelId: string): Promise<void> {
    if (expandedRepos[modelId] && !expandedRepos[modelId].loading) {
      const copy = { ...expandedRepos };
      delete copy[modelId];
      expandedRepos = copy;
      return;
    }
    expandedRepos = {
      ...expandedRepos,
      [modelId]: { id: modelId, siblings: [], loading: true, error: null }
    };
    try {
      const response = await fetch(`https://huggingface.co/api/models/${modelId}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data: { siblings?: Array<{ rfilename?: string; size?: number }> } = await response.json();
      const siblings: HfSibling[] = (data.siblings ?? [])
        .filter((s) => s.rfilename?.endsWith('.gguf'))
        .map((s) => ({ rfilename: s.rfilename ?? '', size: s.size }));
      expandedRepos = {
        ...expandedRepos,
        [modelId]: { id: modelId, siblings, loading: false, error: null }
      };
    } catch (err) {
      expandedRepos = {
        ...expandedRepos,
        [modelId]: { id: modelId, siblings: [], loading: false, error: err instanceof Error ? err.message : String(err) }
      };
    }
  }

  function buildDownloadUrl(modelId: string, filename: string): string {
    return `https://huggingface.co/${modelId}/resolve/main/${filename}`;
  }

  async function startDownload(modelId: string, filename: string): Promise<void> {
    const url = buildDownloadUrl(modelId, filename);
    downloadingUrls = { ...downloadingUrls, [url]: 'pending' };
    try {
      downloadingUrls = { ...downloadingUrls, [url]: 'started' };
      await downloadArbitraryHuggingFaceArtifact(url);
      const copy = { ...downloadingUrls };
      delete copy[url];
      downloadingUrls = copy;
    } catch {
      downloadingUrls = { ...downloadingUrls, [url]: 'error' };
    }
  }

  function formatSize(bytes: number | undefined): string {
    if (bytes === undefined || bytes === 0) return '—';
    if (bytes >= 1_073_741_824) return `${(bytes / 1_073_741_824).toFixed(1)} GB`;
    if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(0)} MB`;
    return `${(bytes / 1_024).toFixed(0)} KB`;
  }

  function formatDownloads(n: number): string {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
    return String(n);
  }

  function extractQuant(filename: string): string {
    const match = filename.match(/[_.-](Q\d[_A-Z0-9]+|F16|F32|BF16|IQ\d[_A-Z0-9]*)/i);
    return match ? match[1].toUpperCase() : '';
  }
</script>

<div class="hf-browser">
  <header class="hf-header">
    <h2>🤗 {$t('hf.title')}</h2>
    <p class="hf-subtitle">{$t('hf.subtitle')}</p>
  </header>

  <div class="hf-search">
    <input
      type="text"
      bind:value={query}
      placeholder={$t('hf.search_placeholder')}
      onkeydown={handleKeydown}
      class="hf-search-input"
    />
    <button type="button" class="hf-search-btn" onclick={() => void search()} disabled={searching || query.trim().length === 0}>
      {#if searching}
        {$t('hf.searching')}
      {:else}
        {$t('hf.search_button')}
      {/if}
    </button>
  </div>

  {#if searchError}
    <div class="hf-error">
      <StatusBadge label={$t('hf.error')} tone="danger" />
      <span>{searchError}</span>
    </div>
  {/if}

  {#if results.length > 0}
    <div class="hf-results">
      {#each results as model (model.id)}
        <div class="hf-card" class:expanded={expandedRepos[model.id]}>
          <button type="button" class="hf-card-header" onclick={() => void toggleRepo(model.id)}>
            <div class="hf-card-info">
              <strong class="hf-model-name">{model.id}</strong>
              <span class="hf-downloads">⬇ {formatDownloads(model.downloads)}</span>
              {#if model.pipeline_tag}
                <span class="hf-tag">{model.pipeline_tag}</span>
              {/if}
            </div>
            <span class="hf-chevron">{expandedRepos[model.id] ? '▲' : '▼'}</span>
          </button>

          {#if expandedRepos[model.id]}
            <div class="hf-files">
              {#if expandedRepos[model.id].loading}
                <div class="hf-files-loading">{$t('hf.loading_files')}</div>
              {:else if expandedRepos[model.id].error}
                <div class="hf-files-error">{expandedRepos[model.id].error}</div>
              {:else if expandedRepos[model.id].siblings.length === 0}
                <div class="hf-files-empty">{$t('hf.no_gguf')}</div>
              {:else}
                <table class="hf-file-table">
                  <thead>
                    <tr>
                      <th>{$t('hf.filename')}</th>
                      <th>{$t('hf.quant')}</th>
                      <th>{$t('hf.size')}</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each expandedRepos[model.id].siblings as file (file.rfilename)}
                      {@const url = buildDownloadUrl(model.id, file.rfilename)}
                      <tr>
                        <td class="hf-file-name" title={file.rfilename}>{file.rfilename}</td>
                        <td><span class="hf-quant-badge">{extractQuant(file.rfilename) || '—'}</span></td>
                        <td class="hf-file-size">{formatSize(file.size)}</td>
                        <td>
                          <button
                            type="button"
                            class="hf-download-btn"
                            disabled={downloadingUrls[url] !== undefined}
                            onclick={() => void startDownload(model.id, file.rfilename)}
                          >
                            {#if downloadingUrls[url] === 'started'}
                              {$t('hf.downloading')}
                            {:else if downloadingUrls[url] === 'error'}
                              {$t('hf.retry')}
                            {:else}
                              {$t('hf.download')}
                            {/if}
                          </button>
                        </td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {:else if !searching && !searchError && query.trim().length > 0}
    <div class="hf-empty">{$t('hf.no_results')}</div>
  {/if}
</div>

<style>
  .hf-browser {
    display: flex;
    flex-direction: column;
    gap: var(--lc-space-4);
    padding: var(--lc-space-5);
    height: 100%;
    overflow-y: auto;
    overflow-x: hidden;
  }

  .hf-header h2 {
    margin: 0;
    font-size: 1.4rem;
    font-weight: 700;
    color: var(--lc-text);
  }

  .hf-subtitle {
    margin: var(--lc-space-1) 0 0;
    font-size: 0.82rem;
    color: var(--lc-muted);
  }

  .hf-search {
    display: flex;
    gap: var(--lc-space-2);
  }

  .hf-search-input {
    flex: 1;
    padding: 10px 14px;
    border: 1px solid var(--lc-line-strong);
    border-radius: var(--lc-radius-md);
    background: var(--lc-panel);
    color: var(--lc-text);
    font-size: 0.9rem;
    outline: none;
    transition: border-color var(--lc-transition-fast);
  }

  .hf-search-input:focus {
    border-color: var(--lc-accent);
    box-shadow: var(--lc-focus-ring);
  }

  .hf-search-input::placeholder {
    color: var(--lc-faint);
  }

  .hf-search-btn {
    padding: 10px 20px;
    border: none;
    border-radius: var(--lc-radius-md);
    background: var(--lc-accent);
    color: var(--lc-bg);
    font-weight: 600;
    font-size: 0.85rem;
    cursor: pointer;
    transition: opacity var(--lc-transition-fast);
    white-space: nowrap;
  }

  .hf-search-btn:hover:not(:disabled) {
    opacity: 0.88;
  }

  .hf-search-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .hf-error {
    display: flex;
    align-items: center;
    gap: var(--lc-space-2);
    padding: var(--lc-space-3);
    border-radius: var(--lc-radius-sm);
    background: rgba(240, 96, 96, 0.1);
    color: var(--lc-danger);
    font-size: 0.82rem;
  }

  .hf-results {
    display: flex;
    flex-direction: column;
    gap: var(--lc-space-2);
  }

  .hf-card {
    border: 1px solid var(--lc-line);
    border-radius: var(--lc-radius-md);
    background: var(--lc-panel);
    overflow: hidden;
    transition: border-color var(--lc-transition-fast);
  }

  .hf-card:hover {
    border-color: var(--lc-line-strong);
  }

  .hf-card.expanded {
    border-color: var(--lc-accent-dim);
  }

  .hf-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: var(--lc-space-3) var(--lc-space-4);
    border: none;
    background: transparent;
    color: var(--lc-text);
    cursor: pointer;
    text-align: left;
  }

  .hf-card-info {
    display: flex;
    align-items: center;
    gap: var(--lc-space-3);
    flex-wrap: wrap;
    min-width: 0;
  }

  .hf-model-name {
    font-size: 0.88rem;
    font-weight: 600;
    word-break: break-all;
  }

  .hf-downloads {
    font-size: 0.74rem;
    color: var(--lc-muted);
    white-space: nowrap;
  }

  .hf-tag {
    font-size: 0.68rem;
    padding: 2px 7px;
    border-radius: var(--lc-radius-sm);
    background: var(--lc-accent-dim);
    color: var(--lc-accent);
    font-weight: 500;
  }

  .hf-chevron {
    font-size: 0.7rem;
    color: var(--lc-faint);
    flex-shrink: 0;
    margin-left: var(--lc-space-2);
  }

  .hf-files {
    border-top: 1px solid var(--lc-line);
    padding: var(--lc-space-3) var(--lc-space-4);
  }

  .hf-files-loading,
  .hf-files-error,
  .hf-files-empty {
    font-size: 0.8rem;
    color: var(--lc-muted);
    padding: var(--lc-space-2) 0;
  }

  .hf-files-error {
    color: var(--lc-danger);
  }

  .hf-file-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8rem;
  }

  .hf-file-table th {
    text-align: left;
    color: var(--lc-faint);
    font-weight: 500;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: var(--lc-space-1) var(--lc-space-2);
    border-bottom: 1px solid var(--lc-line);
  }

  .hf-file-table td {
    padding: var(--lc-space-2);
    border-bottom: 1px solid rgba(36, 52, 44, 0.36);
    vertical-align: middle;
  }

  .hf-file-name {
    color: var(--lc-text);
    font-family: var(--lc-mono);
    font-size: 0.76rem;
    max-width: 360px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .hf-quant-badge {
    display: inline-block;
    padding: 1px 6px;
    border-radius: var(--lc-radius-sm);
    background: rgba(61, 220, 132, 0.08);
    color: var(--lc-accent);
    font-family: var(--lc-mono);
    font-size: 0.72rem;
    font-weight: 600;
  }

  .hf-file-size {
    color: var(--lc-muted);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }

  .hf-download-btn {
    padding: 4px 14px;
    border: 1px solid var(--lc-accent);
    border-radius: var(--lc-radius-sm);
    background: transparent;
    color: var(--lc-accent);
    font-size: 0.76rem;
    font-weight: 600;
    cursor: pointer;
    transition: all var(--lc-transition-fast);
    white-space: nowrap;
  }

  .hf-download-btn:hover:not(:disabled) {
    background: var(--lc-accent);
    color: var(--lc-bg);
  }

  .hf-download-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .hf-empty {
    text-align: center;
    padding: var(--lc-space-6) 0;
    color: var(--lc-faint);
    font-size: 0.86rem;
  }
</style>
