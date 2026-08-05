<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from '$lib/components/common/Icon.svelte';
  import FilePreviewDialog from '$lib/components/files/FilePreviewDialog.svelte';
  import { locale, t } from '$lib/i18n';
  import {
    addFiles,
    clearFilesError,
    closeFilePreview,
    filesCapabilityAvailable,
    filesStore,
    forgetFile,
    includedFilesTotals,
    initializeFilesCapability,
    openFilePreview,
    setFileIncluded
  } from '$lib/stores/files';

  let previewTrigger: HTMLElement | null = null;

  onMount(() => {
    void initializeFilesCapability();
  });

  function showPreview(fileId: string, trigger: HTMLElement): void {
    previewTrigger = trigger;
    void openFilePreview(fileId);
  }

  function formatAdded(unixMs: number): string {
    return new Intl.DateTimeFormat($locale === 'ru' ? 'ru-RU' : 'en-US', {
      dateStyle: 'short',
      timeStyle: 'short'
    }).format(new Date(unixMs));
  }

  function errorKey(code: string): string {
    const known = new Set([
      'LC_FILE_UNSUPPORTED_TYPE',
      'LC_FILE_TOO_LARGE',
      'LC_FILE_BINARY',
      'LC_FILE_INVALID_UTF8',
      'LC_FILE_MISSING',
      'LC_FILE_CHANGED',
      'LC_FILE_ACCESS_DENIED',
      'LC_FILE_REPARSE_POINT',
      'LC_FILE_CONTEXT_LIMIT',
      'LC_FILE_UNREADABLE',
      'LC_FILE_SELECTION_LIMIT',
      'LC_FILE_PICKER_UNAVAILABLE',
      'LC_FILE_STATE_UNAVAILABLE'
    ]);
    return known.has(code) ? `files.error.${code}` : 'files.error.default';
  }
</script>

