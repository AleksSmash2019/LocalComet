export type ComputeMode = 'gpu' | 'hybrid' | 'cpu';

export const COMPUTE_MODES: readonly ComputeMode[] = ['gpu', 'hybrid', 'cpu'];

export interface ComputeModeProfile {
  readonly ctxSizeOverride: number | null;
  readonly gpuLayersOverride: number | null;
  readonly runtimeVariant: 'vulkan' | 'cpu';
}

const PROFILES: Readonly<Record<ComputeMode, ComputeModeProfile>> = Object.freeze({
  gpu: Object.freeze({
    ctxSizeOverride: null,
    gpuLayersOverride: null,
    runtimeVariant: 'vulkan'
  }),
  hybrid: Object.freeze({
    ctxSizeOverride: 2048,
    gpuLayersOverride: 8,
    runtimeVariant: 'vulkan'
  }),
  cpu: Object.freeze({
    ctxSizeOverride: 2048,
    gpuLayersOverride: 0,
    runtimeVariant: 'cpu'
  })
});

export function isComputeMode(value: unknown): value is ComputeMode {
  return typeof value === 'string' && (COMPUTE_MODES as readonly string[]).includes(value);
}

export function computeModeProfile(mode: ComputeMode): ComputeModeProfile {
  return PROFILES[mode];
}
