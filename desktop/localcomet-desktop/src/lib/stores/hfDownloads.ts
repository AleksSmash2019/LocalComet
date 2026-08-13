import { get, writable } from 'svelte/store';
import {
  cancelArtifactDownload,
  getArtifactDownloadState,
  normalizeGatewayError,
  startApprovedArtifactDownload,
  startArbitraryHuggingFaceDownload
} from '$lib/bridge/modelGateway';
import { refreshManagedArtifactCatalog } from '$lib/stores/artifactAcquisition';
import { refreshManagedRuntimeStatus } from '$lib/stores/modelGateway';
import type { ArtifactDownloadState } from '$lib/types/modelGateway';

export type HfDownloadPhase = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface HfDownloadEntry {
  readonly phase: HfDownloadPhase;
  readonly jobId: string | null;
  readonly state: ArtifactDownloadState | null;
  readonly error: string | null;
  readonly percent: number | null;
}

const POLL_MS = 500;

const timers = new Map<string, ReturnType<typeof setTimeout>>();
const generations = new Map<string, number>();
const requestSequences = new Map<string, number>();
const pendingPolls = new Map<string, { jobId: string; generation: number }>();
let coalesceTimer: ReturnType<typeof setTimeout> | null = null;

export const hfDownloads = writable<Record<string, HfDownloadEntry>>({});

function setEntry(cellKey: string, entry: HfDownloadEntry): void {
  hfDownloads.update((current) => ({ ...current, [cellKey]: entry }));
}

function stopTimer(cellKey: string): void {
  const timer = timers.get(cellKey);
  if (timer !== undefined) {
    clearTimeout(timer);
    timers.delete(cellKey);
  }
  pendingPolls.delete(cellKey);
  releaseCoalesceTimerIfIdle();
}

// coalesceTimer is module-global and gates every future poll: schedulePoll only
// arms a new timer when it is null. If the pending timer is destroyed from the
// outside while it is still armed, the variable stays non-null forever and no
// download is ever polled again -- observed as polling that silently freezes
// after a download is cleared. Once nothing is queued, drop the handle so the
// next schedulePoll can arm a fresh timer.
function releaseCoalesceTimerIfIdle(): void {
  if (pendingPolls.size > 0 || coalesceTimer === null) return;
  clearTimeout(coalesceTimer);
  coalesceTimer = null;
}

function beginGeneration(cellKey: string): number {
  const generation = (generations.get(cellKey) ?? 0) + 1;
  generations.set(cellKey, generation);
  requestSequences.set(cellKey, 0);
  return generation;
}

function nextRequest(cellKey: string): number {
  const sequence = (requestSequences.get(cellKey) ?? 0) + 1;
  requestSequences.set(cellKey, sequence);
  return sequence;
}

function isCurrent(cellKey: string, generation: number, request?: number): boolean {
  return generations.get(cellKey) === generation
    && (request === undefined || requestSequences.get(cellKey) === request);
}

function isTerminal(state: ArtifactDownloadState): boolean {
  return ['cancelled', 'completed', 'failed'].includes(state.lifecycle);
}

function phaseFor(lifecycle: ArtifactDownloadState['lifecycle']): HfDownloadPhase {
  if (lifecycle === 'completed') return 'completed';
  if (lifecycle === 'cancelled') return 'cancelled';
  if (lifecycle === 'failed') return 'failed';
  return 'running';
}

function errorMessage(error: unknown): string {
  return normalizeGatewayError(error).message;
}

function computePercent(state: ArtifactDownloadState | null): number | null {
  if (!state) return null;
  const expected = Number(state.expected_bytes ?? 0);
  const received = Number(state.received_bytes ?? 0);
  if (expected <= 0) return null;
  const raw = typeof state.percent === 'number' ? state.percent : received / expected;
  return Math.min(100, Math.max(0, raw * 100));
}

function schedulePoll(cellKey: string, jobId: string, generation: number): void {
  if (!isCurrent(cellKey, generation)) return;
  stopTimer(cellKey);
  pendingPolls.set(cellKey, { jobId, generation });
  if (!coalesceTimer) {
    coalesceTimer = setTimeout(() => {
      coalesceTimer = null;
      const snapshot = Array.from(pendingPolls.entries());
      pendingPolls.clear();
      void runCoalescedPolls(snapshot);
    }, POLL_MS);
  }
}

async function runCoalescedPolls(snapshot: Array<[string, { jobId: string; generation: number }]>): Promise<void> {
  const tasks = snapshot.map(async ([cellKey, { jobId, generation }]) => {
    if (!isCurrent(cellKey, generation)) return;
    const request = nextRequest(cellKey);
    try {
      const next = await getArtifactDownloadState(jobId);
      if (!isCurrent(cellKey, generation, request)) return;
      await acceptState(cellKey, jobId, generation, next);
    } catch (error) {
      if (!isCurrent(cellKey, generation, request)) return;
      const normalized = normalizeGatewayError(error);
      const current = get(hfDownloads)[cellKey];
      if (!current || current.jobId !== jobId) return;
      if (normalized.code === 'unknown_download_job') {
        stopTimer(cellKey);
        setEntry(cellKey, { ...current, phase: 'failed', error: normalized.message, percent: computePercent(current.state) });
        return;
      }
      setEntry(cellKey, { ...current, error: normalized.message, percent: computePercent(current.state) });
      schedulePoll(cellKey, jobId, generation);
    }
  });

  await Promise.allSettled(tasks);
}

