import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  MAX_KNOWLEDGE_REVIEW_LIST_LIMIT,
  createKnowledgeReviewDecision,
  getKnowledgeReview,
  getKnowledgeReviewSnapshot,
  listKnowledgeReviews,
  refreshKnowledgeReviews,
  reviewProjectionToCenterItem
} from '../src/lib/bridge/knowledgeReview';
import type {
  BoundedTextPreviewProjection,
  KnowledgeChangeReviewProjection,
  KnowledgeReviewDecisionCreateEnvelope,
  KnowledgeReviewDecisionRequest,
  KnowledgeReviewGetEnvelope,
  KnowledgeReviewListEnvelope,
  KnowledgeReviewSnapshotEnvelope,
  KnowledgeReviewSummaryProjection
} from '../src/lib/types/knowledgeReview';

const REVIEW_ID = `kreview:${'a'.repeat(64)}`;
const PROPOSAL_ID = `kprop:${'b'.repeat(64)}`;
const CHANGE_ID = `kchange:${'c'.repeat(64)}`;
const SHA_D = `sha256:${'d'.repeat(64)}`;
const SHA_E = `sha256:${'e'.repeat(64)}`;
const SHA_F = `sha256:${'f'.repeat(64)}`;
const bridgeMock = vi.hoisted(() => ({
  response: null as unknown,
  calls: [] as Array<{ command: string; args: Record<string, unknown> }>
}));

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(async (command: string, args: Record<string, unknown>): Promise<unknown> => {
    bridgeMock.calls.push({ command, args });
    return bridgeMock.response;
  })
}));

function lineCount(value: string): number {
  return value.length === 0 ? 0 : value.split(/\r\n|\r|\n/).length;
}

function text(value: string, truncated = false): BoundedTextPreviewProjection {
  const bytes = new TextEncoder().encode(value).length;
  const lines = lineCount(value);
  return {
    preview_text: value,
    is_preview: true,
    truncated,
    original_utf8_bytes: truncated ? bytes + 10 : bytes,
    original_line_count: truncated ? lines + 1 : lines,
    preview_utf8_bytes: bytes,
    preview_line_count: lines
  };
}

function summary(
  patch: Partial<KnowledgeReviewSummaryProjection> = {}
): KnowledgeReviewSummaryProjection {
  return {
    projection_contract: 'localcomet.knowledge-review-ui/1.0',
    kind: 'KNOWLEDGE_CHANGE_REVIEW_SUMMARY',
    contract_version: 'localcomet.knowledge-change-review/1.0',
    status: 'REVIEW_REQUIRED',
    blocked: false,
    proposal_id: PROPOSAL_ID,
    target_stable_id: 'architecture.review-center',
    operation: 'UPDATE_EXISTING',
    expected_vault_revision: SHA_D,
    observed_vault_revision: SHA_E,
    review_artifact_identity: REVIEW_ID,
    change_identity: CHANGE_ID,
    finding_count: 1,
    normal_change_material_present: true,
    detail_projection_truncated: false,
    ...patch
  };
}

function listEnvelope(
  items: readonly KnowledgeReviewSummaryProjection[] = [summary()],
  patch: Partial<KnowledgeReviewListEnvelope> = {}
): KnowledgeReviewListEnvelope {
  return {
    contract: 'localcomet.knowledge-review-list/1.0',
    source: 'LOCAL_CONTROL_PLANE',
    fixture: false,
    offset: 0,
    limit: 50,
    total_count: items.length,
    returned_count: items.length,
    truncated: false,
    next_offset: null,
    items,
    ...patch
  };
}

