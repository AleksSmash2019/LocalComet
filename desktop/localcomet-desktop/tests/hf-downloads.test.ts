import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';
import type { ArtifactDownloadLifecycle, ArtifactDownloadState } from '../src/lib/types/modelGateway';

const bridge = vi.hoisted(() => ({
  cancel: vi.fn(),
  getState: vi.fn(),
  startApproved: vi.fn(),
  startCustom: vi.fn(),
  normalize: vi.fn()
}));
const refresh = vi.hoisted(() => ({
  catalog: vi.fn(),
  runtime: vi.fn()
}));

vi.mock('$lib/bridge/modelGateway', () => ({
  cancelArtifactDownload: bridge.cancel,
  getArtifactDownloadState: bridge.getState,
  normalizeGatewayError: bridge.normalize,
  startApprovedArtifactDownload: bridge.startApproved,
  startArbitraryHuggingFaceDownload: bridge.startCustom
}));

vi.mock('$lib/stores/artifactAcquisition', () => ({
  refreshManagedArtifactCatalog: refresh.catalog
}));

vi.mock('$lib/stores/modelGateway', () => ({
  refreshManagedRuntimeStatus: refresh.runtime
}));

import {
  clearHfDownload,
  hfDownloads,
  startHfDownload
} from '../src/lib/stores/hfDownloads';

const CELL_KEY = 'approved::model-a';
const POLL_INTERVAL_MS = 500;

function state(
  lifecycle: ArtifactDownloadLifecycle,
  overrides: Partial<ArtifactDownloadState> = {}
): ArtifactDownloadState {
  return {
    job_id: 'a'.repeat(64),
    artifact_id: 'model-a',
    lifecycle,
    expected_bytes: 100,
    received_bytes: lifecycle === 'completed' ? 100 : 0,
    percent: lifecycle === 'completed' ? 100 : 0,
    started_utc_ms: 1,
    updated_utc_ms: 1,
    error_code: null,
    ...overrides
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((accept) => {
    resolve = accept;
  });
  return { promise, resolve };
}

async function settle(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
}

describe('HF download polling', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    bridge.cancel.mockReset();
    bridge.getState.mockReset();
    bridge.startApproved.mockReset();
    bridge.startCustom.mockReset();
    bridge.normalize.mockImplementation((error: unknown) => {
      const value = error as { code?: unknown; message?: unknown };
      return {
        code: typeof value?.code === 'string' ? value.code : 'gateway_error',
        message: typeof value?.message === 'string' ? value.message : 'Local model gateway error'
      };
    });
    refresh.catalog.mockReset().mockResolvedValue(undefined);
    refresh.runtime.mockReset().mockResolvedValue(undefined);
    hfDownloads.set({});
  });

  afterEach(() => {
    clearHfDownload(CELL_KEY);
    clearHfDownload(`${CELL_KEY}-second`);
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it('refreshes both managed views when a start call is already completed', async () => {
    bridge.startApproved.mockResolvedValue(state('completed'));

    await startHfDownload(CELL_KEY, 'approved', 'model-a');

    expect(get(hfDownloads)[CELL_KEY]).toMatchObject({ phase: 'completed', jobId: 'a'.repeat(64) });
    expect(refresh.catalog).toHaveBeenCalledTimes(1);
    expect(refresh.runtime).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(1_000);
    expect(bridge.getState).not.toHaveBeenCalled();
  });

  it('waits for each poll before scheduling the next one', async () => {
    const firstPoll = deferred<ArtifactDownloadState>();
    bridge.startApproved.mockResolvedValue(state('downloading'));
    bridge.getState
      .mockReturnValueOnce(firstPoll.promise)
      .mockResolvedValueOnce(state('completed'));

    await startHfDownload(CELL_KEY, 'approved', 'model-a');
    vi.advanceTimersByTime(500);
    await settle();
    expect(bridge.getState).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(1_000);
    expect(bridge.getState).toHaveBeenCalledTimes(1);

    firstPoll.resolve(state('downloading', { received_bytes: 50, percent: 50, updated_utc_ms: 2 }));
    await settle();
    vi.advanceTimersByTime(500);
    await settle();

    expect(bridge.getState).toHaveBeenCalledTimes(2);
    expect(get(hfDownloads)[CELL_KEY]?.phase).toBe('completed');
  });

  it('ignores a late poll from a cleared prior attempt', async () => {
    const firstPoll = deferred<ArtifactDownloadState>();
    bridge.startApproved
      .mockResolvedValueOnce(state('downloading', { job_id: 'a'.repeat(64) }))
      .mockResolvedValueOnce(state('downloading', { job_id: 'b'.repeat(64) }));
    bridge.getState.mockReturnValueOnce(firstPoll.promise);

    await startHfDownload(CELL_KEY, 'approved', 'model-a');
    vi.advanceTimersByTime(500);
    await settle();
    clearHfDownload(CELL_KEY);
    await startHfDownload(CELL_KEY, 'approved', 'model-a');

    firstPoll.resolve(state('failed', { error_code: 'download_failed' }));
    await settle();

    expect(get(hfDownloads)[CELL_KEY]).toMatchObject({ phase: 'running', jobId: 'b'.repeat(64) });
  });

  it('keeps polling other downloads after a pending coalesced timer is destroyed', async () => {
    // schedulePoll only arms a new coalesced timer when the module-global handle
    // is null. If that timer is destroyed while still armed, the handle stayed
    // non-null forever and every later download silently stopped polling. This
    // asserts recovery rather than the leak.
    bridge.startApproved.mockResolvedValue(state('downloading'));
    bridge.getState.mockResolvedValue(state('downloading'));

    await startHfDownload(CELL_KEY, 'approved', 'model-a');
    vi.clearAllTimers();
    clearHfDownload(CELL_KEY);

    await startHfDownload(`${CELL_KEY}-second`, 'approved', 'model-b');
    vi.advanceTimersByTime(POLL_INTERVAL_MS);
    await settle();

    expect(bridge.getState).toHaveBeenCalled();
  });

  it('keeps a transient poll failure visible and retries it', async () => {
    bridge.startApproved.mockResolvedValue(state('downloading'));
    bridge.getState.mockRejectedValue({ code: 'download_transport', message: 'Temporary transport failure' });

    await startHfDownload(CELL_KEY, 'approved', 'model-a');
    vi.advanceTimersByTime(500);
    await settle();

    expect(get(hfDownloads)[CELL_KEY]).toMatchObject({
      phase: 'running',
      error: 'Temporary transport failure'
    });

    bridge.getState.mockRejectedValue({ code: 'download_transport', message: 'Temporary transport failure' });
    vi.advanceTimersByTime(500);
    await settle();

    expect(bridge.getState).toHaveBeenCalledTimes(2);
    expect(get(hfDownloads)[CELL_KEY]).toMatchObject({ phase: 'running', error: 'Temporary transport failure' });
  });
});
