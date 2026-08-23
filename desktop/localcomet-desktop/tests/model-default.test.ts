import { describe, expect, it } from 'vitest';
import {
  DEFAULT_BASE_MODEL_ID,
  selectDefaultModelArtifact
} from '../src/lib/stores/modelDefault';
import type {
  ApprovedDownloadableArtifact,
  CustomDownloadableArtifact,
  ManagedDownloadableArtifact
} from '../src/lib/types/modelGateway';

function approvedModel(artifact_id: string, display_name: string): ApprovedDownloadableArtifact {
  return {
    artifact_id,
    kind: 'model',
    trust_kind: 'approved_catalog',
    display_name,
    source_identity: 'test/catalog',
    expected_bytes: 1,
    license_id: 'Apache-2.0',
    format: 'GGUF',
    quantization: 'Q4_K_M',
    user_confirmation_required: true,
    automatic_download: false
  };
}

function customModel(artifact_id: string): CustomDownloadableArtifact {
  return {
    artifact_id,
    kind: 'model',
    trust_kind: 'user_supplied',
    display_name: 'Qwen3 1.7B',
    source_identity: 'local://test/qwen3',
    expected_bytes: 1,
    expected_sha256: 'a'.repeat(64),
    license_id: null,
    format: 'GGUF',
    quantization: null,
    user_confirmation_required: true,
    automatic_download: false
  };
}

describe('pinned model selection', () => {
  it('selects the exact pinned Qwen3 artifact when it is runtime-visible', () => {
    const pinned = customModel(DEFAULT_BASE_MODEL_ID);
    const legacy = approvedModel('qwen2.5-7b-instruct-q4-k-m', 'Qwen2.5 7B');

    expect(selectDefaultModelArtifact([legacy, pinned], new Set([DEFAULT_BASE_MODEL_ID]))).toBe(pinned);
  });

  it('fails closed instead of selecting an installed legacy model when pinned Qwen3 is absent', () => {
    const legacy = approvedModel('qwen2.5-7b-instruct-q4-k-m', 'Qwen2.5 7B');

    expect(selectDefaultModelArtifact([legacy], new Set([legacy.artifact_id]))).toBeNull();
  });

  it('does not select an uninstalled user-supplied pinned artifact', () => {
    const pinned = customModel(DEFAULT_BASE_MODEL_ID);

    expect(selectDefaultModelArtifact([pinned], new Set())).toBeNull();
  });

  it('allows an approved pinned artifact to proceed to its download step', () => {
    const pinned = approvedModel(DEFAULT_BASE_MODEL_ID, 'Qwen3 1.7B');

    expect(selectDefaultModelArtifact([pinned], new Set())).toBe(pinned);
  });

  it('does not broaden selection to arbitrary artifact kinds', () => {
    const runtime: ManagedDownloadableArtifact = {
      artifact_id: 'llama-cpp-windows-x86-64-cpu-bootstrap',
      kind: 'runtime',
      trust_kind: 'approved_catalog',
      display_name: 'llama.cpp CPU',
      source_identity: 'test/runtime',
      expected_bytes: 1,
      license_id: 'MIT',
      format: 'zip',
      quantization: null,
      user_confirmation_required: true,
      automatic_download: false
    };

    expect(selectDefaultModelArtifact([runtime], new Set([runtime.artifact_id]))).toBeNull();
  });
});