function projection(
  patch: Partial<KnowledgeChangeReviewProjection> = {}
): KnowledgeChangeReviewProjection {
  const body = 'Review Center body.\n';
  return {
    projection_contract: 'localcomet.knowledge-review-ui/1.0',
    kind: 'KNOWLEDGE_CHANGE_REVIEW',
    contract_version: 'localcomet.knowledge-change-review/1.0',
    status: 'REVIEW_REQUIRED',
    proposal_id: PROPOSAL_ID,
    proposal_content_hash: SHA_D,
    operation: 'UPDATE_EXISTING',
    target_stable_id: 'architecture.review-center',
    expected_vault_revision: SHA_D,
    observed_vault_revision: SHA_E,
    validation_outcome: 'VALID',
    validation_snapshot: {
      value: {
        type_tag: 'mapping',
        scalar_value: null,
        mapping_items: [
          {
            key: 'contract_version',
            value: {
              type_tag: 'string',
              scalar_value: 'localcomet.knowledge-change-review/1.0',
              mapping_items: [],
              sequence_items: []
            }
          },
          {
            key: 'proposal_content_hash',
            value: {
              type_tag: 'string',
              scalar_value: SHA_D,
              mapping_items: [],
              sequence_items: []
            }
          },
          {
            key: 'validated_vault_revision',
            value: {
              type_tag: 'string',
              scalar_value: SHA_E,
              mapping_items: [],
              sequence_items: []
            }
          }
        ],
        sequence_items: []
      },
      truncated: false
    },
    source_validation_findings: {
      items: [{ code: 'SOURCE_VALID', severity: 'INFO' }],
      original_count: 1,
      truncated: false
    },
    stable_id_set_hash: SHA_F,
    proposed_content_snapshot: {
      title: 'Review Center',
      body_text: {
        ...text(body),
        raw_text_hash: SHA_D,
        semantic_text_hash: SHA_E
      },
      type: 'architecture',
      status: 'current',
      knowledge_layer: 'current_source_truth',
      evidence_class: 'A',
      authority: 'source',
      canonical: true,
      canonical_scope: 'desktop',
      aliases: { items: ['review'], original_count: 1, truncated: false },
      releases: { items: ['v6.84.5.1'], original_count: 1, truncated: false },
      source_paths: {
        items: ['modules/knowledge_change_review_ru.py'],
        original_count: 1,
        truncated: false
      },
      evidence_refs: { items: ['e9b'], original_count: 1, truncated: false },
      supersedes: { items: [], original_count: 0, truncated: false },
      superseded_by: { items: [], original_count: 0, truncated: false },
      updated: '2026-07-16',
      last_reviewed: '2026-07-16',
      verified_at: null
    },
    findings: {
      items: [
        {
          code: 'TARGET_STATE_COMPARISON_UNAVAILABLE',
          severity: 'REVIEW',
          message: text('Comparison needs human review.'),
          details: {
            items: [{ key: 'target', value: 'architecture.review-center' }],
            original_count: 1,
            truncated: false
          }
        }
      ],
      original_count: 1,
      truncated: false
    },
    before_source_byte_hash: SHA_D,
    before_text_raw_hash: SHA_D,
    before_semantic_text_hash: SHA_E,
    proposed_text_raw_hash: SHA_D,
    proposed_semantic_text_hash: SHA_E,
    diff: {
      preview: text('@@ -1 +1 @@\n-old\n+new\n'),
      preview_truncated: false,
      preview_is_full_diff: false,
      full_diff_present: true,
      full_diff_hash: SHA_F,
      full_diff_utf8_bytes: 22
    },
    representation_delta: {
      before_present: true,
      after_present: true,
      before_line_endings: {
        crlf_count: 1,
        lf_count: 0,
        cr_count: 0,
        terminal_newline: true
      },
      after_line_endings: {
        crlf_count: 0,
        lf_count: 1,
        cr_count: 0,
        terminal_newline: true
      },
      terminal_newline_changed: false,
      after_source_bytes_known: true,
      source_bytes_changed_text_identical: false,
      raw_text_changed_semantic_equal: true,
      semantic_content_changed: false,
      identity: SHA_F
    },
    change_identity: CHANGE_ID,
    review_artifact_identity: REVIEW_ID,
    human_review_preview: text('Review this immutable proposal.'),
    ...patch
  };
}

function getEnvelope(
  value: KnowledgeChangeReviewProjection = projection(),
  patch: Partial<KnowledgeReviewGetEnvelope> = {}
): KnowledgeReviewGetEnvelope {
  return {
    contract: 'localcomet.knowledge-review-get/1.0',
    source: 'LOCAL_CONTROL_PLANE',
    fixture: false,
    projection: value,
    ...patch
  };
}

