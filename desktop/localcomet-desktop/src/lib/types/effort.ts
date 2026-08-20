export type EffortLevel = 'off' | 'low' | 'medium' | 'high';

export const EFFORT_LEVELS: readonly EffortLevel[] = ['off', 'low', 'medium', 'high'];

export function isEffortLevel(value: unknown): value is EffortLevel {
  return typeof value === 'string' && (EFFORT_LEVELS as readonly string[]).includes(value);
}

export function effortBudgetTokens(level: EffortLevel): number {
  switch (level) {
    case 'off': return 0;
    case 'low': return 512;
    case 'medium': return 2048;
    case 'high': return 8192;
  }
}

/**
 * Conservative capability hint. The gateway remains authoritative and will
 * fall back to content-only output when the provider emits no reasoning stream.
 */
export function modelMaySupportThinking(modelId: string): boolean {
  const normalized = modelId.toLowerCase();
  return normalized.includes('qwen3') ||
    normalized.includes('deepseek-r1') ||
    normalized.includes('qwq') ||
    normalized.includes('phi-4-reasoning') ||
    normalized.includes('reasoning');
}
