export type RiskLevel = 'read_only' | 'guarded' | 'dangerous';

export const RISK_LEVELS: readonly RiskLevel[] = ['read_only', 'guarded', 'dangerous'];

export const RISK_TONE: Record<RiskLevel, 'ready' | 'info' | 'waiting' | 'danger' | 'disabled' | 'unknown'> = {
  'read_only': 'ready',
  'guarded': 'waiting',
  'dangerous': 'danger'
};

export const RISK_LABEL_KEY: Record<RiskLevel, string> = {
  'read_only': 'risk.read_only',
  'guarded': 'risk.guarded',
  'dangerous': 'risk.dangerous'
};

export function isRiskLevel(value: unknown): value is RiskLevel {
  return value === 'read_only' || value === 'guarded' || value === 'dangerous';
}
