import type { ApprovedDownloadableArtifact } from '$lib/types/modelGateway';

// Exact user-installed Qwen3-1.7B Q4_K_M artifact. If it is absent, the
// approved catalog fallback below keeps first-run setup deterministic.
export const DEFAULT_BASE_MODEL_ID = 'custom-hf-72962196cbe48a1dc6b432301cb3666a0aad360a53a43139094d52aa62b0f4f6';
export const DEFAULT_APPROVED_FALLBACK_MODEL_ID = 'qwen2.5-1.5b-instruct-q4-k-m';

export function selectDefaultModelArtifact(
  artifacts: readonly ApprovedDownloadableArtifact[],
  installedIds: ReadonlySet<string>
): ApprovedDownloadableArtifact | null {
  const preferred = artifacts.find((artifact) => artifact.artifact_id === DEFAULT_BASE_MODEL_ID);
  if (preferred) return preferred;

  const approvedFallback = artifacts.find((artifact) => artifact.artifact_id === DEFAULT_APPROVED_FALLBACK_MODEL_ID);
  if (approvedFallback && installedIds.has(approvedFallback.artifact_id)) return approvedFallback;

  return artifacts
    .filter((artifact) => installedIds.has(artifact.artifact_id))
    .sort((left, right) => {
      const leftIsVision = /\bvl\b/i.test(left.display_name) ? 1 : 0;
      const rightIsVision = /\bvl\b/i.test(right.display_name) ? 1 : 0;
      return leftIsVision - rightIsVision || right.expected_bytes - left.expected_bytes;
    })[0] ?? null;
}