function snapshotEnvelope(
  refreshRequested = false,
  patch: Partial<KnowledgeReviewSnapshotEnvelope> = {}
): KnowledgeReviewSnapshotEnvelope {
  return {
    contract: refreshRequested
      ? 'localcomet.knowledge-review-refresh/1.0'
      : 'localcomet.knowledge-review-snapshot/1.0',
    command_center_version: 'v6.84.6',
    control_plane_version: 'v6.84.5.1e5',
    sidecar_runtime_version: 'v6.84.4.1',
    source: 'LOCAL_CONTROL_PLANE',
    fixture: false,
    refresh_requested: refreshRequested,
    refresh_succeeded: refreshRequested,
    current_vault_revision: SHA_E,
    freshness_known: true,
    knowledge_state: 'READY',
    last_error_code: null,
    inbox_count: 1,
    stale_count: 0,
    blocked_count: 0,
    session_decision_count: 0,
    review_states: [
      {
        review_artifact_identity: REVIEW_ID,
        status: 'REVIEW_REQUIRED',
        stale: false
      }
    ],
    hard_stop: true,
    persistence: false,
    vault_write_authority: false,
    publication_authority: false,
    ...patch
  };
}

function decisionRequest(
  patch: Partial<KnowledgeReviewDecisionRequest> = {}
): KnowledgeReviewDecisionRequest {
  return {
    reviewContractVersion: 'localcomet.knowledge-change-review/1.0',
    proposalId: PROPOSAL_ID,
    reviewArtifactIdentity: REVIEW_ID,
    changeIdentity: CHANGE_ID,
    observedVaultRevision: SHA_E,
    decision: 'APPROVE',
    comment: '',
    actorIdentifier: 'local-user',
    actorDisplayName: 'Local user',
    actorSource: 'LOCALCOMET_REVIEW_CENTER',
    ...patch
  };
}

function decisionEnvelope(
  request: KnowledgeReviewDecisionRequest = decisionRequest(),
  patch: Partial<KnowledgeReviewDecisionCreateEnvelope> = {}
): KnowledgeReviewDecisionCreateEnvelope {
  return {
    contract: 'localcomet.knowledge-review-decision-create/1.0',
    command_center_version: 'v6.84.6',
    control_plane_version: 'v6.84.5.1e5',
    sidecar_runtime_version: 'v6.84.4.1',
    source: 'LOCAL_CONTROL_PLANE',
    fixture: false,
    duplicate: false,
    current_vault_revision: request.observedVaultRevision,
    decision: {
      projection_contract: 'localcomet.knowledge-review-ui/1.0',
      kind: 'HUMAN_REVIEW_DECISION',
      contract_version: 'localcomet.knowledge-change-review-decision/1.0',
      review_contract_version: request.reviewContractVersion,
      review_status: 'REVIEW_REQUIRED',
      proposal_id: request.proposalId,
      review_artifact_identity: request.reviewArtifactIdentity,
      change_identity: request.changeIdentity,
      observed_vault_revision: request.observedVaultRevision,
      decision: request.decision,
      comment: request.comment,
      actor: {
        actor_identifier: request.actorIdentifier,
        display_name: request.actorDisplayName,
        source: request.actorSource
      },
      decision_identity: `kdecision:${'1'.repeat(64)}`,
      hard_stop: true,
      review_decision_only: true,
      actor_metadata_evidence_only: true,
      human_identity_authenticated: false,
      grants_write_authority: false,
      grants_vault_write_authority: false,
      grants_persistence_authority: false,
      grants_publication_authority: false,
      grants_merge_authority: false,
      grants_rebase_authority: false,
      grants_execution_authority: false,
      grants_policy_authority: false,
      grants_model_gateway_authority: false,
      grants_tauri_frontend_authority: false,
      grants_automatic_approval_authority: false
    },
    hard_stop: true,
    vault_modified: false,
    persistence: false,
    publication: false,
    ...patch
  };
}

beforeEach(() => {
  bridgeMock.calls = [];
  bridgeMock.response = listEnvelope();
});

