import type { ManagedDownloadableArtifact } from '$lib/types/modelGateway';

// Exact user-installed Qwen3-1.7B Q4_K_M artifact. It is the only
// preferred baseline; no legacy lightweight fallback is permitted.
export const DEFAULT_BASE_MODEL_ID = 'custom-hf-72962196cbe48a1dc6b432301cb3666a0aad360a53a43139094d52aa62b0f4f6';

/**
 * Select only the pinned baseline. A missing baseline is an explicit setup
 * failure, never permission to silently choose another installed model.
 */
export function selectDefaultModelArtifact(
  artifacts: readonly ManagedDownloadableArtifact[],
  installedIds: ReadonlySet<string>
): ManagedDownloadableArtifact | null {
  const preferred = artifacts.find((artifact) => artifact.artifact_id === DEFAULT_BASE_MODEL_ID);
  if (!preferred) return null;
  if (preferred.trust_kind === 'user_supplied' && !installedIds.has(preferred.artifact_id)) return null;
  return preferred;
}