async function refreshAfterCompletion(cellKey: string, generation: number): Promise<void> {
  const results = await Promise.allSettled([
    refreshManagedArtifactCatalog(),
    refreshManagedRuntimeStatus()
  ]);
  if (!isCurrent(cellKey, generation)) return;
  const failure = results.find((result) => result.status === 'rejected');
  if (failure?.status === 'rejected') {
    const current = get(hfDownloads)[cellKey];
    if (current?.phase === 'completed') {
      setEntry(cellKey, { ...current, error: errorMessage(failure.reason), percent: computePercent(current.state) });
    }
  }
}

async function acceptState(
  cellKey: string,
  jobId: string,
  generation: number,
  state: ArtifactDownloadState
): Promise<void> {
  if (!isCurrent(cellKey, generation)) return;
  if (isTerminal(state)) {
    stopTimer(cellKey);
    setEntry(cellKey, {
      phase: phaseFor(state.lifecycle),
      jobId,
      state,
      error: state.lifecycle === 'failed' ? (state.error_code ?? 'download_failed') : null,
      percent: computePercent(state)
    });
    if (state.lifecycle === 'completed') await refreshAfterCompletion(cellKey, generation);
    return;
  }
  setEntry(cellKey, { phase: 'running', jobId, state, error: null, percent: computePercent(state) });
  schedulePoll(cellKey, jobId, generation);
}

async function pollDownload(cellKey: string, jobId: string, generation: number): Promise<void> {
  if (!isCurrent(cellKey, generation)) return;
  const request = nextRequest(cellKey);
  try {
    const next = await getArtifactDownloadState(jobId);
    if (!isCurrent(cellKey, generation, request)) return;
    await acceptState(cellKey, jobId, generation, next);
  } catch (error) {
    if (!isCurrent(cellKey, generation, request)) return;
    const normalized = normalizeGatewayError(error);
    const current = get(hfDownloads)[cellKey];
    if (!current || current.jobId !== jobId) return;
    if (normalized.code === 'unknown_download_job') {
      stopTimer(cellKey);
      setEntry(cellKey, { ...current, phase: 'failed', error: normalized.message, percent: computePercent(current.state) });
      return;
    }
    setEntry(cellKey, { ...current, error: normalized.message });
    schedulePoll(cellKey, jobId, generation);
  }
}

export async function startHfDownload(cellKey: string, kind: 'url' | 'approved', target: string): Promise<void> {
  const existing = get(hfDownloads)[cellKey];
  if (existing && (existing.phase === 'pending' || existing.phase === 'running')) return;
  stopTimer(cellKey);
  const generation = beginGeneration(cellKey);
  const preservedState = existing?.state ?? null;
  const preservedJobId = existing?.jobId ?? null;
  setEntry(cellKey, { phase: 'pending', jobId: preservedJobId, state: preservedState, error: null, percent: computePercent(preservedState) });
  let started: ArtifactDownloadState;
  try {
    started =
      kind === 'url'
        ? await startArbitraryHuggingFaceDownload(target)
        : await startApprovedArtifactDownload(target);
  } catch (error) {
    if (!isCurrent(cellKey, generation)) return;
    setEntry(cellKey, { phase: 'failed', jobId: null, state: null, error: errorMessage(error), percent: null });
    return;
  }
  if (!isCurrent(cellKey, generation)) return;
  await acceptState(cellKey, started.job_id, generation, started);
}

export async function cancelHfDownload(cellKey: string): Promise<void> {
  const current = get(hfDownloads)[cellKey];
  if (!current || current.jobId === null || !current.state || isTerminal(current.state)) return;
  const generation = generations.get(cellKey);
  if (generation === undefined) return;
  const request = nextRequest(cellKey);
  try {
    const next = await cancelArtifactDownload(current.jobId);
    if (!isCurrent(cellKey, generation, request)) return;
    await acceptState(cellKey, current.jobId, generation, next);
  } catch (error) {
    if (!isCurrent(cellKey, generation, request)) return;
    const latest = get(hfDownloads)[cellKey];
    if (latest?.jobId === current.jobId) {
      setEntry(cellKey, { ...latest, error: errorMessage(error), percent: computePercent(latest.state) });
      schedulePoll(cellKey, current.jobId, generation);
    }
  }
}

export function clearHfDownload(cellKey: string): void {
  stopTimer(cellKey);
  generations.delete(cellKey);
  requestSequences.delete(cellKey);
  hfDownloads.update((current) => {
    const copy = { ...current };
    delete copy[cellKey];
    return copy;
  });
}