describe('fixed Knowledge Operations Command Center bridge', () => {
  it('invokes the exact bounded list command and freezes its accepted response', async () => {
    const result = await listKnowledgeReviews(0, 50);
    expect(bridgeMock.calls).toEqual([
      { command: 'knowledge_review_list', args: { offset: 0, limit: 50 } }
    ]);
    expect(result.source).toBe('LOCAL_CONTROL_PLANE');
    expect(result.fixture).toBe(false);
    expect(Object.isFrozen(result)).toBe(true);
    expect(Object.isFrozen(result.items)).toBe(true);
    expect(Object.isFrozen(result.items[0])).toBe(true);
  });

  it('accepts a truthful empty page at a bounded offset beyond the collection end', async () => {
    bridgeMock.response = listEnvelope([], {
      offset: 128,
      limit: 1,
      total_count: 0,
      returned_count: 0,
      truncated: false,
      next_offset: null
    });
    const result = await listKnowledgeReviews(128, 1);
    expect(result.items).toEqual([]);
    expect(result.offset).toBe(128);
    expect(result.total_count).toBe(0);
    expect(bridgeMock.calls).toEqual([
      { command: 'knowledge_review_list', args: { offset: 128, limit: 1 } }
    ]);
  });

  it('invokes exact get, preserves all metadata, and retains the frozen raw projection', async () => {
    bridgeMock.response = getEnvelope();
    const result = await getKnowledgeReview(REVIEW_ID);
    expect(bridgeMock.calls).toEqual([
      { command: 'knowledge_review_get', args: { reviewArtifactIdentity: REVIEW_ID } }
    ]);
    const item = reviewProjectionToCenterItem(result);
    expect(item.fixture).toBe(false);
    expect(item.source).toBe('LOCAL_CONTROL_PLANE');
    expect(item.rawProjection).toEqual(result.projection);
    expect(item.proposedContent.source_paths).toEqual(['modules/knowledge_change_review_ru.py']);
    expect(item.validation.proposalContentHash).toBe(SHA_D);
    expect(item.representationDelta?.beforeLineEndings?.label).toBe('CRLF');
    expect(item.representationDelta?.afterLineEndings.label).toBe('LF');
    expect(item.detailProjectionTruncated).toBe(false);
    expect(Object.isFrozen(item.rawProjection)).toBe(true);
  });

  it('preserves and aggregates bounded body, collection, finding-message, and detail facts', async () => {
    const base = projection();
    const baseFinding = base.findings.items[0];
    const boundedProjection = projection({
      proposed_content_snapshot: {
        ...base.proposed_content_snapshot,
        body_text: {
          ...base.proposed_content_snapshot.body_text,
          ...text('Bounded body preview.', true),
          raw_text_hash: SHA_D,
          semantic_text_hash: SHA_E
        },
        aliases: {
          items: ['review'],
          original_count: 2,
          truncated: true
        }
      },
      findings: {
        items: [
          {
            ...baseFinding,
            message: text('Bounded finding preview.', true),
            details: {
              items: [{ key: 'target', value: 'architecture.review-center' }],
              original_count: 2,
              truncated: true
            }
          }
        ],
        original_count: 2,
        truncated: true
      }
    });
    bridgeMock.response = getEnvelope(boundedProjection);

    const item = reviewProjectionToCenterItem(await getKnowledgeReview(REVIEW_ID));
    expect(item.detailProjectionTruncated).toBe(true);
    expect(item.rawProjection.proposed_content_snapshot.body_text.truncated).toBe(true);
    expect(item.rawProjection.proposed_content_snapshot.aliases.truncated).toBe(true);
    expect(item.rawProjection.findings.truncated).toBe(true);
    expect(item.rawProjection.findings.items[0].message.truncated).toBe(true);
    expect(item.rawProjection.findings.items[0].details.truncated).toBe(true);
  });

  it('accepts a safe source path within Python code-point and UTF-8 bounds', async () => {
    const unicodePath = Array.from({ length: 5 }, () => '😀'.repeat(60)).join('/');
    expect([...unicodePath].length).toBe(304);
    expect(new TextEncoder().encode(unicodePath).length).toBe(1_204);
    const base = projection();
    bridgeMock.response = getEnvelope(projection({
      proposed_content_snapshot: {
        ...base.proposed_content_snapshot,
        source_paths: {
          items: [unicodePath],
          original_count: 1,
          truncated: false
        }
      }
    }));

    const accepted = await getKnowledgeReview(REVIEW_ID);
    expect(accepted.projection.proposed_content_snapshot.source_paths.items).toEqual([unicodePath]);
  });

  it('rejects wrong list contract, projection kind, and malformed identities', async () => {
    bridgeMock.response = { ...listEnvelope(), contract: 'localcomet.wrong/1.0' };
    await expect(listKnowledgeReviews()).rejects.toMatchObject({ code: 'invalid_payload' });

    bridgeMock.response = listEnvelope([
      { ...summary(), kind: 'KNOWLEDGE_CHANGE_REVIEW' as never }
    ]);
    await expect(listKnowledgeReviews()).rejects.toMatchObject({ code: 'invalid_payload' });

    await expect(getKnowledgeReview('kreview:not-a-hash')).rejects.toMatchObject({
      code: 'invalid_payload'
    });
  });

  it('rejects wrong full projection contract, kind, get identity, and unsafe source paths', async () => {
    bridgeMock.response = getEnvelope(
      projection({ projection_contract: 'localcomet.wrong/1.0' as never })
    );
    await expect(getKnowledgeReview(REVIEW_ID)).rejects.toMatchObject({ code: 'invalid_payload' });

    bridgeMock.response = getEnvelope(projection({ kind: 'HUMAN_REVIEW_DECISION' as never }));
    await expect(getKnowledgeReview(REVIEW_ID)).rejects.toMatchObject({ code: 'invalid_payload' });

    const otherIdentity = `kreview:${'9'.repeat(64)}`;
    bridgeMock.response = getEnvelope(projection({ review_artifact_identity: otherIdentity }));
    await expect(getKnowledgeReview(REVIEW_ID)).rejects.toMatchObject({ code: 'invalid_payload' });

    bridgeMock.response = getEnvelope(
      projection({
        proposed_content_snapshot: {
          ...projection().proposed_content_snapshot,
          source_paths: {
            items: ['C:/Vault/secret.md'],
            original_count: 1,
            truncated: false
          }
        }
      })
    );
    await expect(getKnowledgeReview(REVIEW_ID)).rejects.toMatchObject({ code: 'invalid_payload' });
  });

  it('enforces offset, limit, response, and projection bounds before accepting data', async () => {
    await expect(listKnowledgeReviews(129, 1)).rejects.toMatchObject({ code: 'invalid_payload' });
    await expect(listKnowledgeReviews(0, 0)).rejects.toMatchObject({ code: 'invalid_payload' });
    await expect(listKnowledgeReviews(0, MAX_KNOWLEDGE_REVIEW_LIST_LIMIT + 1)).rejects.toMatchObject({
      code: 'invalid_payload'
    });
    expect(bridgeMock.calls).toHaveLength(0);

    bridgeMock.response = { padding: 'x'.repeat(1_048_576) };
    await expect(listKnowledgeReviews()).rejects.toMatchObject({ code: 'invalid_payload' });

    bridgeMock.response = getEnvelope(
      projection({
        human_review_preview: {
          ...text('x'),
          preview_text: 'x'.repeat(262_145),
          preview_utf8_bytes: 262_145,
          original_utf8_bytes: 262_145
        }
      })
    );
    await expect(getKnowledgeReview(REVIEW_ID)).rejects.toMatchObject({ code: 'invalid_payload' });
  });

  it('preserves BLOCKED absence and rejects synthesized normal change material', async () => {
    const blocked = projection({
      status: 'BLOCKED',
      diff: null,
      representation_delta: null,
      change_identity: null
    });
    bridgeMock.response = getEnvelope(blocked);
    const accepted = reviewProjectionToCenterItem(await getKnowledgeReview(REVIEW_ID));
    expect(accepted.changeIdentity).toBeNull();
    expect(accepted.textDiff.preview).toBeNull();
    expect(accepted.representationDelta).toBeNull();

    bridgeMock.response = getEnvelope({ ...blocked, diff: projection().diff });
    await expect(getKnowledgeReview(REVIEW_ID)).rejects.toMatchObject({ code: 'invalid_payload' });
  });

  it('rejects duplicate summaries and inconsistent continuation metadata', async () => {
    bridgeMock.response = listEnvelope([summary(), summary()], {
      total_count: 2,
      returned_count: 2
    });
    await expect(listKnowledgeReviews()).rejects.toMatchObject({ code: 'invalid_payload' });

    bridgeMock.response = listEnvelope([summary()], {
      total_count: 2,
      returned_count: 1,
      truncated: true,
      next_offset: null
    });
    await expect(listKnowledgeReviews()).rejects.toMatchObject({ code: 'invalid_payload' });
  });

  it('invokes exact snapshot and refresh commands with immutable freshness state', async () => {
    bridgeMock.response = snapshotEnvelope(false);
    const snapshot = await getKnowledgeReviewSnapshot();
    expect(bridgeMock.calls).toEqual([
      { command: 'knowledge_review_snapshot', args: undefined }
    ]);
    expect(snapshot.review_states[0]).toMatchObject({
      review_artifact_identity: REVIEW_ID,
      stale: false
    });
    expect(Object.isFrozen(snapshot)).toBe(true);
    expect(Object.isFrozen(snapshot.review_states)).toBe(true);

    bridgeMock.calls = [];
    bridgeMock.response = snapshotEnvelope(true);
    const refreshed = await refreshKnowledgeReviews();
    expect(bridgeMock.calls).toEqual([
      { command: 'knowledge_review_refresh', args: undefined }
    ]);
    expect(refreshed.refresh_requested).toBe(true);
    expect(refreshed.refresh_succeeded).toBe(true);
  });

  it('rejects malformed snapshot counts, authority, contracts, and unknown freshness', async () => {
    bridgeMock.response = snapshotEnvelope(false, { stale_count: 1 });
    await expect(getKnowledgeReviewSnapshot()).rejects.toMatchObject({ code: 'invalid_payload' });

    bridgeMock.response = snapshotEnvelope(false, { persistence: true as never });
    await expect(getKnowledgeReviewSnapshot()).rejects.toMatchObject({ code: 'invalid_payload' });

    bridgeMock.response = snapshotEnvelope(false, {
      contract: 'localcomet.knowledge-review-refresh/1.0'
    });
    await expect(getKnowledgeReviewSnapshot()).rejects.toMatchObject({ code: 'invalid_payload' });

    bridgeMock.response = snapshotEnvelope(false, {
      current_vault_revision: null,
      freshness_known: false,
      review_states: [
        {
          review_artifact_identity: REVIEW_ID,
          status: 'REVIEW_REQUIRED',
          stale: false
        }
      ]
    });
    await expect(getKnowledgeReviewSnapshot()).rejects.toMatchObject({ code: 'invalid_payload' });
  });

  it('creates one exact e9c decision and verifies the complete HARD STOP response', async () => {
    const request = decisionRequest({
      decision: 'REQUEST_CHANGES',
      comment: 'Please clarify the evidence.'
    });
    bridgeMock.response = decisionEnvelope(request);
    const result = await createKnowledgeReviewDecision(request);
    expect(bridgeMock.calls).toEqual([
      {
        command: 'knowledge_review_decision_create',
        args: {
          reviewContractVersion: request.reviewContractVersion,
          proposalId: request.proposalId,
          reviewArtifactIdentity: request.reviewArtifactIdentity,
          changeIdentity: request.changeIdentity,
          observedVaultRevision: request.observedVaultRevision,
          decision: request.decision,
          comment: request.comment,
          actorIdentifier: request.actorIdentifier,
          actorDisplayName: request.actorDisplayName,
          actorSource: request.actorSource
        }
      }
    ]);
    expect(result.decision.decision_identity).toMatch(/^kdecision:[0-9a-f]{64}$/);
    expect(result.decision.comment).toBe(request.comment);
    expect(result.hard_stop).toBe(true);
    expect(result.vault_modified).toBe(false);
    expect(result.persistence).toBe(false);
    expect(result.publication).toBe(false);
    expect(Object.isFrozen(result.decision.actor)).toBe(true);
  });

  it('rejects unbound, over-limit, stale, or authority-bearing decisions', async () => {
    await expect(
      createKnowledgeReviewDecision(decisionRequest({
        decision: 'REQUEST_CHANGES',
        comment: '   '
      }))
    ).rejects.toMatchObject({ code: 'invalid_payload' });
    await expect(
      createKnowledgeReviewDecision(decisionRequest({ comment: 'x'.repeat(2_001) }))
    ).rejects.toMatchObject({ code: 'invalid_payload' });
    await expect(
      createKnowledgeReviewDecision(decisionRequest({ actorIdentifier: 'x'.repeat(257) }))
    ).rejects.toMatchObject({ code: 'invalid_payload' });
    await expect(
      createKnowledgeReviewDecision(decisionRequest({
        decision: 'APPROVE',
        changeIdentity: null
      }))
    ).rejects.toMatchObject({ code: 'invalid_payload' });
    expect(bridgeMock.calls).toHaveLength(0);

    const request = decisionRequest();
    bridgeMock.response = decisionEnvelope(request, { current_vault_revision: SHA_D });
    await expect(createKnowledgeReviewDecision(request)).rejects.toMatchObject({
      code: 'invalid_payload'
    });

    bridgeMock.response = decisionEnvelope(request, {
      vault_modified: true as never
    });
    await expect(createKnowledgeReviewDecision(request)).rejects.toMatchObject({
      code: 'invalid_payload'
    });

    const wrong = decisionEnvelope(request);
    bridgeMock.response = {
      ...wrong,
      decision: {
        ...wrong.decision,
        review_artifact_identity: `kreview:${'9'.repeat(64)}`
      }
    };
    await expect(createKnowledgeReviewDecision(request)).rejects.toMatchObject({
      code: 'invalid_payload'
    });
  });

});