{#if $filesStore.files.length > 0 || $filesStore.selecting || $filesStore.lastError}
  <section class="files-panel card-surface" aria-labelledby="files-panel-title" aria-busy={$filesStore.selecting}>
    <header>
      <div>
        <h2 id="files-panel-title">{$t('files.title')}</h2>
      </div>
      <button
        type="button"
        class="add-files"
        disabled={!$filesCapabilityAvailable || $filesStore.selecting}
        aria-label={$t('files.add')}
        title={$t('files.add')}
        onclick={() => void addFiles()}
      >
        <Icon name="attach" size={16} />
      </button>
    </header>

    <ul class="file-list" aria-label={$t('files.selected_list')}>
      {#each $filesStore.files as file (file.file_id)}
        {@const inclusion = $filesStore.lastContextReport?.files.find((entry) => entry.file_id === file.file_id)}
        <li>
          <div class="file-heading">
            <div class="file-name">
              <strong>{file.filename}</strong>
              <span class:ready={file.readable} class="status">{$t(`files.status.${file.status}`)}</span>
            </div>
            <span class="type">{file.media_type} · .{file.extension}</span>
          </div>
          <dl>
            <div><dt>{$t('files.size')}</dt><dd>{file.byte_size.toLocaleString()} {$t('files.bytes')}</dd></div>
            <div><dt>{$t('files.characters')}</dt><dd>{file.character_count.toLocaleString()}</dd></div>
            <div><dt>{$t('files.added')}</dt><dd>{formatAdded(file.added_at_unix_ms)}</dd></div>
            <div class="location"><dt>{$t('files.location')}</dt><dd title={file.display_location}>{file.display_location}</dd></div>
          </dl>
          <div class="file-actions">
            <label>
              <input
                type="checkbox"
                checked={$filesStore.includedIds.includes(file.file_id)}
                disabled={!file.readable}
                onchange={(event) => setFileIncluded(file.file_id, event.currentTarget.checked)}
              />
              <span>{$t('files.include')}</span>
            </label>
            <button
              type="button"
              disabled={!file.readable || $filesStore.previewingId !== null}
              aria-label={`${$t('files.preview')} ${file.filename}`}
              onclick={(event) => showPreview(file.file_id, event.currentTarget)}
            >
              {$filesStore.previewingId === file.file_id ? $t('files.loading_preview') : $t('files.preview')}
            </button>
            <button
              type="button"
              class="forget"
              disabled={$filesStore.forgettingId !== null}
              aria-label={`${$t('files.forget')} ${file.filename}`}
              onclick={() => void forgetFile(file.file_id)}
            >
              {$filesStore.forgettingId === file.file_id ? $t('files.forgetting') : $t('files.forget')}
            </button>
          </div>
          {#if inclusion}
            <p class="inclusion-report" role="status">
              {$t(inclusion.inclusion === 'full' ? 'files.inclusion.full' : 'files.inclusion.excerpt')}
              · {inclusion.included_bytes.toLocaleString()} / {inclusion.original_bytes.toLocaleString()} {$t('files.bytes')}
              · {inclusion.included_characters.toLocaleString()} / {inclusion.original_characters.toLocaleString()} {$t('files.characters')}
            </p>
          {/if}
        </li>
      {/each}
    </ul>

    {#if $filesCapabilityAvailable}
      <footer aria-live="polite">
        <span>{$t('files.context_total')}</span>
        <strong>{$includedFilesTotals.count} · {$includedFilesTotals.bytes.toLocaleString()} {$t('files.bytes')} · {$includedFilesTotals.characters.toLocaleString()} {$t('files.characters')}</strong>
      </footer>
    {/if}

    {#if $filesStore.lastError}
      <div class="file-error" role="alert">
        <span>{$t(errorKey($filesStore.lastError.code))}</span>
        <button type="button" aria-label={$t('files.dismiss_error')} onclick={clearFilesError}>
          <Icon name="cancel" size={14} />
        </button>
      </div>
    {/if}
  </section>
{/if}

{#if $filesStore.preview}
  <FilePreviewDialog preview={$filesStore.preview} triggerElement={previewTrigger} onClose={closeFilePreview} />
{/if}

<style>
  .files-panel {
    display: grid;
    gap: var(--lc-space-3);
    margin-bottom: var(--lc-space-2);
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    padding: var(--lc-space-3);
    background: var(--lc-panel-soft);
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--lc-space-3);
  }

  h2,
  header p,
  .empty {
    margin: 0;
  }

  h2 {
    font-size: 13px;
  }

  header p,
  .empty {
    margin-top: 2px;
    color: var(--lc-muted);
    font-size: 11px;
  }

  button,
  label {
    min-height: 34px;
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    background: var(--lc-panel-solid);
    color: var(--lc-text);
    font-size: 11px;
    font-weight: 740;
  }

  button {
    cursor: pointer;
  }

  button:disabled {
    color: var(--lc-faint);
    cursor: not-allowed;
  }

  .add-files {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--lc-space-1);
    padding: 0 var(--lc-space-3);
    border-color: var(--lc-line-strong);
    color: var(--lc-accent);
  }

  .file-list {
    display: grid;
    gap: var(--lc-space-2);
    max-height: 310px;
    margin: 0;
    overflow-y: auto;
    padding: 0;
    list-style: none;
  }

  .file-list > li {
    min-width: 0;
    display: grid;
    gap: var(--lc-space-2);
    border: var(--border-thin);
    border-radius: var(--lc-radius-sm);
    padding: var(--lc-space-3);
    background: var(--lc-panel-solid);
  }

  .file-heading,
  .file-name,
  .file-actions,
  footer {
    display: flex;
    align-items: center;
  }

  .file-heading {
    min-width: 0;
    justify-content: space-between;
    gap: var(--lc-space-2);
  }

  .file-name {
    min-width: 0;
    gap: var(--lc-space-2);
  }

  .file-name strong {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 12px;
  }

  .status {
    flex: 0 0 auto;
    border-radius: 999px;
    padding: 2px 6px;
    background: color-mix(in srgb, var(--lc-danger) 14%, transparent);
    color: var(--lc-danger);
    font-size: 9px;
    font-weight: 800;
  }

  .status.ready {
    background: var(--lc-accent-dim);
    color: var(--lc-accent);
  }

  .type {
    flex: 0 0 auto;
    color: var(--lc-muted);
    font-size: 10px;
  }

  dl {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, auto)) minmax(120px, 1fr);
    gap: var(--lc-space-2);
    margin: 0;
  }

  dl div {
    min-width: 0;
  }

  dt {
    color: var(--lc-faint);
    font-size: 9px;
    text-transform: uppercase;
  }

  dd {
    min-width: 0;
    margin: 2px 0 0;
    color: var(--lc-muted);
    font-size: 10px;
  }

  .location dd {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-family: var(--lc-mono);
  }

  .file-actions {
    flex-wrap: wrap;
    gap: var(--lc-space-2);
  }

  .file-actions label {
    display: inline-flex;
    align-items: center;
    gap: var(--lc-space-1);
    padding: 0 var(--lc-space-2);
    cursor: pointer;
  }

  .file-actions input {
    accent-color: var(--lc-accent);
  }

  .file-actions button {
    padding: 0 var(--lc-space-2);
  }

  .file-actions .forget {
    color: var(--lc-danger);
  }

  .inclusion-report {
    margin: 0;
    color: var(--lc-accent);
    font-size: 10px;
    font-weight: 720;
  }

  footer {
    flex-wrap: wrap;
    gap: var(--lc-space-1) var(--lc-space-2);
    color: var(--lc-muted);
    font-size: 10px;
  }

  footer strong {
    color: var(--lc-text);
  }

  footer small {
    flex-basis: 100%;
    color: var(--lc-faint);
    font-size: 9px;
  }

  .file-error {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--lc-space-2);
    border: 1px solid color-mix(in srgb, var(--lc-danger) 45%, transparent);
    border-radius: var(--lc-radius-sm);
    padding: var(--lc-space-2);
    color: var(--lc-danger);
    font-size: 11px;
  }

  .file-error button {
    min-width: 30px;
    min-height: 30px;
    display: grid;
    place-items: center;
  }

  @media (max-width: 680px) {
    header,
    .file-heading {
      align-items: stretch;
      flex-direction: column;
    }

    .add-files {
      width: 100%;
    }

    dl {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .location {
      grid-column: 1 / -1;
    }
  }
</style>
