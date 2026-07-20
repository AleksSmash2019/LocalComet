export const TRANSCRIPT_BOTTOM_THRESHOLD_PX = 96;

export interface TranscriptScrollMetrics {
  scrollTop: number;
  scrollHeight: number;
  clientHeight: number;
}

export interface TranscriptScrollTarget extends TranscriptScrollMetrics {
  scrollTop: number;
}

export function transcriptDistanceFromBottom(metrics: TranscriptScrollMetrics): number {
  const { scrollTop, scrollHeight, clientHeight } = metrics;
  if (![scrollTop, scrollHeight, clientHeight].every(Number.isFinite)) return Number.POSITIVE_INFINITY;
  if (scrollHeight < 0 || clientHeight < 0) return Number.POSITIVE_INFINITY;
  return Math.max(0, scrollHeight - clientHeight - Math.max(0, scrollTop));
}

export function isTranscriptNearBottom(
  metrics: TranscriptScrollMetrics,
  threshold = TRANSCRIPT_BOTTOM_THRESHOLD_PX
): boolean {
  if (!Number.isFinite(threshold) || threshold < 0) return false;
  return transcriptDistanceFromBottom(metrics) <= threshold;
}

export function followTranscriptToEnd(target: TranscriptScrollTarget, following: boolean): boolean {
  if (!following) return false;
  target.scrollTop = target.scrollHeight;
  return true;
}
