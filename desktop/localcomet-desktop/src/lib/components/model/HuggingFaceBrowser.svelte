<script lang="ts">
  import { onMount } from 'svelte';
  import { t } from '$lib/i18n';
  import { managedRuntimeStore } from '$lib/stores/modelGateway';
  import { cancelHfDownload, hfDownloads, startHfDownload } from '$lib/stores/hfDownloads';
  import { listHuggingFaceRepoFiles, searchHuggingFaceModels, listApprovedDownloadableArtifacts } from '$lib/bridge/modelGateway';
  import type { ApprovedDownloadableArtifact, ArtifactDownloadState } from '$lib/types/modelGateway';
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

  let query = $state('');
  let results = $state<HfModel[]>([]);
  let searching = $state(false);
  let searchError = $state<string | null>(null);
  let expandedRepos = $state<Record<string, ExpandedRepo>>({});
  let approvedArtifacts = $state<readonly ApprovedDownloadableArtifact[]>([]);
  let approvedArtifactsLoading = $state(false);
  let approvedArtifactsError = $state<string | null>(null);

  async function loadApprovedArtifacts(): Promise<void> {
    approvedArtifactsLoading = true;
    approvedArtifactsError = null;
    try {
      approvedArtifacts = await listApprovedDownloadableArtifacts();
    } catch (err) {
      approvedArtifactsError = err instanceof Error ? err.message : String(err);
      approvedArtifacts = [];
    } finally {
      approvedArtifactsLoading = false;
    }
  }

  function startApprovedDownload(artifactId: string): void {
    void startHfDownload(`approved::${artifactId}`, 'approved', artifactId);
  }

  function cancelDownload(cellKey: string): void {
    void cancelHfDownload(cellKey);
  }

  async function search(): Promise<void> {
    const trimmed = query.trim();
    if (trimmed.length === 0) return;
    searching = true;
    searchError = null;
    results = [];
    try {
      // Routed through the Rust backend so the webview never opens its own
      // connection to huggingface.co.
      const data = await searchHuggingFaceModels(trimmed);
      results = data.map((item) => ({
        id: item.id,
        downloads: item.downloads,
        tags: [...item.tags],
        lastModified: item.last_modified,
        pipeline_tag: item.pipeline_tag ?? undefined
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
      const files = await listHuggingFaceRepoFiles(modelId);
      const siblings: HfSibling[] = files.map((file) => ({
        rfilename: file.filename,
        size: file.size ?? undefined
      }));
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

  function startDownload(modelId: string, filename: string): void {
    const url = buildDownloadUrl(modelId, filename);
    void startHfDownload(`${modelId}::${filename}`, 'url', url);
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

  function formatDownloadState(state: ArtifactDownloadState | null, percent: number | null): string {
    if (!state) return '';
    const expected = Number(state.expected_bytes ?? 0);
    const received = Number(state.received_bytes ?? 0);
    const displayPercent = percent ?? (expected > 0 ? Math.min(100, Math.max(0, (received / expected) * 100)) : null);
    const stage = stageKey(state.lifecycle);
    if (expected <= 0) {
      const base = formatSize(received);
      return stage ? `${$t(stage)}: ${base}` : base;
    }
    const sizes = `${formatSize(received)} / ${formatSize(expected)} · ${displayPercent !== null ? displayPercent.toFixed(1) : '—'} %`;
    return stage ? `${$t(stage)}: ${sizes}` : sizes;
  }

  function stageKey(lc: ArtifactDownloadState['lifecycle']): string | null {
    switch (lc) {
      case 'awaiting_confirmation':
        return 'hf.stage.awaiting_confirmation';
      case 'checking_disk':
        return 'hf.stage.checking_disk';
      case 'cancelling':
        return 'hf.stage.cancelling';
      case 'verifying_size':
        return 'hf.stage.verifying_size';
      case 'verifying_hash':
        return 'hf.stage.verifying_hash';
      case 'validating_artifact':
        return 'hf.stage.validating_artifact';
      case 'installing':
        return 'hf.stage.installing';
      default:
        return null;
    }
  }

  function isInstalledArtifact(artifactId: string): boolean {
    return $managedRuntimeStore.installedArtifacts.some(
      (a) => a.artifact_id === artifactId && a.installation_status === 'valid'
    );
  }

  onMount(() => {
    void loadApprovedArtifacts();
  });
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

  <section class="hf-approved">
    <div class="hf-approved-header">
      <strong>{$t('hf.approved_title')}</strong>
      <button type="button" class="hf-search-btn" onclick={() => void loadApprovedArtifacts()} disabled={approvedArtifactsLoading}>
        {#if approvedArtifactsLoading}
          {$t('hf.loading')}
        {:else}
          {$t('hf.refresh')}
        {/if}
      </button>
    </div>
    {#if approvedArtifactsError}
      <div class="hf-error">
        <StatusBadge label={$t('hf.error')} tone="danger" />
        <span>{approvedArtifactsError}</span>
      </div>
    {/if}
    {#if approvedArtifacts.length > 0}
      <div class="hf-approved-list">
        {#each approvedArtifacts as item (item.artifact_id)}
          {@const cellKey = `approved::${item.artifact_id}`}
          {@const entry = $hfDownloads[cellKey]}
          {@const active = entry?.phase === 'pending' || entry?.phase === 'running'}
          <div class="hf-approved-item">
            <div class="hf-approved-info">
              <span class="hf-file-name" title={item.artifact_id}>{item.display_name}</span>
              <span class="hf-quant-badge">{item.kind}</span>
              {#if isInstalledArtifact(item.artifact_id) && !active && entry?.phase !== 'completed'}
                <span class="hf-installed-badge" title={$t('hf.installed')}>✓</span>
              {/if}
            </div>
            <div class="hf-download-cell">
              {#if entry?.phase === 'completed'}
                <span class="hf-installed-label">✓ {$t('hf.installed')}</span>
              {:else}
                <button
                  type="button"
                  class="hf-download-btn"
                  disabled={active}
                  onclick={() => void startApprovedDownload(item.artifact_id)}
                >
                  {#if active}
                    {$t('hf.downloading')}
                  {:else if entry?.phase === 'failed' || entry?.phase === 'cancelled'}
                    {$t('hf.retry')}
                  {:else}
                    {$t('hf.download')}
                  {/if}
                </button>
                {#if active}
                  <div class="hf-download-progress">
                    <div class="hf-download-progress-track">
                      <div
                        class="hf-download-progress-fill"
                        style="width: {Math.min(100, Math.max(0, (Number(entry?.state?.received_bytes ?? 0) / Number(entry?.state?.expected_bytes ?? 1)) * 100))}%"
                      ></div>
                    </div>
                    <div class="hf-download-progress-text">{formatDownloadState(entry?.state ?? null, entry?.percent ?? null)}</div>
                  </div>
                  <button
                    type="button"
                    class="hf-cancel-btn"
                    onclick={() => void cancelDownload(cellKey)}
                    title={$t('hf.cancel_title')}
                  >✕</button>
                {/if}
              {/if}
              {#if entry?.phase === 'failed' || entry?.phase === 'cancelled'}
                <div class="hf-download-error">
                  {entry?.error ?? entry?.state?.error_code ?? (entry?.phase === 'cancelled' ? $t('hf.cancelled') : $t('hf.failed'))}
                </div>
              {:else if entry?.error}
                <div class="hf-download-error">{entry.error}</div>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </section>

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
                      {@const cellKey = `${model.id}::${file.rfilename}`}
                      {@const entry = $hfDownloads[cellKey]}
                      {@const active = entry?.phase === 'pending' || entry?.phase === 'running'}
                      <tr>
                        <td class="hf-file-name" title={file.rfilename}>{file.rfilename}</td>
                        <td><span class="hf-quant-badge">{extractQuant(file.rfilename) || '—'}</span></td>
                        <td class="hf-file-size">{formatSize(file.size)}</td>
                        <td>
                          <div class="hf-download-cell">
                            {#if entry?.phase === 'completed'}
                              <span class="hf-installed-label">✓ {$t('hf.installed')}</span>
                            {:else}
                              <button
                                type="button"
                                class="hf-download-btn"
                                disabled={active}
                                onclick={() => void startDownload(model.id, file.rfilename)}
                              >
                                {#if active}
                                  {$t('hf.downloading')}
                                {:else if entry?.phase === 'failed' || entry?.phase === 'cancelled'}
                                  {$t('hf.retry')}
                                {:else}
                                  {$t('hf.download')}
                                {/if}
                              </button>
                              {#if active}
                                <div class="hf-download-progress">
                                  <div class="hf-download-progress-track">
                                    <div
                                      class="hf-download-progress-fill"
                                      style="width: {Math.min(100, Math.max(0, (Number(entry?.state?.received_bytes ?? 0) / Number(entry?.state?.expected_bytes ?? 1)) * 100))}%"
                                    ></div>
                                  </div>
                                  <div class="hf-download-progress-text">{formatDownloadState(entry?.state ?? null, entry?.percent ?? null)}</div>
                                </div>
                                <button
                                  type="button"
                                  class="hf-cancel-btn"
                                  onclick={() => void cancelDownload(cellKey)}
                                  title={$t('hf.cancel_title')}
                                >✕</button>
                              {/if}
                            {/if}
                            {#if entry?.phase === 'failed' || entry?.phase === 'cancelled'}
                              <div class="hf-download-error">
                                {entry?.error ?? entry?.state?.error_code ?? (entry?.phase === 'cancelled' ? $t('hf.cancelled') : $t('hf.failed'))}
                              </div>
                            {:else if entry?.error}
                              <div class="hf-download-error">{entry.error}</div>
                            {/if}
                          </div>
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
    background: color-mix(in srgb, var(--lc-danger) 12%, transparent);
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
    border-bottom: 1px solid var(--lc-line);
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
    background: var(--lc-accent-dim);
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

  .hf-download-cell {
    display: flex;
    flex-direction: column;
    gap: var(--lc-space-2);
    min-width: 220px;
  }

  .hf-download-progress {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .hf-download-progress-track {
    height: 6px;
    border-radius: 999px;
    background: color-mix(in srgb, var(--lc-accent) 15%, transparent);
    overflow: hidden;
  }

  .hf-download-progress-fill {
    height: 100%;
    border-radius: 999px;
    background: var(--lc-accent);
    transition: width 0.2s ease;
  }

  .hf-download-progress-text {
    font-size: 0.7rem;
    color: var(--lc-muted);
    font-variant-numeric: tabular-nums;
  }

  .hf-download-error {
    font-size: 0.7rem;
    color: var(--lc-danger);
    word-break: break-word;
  }

  .hf-cancel-btn {
    align-self: center;
    background: color-mix(in srgb, var(--lc-danger) 15%, transparent);
    color: var(--lc-danger);
    border: 1px solid var(--lc-danger);
    border-radius: 999px;
    width: 20px;
    height: 20px;
    font-size: 11px;
    line-height: 1;
    cursor: pointer;
  }

  .hf-installed-badge {
    color: var(--lc-accent);
    font-weight: 700;
    font-size: 0.86rem;
  }

  .hf-installed-label {
    color: var(--lc-accent);
    font-family: var(--lc-mono);
    font-size: 0.76rem;
    font-weight: 700;
  }
</style>
