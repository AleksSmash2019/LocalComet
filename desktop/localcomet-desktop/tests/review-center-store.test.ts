import { get } from 'svelte/store';
import { describe, expect, it, vi } from 'vitest';
import type { KnowledgeReviewClient } from '../src/lib/bridge/knowledgeReview';
import { REVIEW_FIXTURES } from '../src/lib/data/reviewFixtures';
import { createReviewCenterController } from '../src/lib/stores/reviewCenter';
import type {
  KnowledgeChangeReviewProjection,
  KnowledgeReviewGetEnvelope,
  KnowledgeReviewDecisionCreateEnvelope,
  KnowledgeReviewListEnvelope,
  KnowledgeReviewSnapshotEnvelope,
  KnowledgeReviewSummaryProjection,
  ReviewStatus
} from '../src/lib/types/knowledgeReview';

const REVIEW_A = `kreview:${'a'.repeat(64)}`;
const REVIEW_B = `kreview:${'b'.repeat(64)}`;
const PROPOSAL = `kprop:${'c'.repeat(64)}`;
const CHANGE = `kchange:${'d'.repeat(64)}`;
const HASH = `sha256:${'e'.repeat(64)}`;

type Deferred<T> = Readonly<{
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason: unknown) => void;
}>;

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function summary(
  reviewArtifactIdentity = REVIEW_A,
  status: ReviewStatus = 'CLEAR'
): KnowledgeReviewSummaryProjection {
  const blocked = status === 'BLOCKED';
  return {
    projection_contract: 'localcomet.knowledge-review-ui/1.0',
    kind: 'KNOWLEDGE_CHANGE_REVIEW_SUMMARY',
    contract_version: 'localcomet.knowledge-change-review/1.0',
    status,
    blocked,
    proposal_id: PROPOSAL,
    target_stable_id: `review.${reviewArtifactIdentity.slice(-8)}`,
    operation: 'UPDATE_EXISTING',
    expected_vault_revision: HASH,
    observed_vault_revision: HASH,
    review_artifact_identity: reviewArtifactIdentity,
    change_identity: blocked ? null : CHANGE,
    finding_count: blocked ? 1 : 0,
    normal_change_material_present: !blocked,
    detail_projection_truncated: false
  };
}

function listEnvelope(
  items: readonly KnowledgeReviewSummaryProjection[],
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

function reviewIdentity(index: number): string {
  return `kreview:${index.toString(16).padStart(64, '0')}`;
}

function reviewSummaries(count: number): readonly KnowledgeReviewSummaryProjection[] {
  return Object.freeze(
    Array.from({ length: count }, (_, index) => summary(reviewIdentity(index + 1)))
  );
}

function pagedListEnvelope(
  allItems: readonly KnowledgeReviewSummaryProjection[],
  offset: number,
  limit = 50
): KnowledgeReviewListEnvelope {
  const items = allItems.slice(offset, offset + limit);
  const nextOffset = offset + items.length;
  const truncated = nextOffset < allItems.length;
  return listEnvelope(items, {
    offset,
    limit,
    total_count: allItems.length,
    returned_count: items.length,
    truncated,
    next_offset: truncated ? nextOffset : null
  });
}

function snapshotEnvelope(
  states: readonly { review_artifact_identity: string; status: ReviewStatus; stale: boolean | null }[] = [
    { review_artifact_identity: REVIEW_A, status: 'CLEAR', stale: false },
    { review_artifact_identity: REVIEW_B, status: 'CLEAR', stale: false }
  ],
  refreshRequested = false
): KnowledgeReviewSnapshotEnvelope {
  return {
    contract: refreshRequested
      ? 'localcomet.knowledge-review-refresh/1.0'
      : 'localcomet.knowledge-review-snapshot/1.0',
    command_center_version: 'v6.84.6',
    control_plane_version: 'v6.84.5.1',
    sidecar_runtime_version: 'v6.84.3',
    source: 'LOCAL_CONTROL_PLANE',
    fixture: false,
    refresh_requested: refreshRequested,
    refresh_succeeded: refreshRequested,
    current_vault_revision: HASH,
    freshness_known: true,
    knowledge_state: 'READY',
    last_error_code: null,
    inbox_count: states.length,
    stale_count: states.filter((state) => state.stale === true).length,
    blocked_count: states.filter((state) => state.status === 'BLOCKED').length,
    session_decision_count: 0,
    review_states: states,
    hard_stop: true,
    persistence: false,
    vault_write_authority: false,
    publication_authority: false
  };
}

function decisionEnvelope(
  request: Parameters<KnowledgeReviewClient['createDecision']>[0]
): KnowledgeReviewDecisionCreateEnvelope {
  return {
    contract: 'localcomet.knowledge-review-decision-create/1.0',
    command_center_version: 'v6.84.6',
    control_plane_version: 'v6.84.5.1',
    sidecar_runtime_version: 'v6.84.3',
    source: 'LOCAL_CONTROL_PLANE',
    fixture: false,
    duplicate: false,
    current_vault_revision: request.observedVaultRevision,
    decision: {
      projection_contract: 'localcomet.knowledge-review-ui/1.0',
      kind: 'HUMAN_REVIEW_DECISION',
      contract_version: 'localcomet.knowledge-change-review-decision/1.0',
      review_contract_version: request.reviewContractVersion,
      review_status: 'CLEAR',
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
      decision_identity: `kdecision:${'f'.repeat(64)}`,
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
    publication: false
  };
}

function getEnvelope(
  reviewArtifactIdentity = REVIEW_A,
  status: ReviewStatus = 'CLEAR'
): KnowledgeReviewGetEnvelope {
  const blocked = status === 'BLOCKED';
  const preview = {
    preview_text: 'bounded text',
    is_preview: true,
    truncated: false,
    original_utf8_bytes: 12,
    original_line_count: 1,
    preview_utf8_bytes: 12,
    preview_line_count: 1
  };
  const projection = {
    projection_contract: 'localcomet.knowledge-review-ui/1.0',
    kind: 'KNOWLEDGE_CHANGE_REVIEW',
    contract_version: 'localcomet.knowledge-change-review/1.0',
    status,
    proposal_id: PROPOSAL,
    proposal_content_hash: HASH,
    operation: 'UPDATE_EXISTING',
    target_stable_id: `review.${reviewArtifactIdentity.slice(-8)}`,
    expected_vault_revision: HASH,
    observed_vault_revision: HASH,
    validation_outcome: 'VALID',
    validation_snapshot: {
      value: { type_tag: 'mapping', scalar_value: null, mapping_items: [], sequence_items: [] },
      truncated: false
    },
    source_validation_findings: { items: [], original_count: 0, truncated: false },
    stable_id_set_hash: HASH,
    proposed_content_snapshot: {
      title: 'Real review',
      body_text: { ...preview, raw_text_hash: HASH, semantic_text_hash: HASH },
      type: 'architecture',
      status: 'current',
      knowledge_layer: 'current_source_truth',
      evidence_class: 'A',
      authority: 'source',
      canonical: true,
      canonical_scope: null,
      aliases: { items: [], original_count: 0, truncated: false },
      releases: { items: [], original_count: 0, truncated: false },
      source_paths: { items: ['modules/review.py'], original_count: 1, truncated: false },
      evidence_refs: { items: [], original_count: 0, truncated: false },
      supersedes: { items: [], original_count: 0, truncated: false },
      superseded_by: { items: [], original_count: 0, truncated: false },
      updated: '2026-07-16',
      last_reviewed: '2026-07-16',
      verified_at: null
    },
    findings: { items: [], original_count: 0, truncated: false },
    before_source_byte_hash: blocked ? null : HASH,
    before_text_raw_hash: blocked ? null : HASH,
    before_semantic_text_hash: blocked ? null : HASH,
    proposed_text_raw_hash: HASH,
    proposed_semantic_text_hash: HASH,
    diff: blocked
      ? null
      : {
          preview,
          preview_truncated: false,
          preview_is_full_diff: true,
          full_diff_present: true,
          full_diff_hash: HASH,
          full_diff_utf8_bytes: 12
        },
    representation_delta: blocked
      ? null
      : {
          before_present: true,
          after_present: true,
          before_line_endings: {
            crlf_count: 0,
            lf_count: 1,
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
          raw_text_changed_semantic_equal: false,
          semantic_content_changed: true,
          identity: HASH
        },
    change_identity: blocked ? null : CHANGE,
    review_artifact_identity: reviewArtifactIdentity,
    human_review_preview: preview
  } as KnowledgeChangeReviewProjection;
  return {
    contract: 'localcomet.knowledge-review-get/1.0',
    source: 'LOCAL_CONTROL_PLANE',
    fixture: false,
    projection
  };
}

function client(
  list: KnowledgeReviewClient['list'],
  getReview: KnowledgeReviewClient['get'] = async (identity) => getEnvelope(identity),
  snapshot: KnowledgeReviewClient['snapshot'] = async () => snapshotEnvelope(),
  refresh: KnowledgeReviewClient['refresh'] = async () => snapshotEnvelope(undefined, true),
  createDecision: KnowledgeReviewClient['createDecision'] = async (request) =>
    decisionEnvelope(request)
): KnowledgeReviewClient {
  return { list, get: getReview, snapshot, refresh, createDecision };
}

describe('real read-only Review Center store', () => {
  it('starts idle with an empty production queue and no fixture fallback', () => {
    const controller = createReviewCenterController(
      client(async () => listEnvelope([]))
    );
    expect(get(controller.reviewCenterState)).toMatchObject({
      status: 'idle',
      source: 'LOCAL_CONTROL_PLANE',
      retryable: false,
      totalCount: 0
    });
    expect(get(controller.reviewQueue)).toEqual([]);
    expect(get(controller.selectedReview)).toBeNull();
    expect('localStorage' in globalThis).toBe(false);
  });

  it('moves through loading to truthful empty state', async () => {
    const pending = deferred<KnowledgeReviewListEnvelope>();
    const controller = createReviewCenterController(client(() => pending.promise));
    const loading = controller.loadReviewCenter();
    expect(get(controller.reviewCenterState).status).toBe('loading');
    pending.resolve(listEnvelope([]));
    await expect(loading).resolves.toBe(true);
    expect(get(controller.reviewCenterState)).toMatchObject({
      status: 'empty',
      source: 'LOCAL_CONTROL_PLANE',
      returnedCount: 0,
      truncated: false,
      nextOffset: null
    });
    expect(get(controller.reviewQueue)).toEqual([]);
  });

  it('loads exactly 50 items in one bounded page', async () => {
    const items = reviewSummaries(50);
    const list = vi.fn(async (offset: number, limit: number) =>
      pagedListEnvelope(items, offset, limit)
    );
    const controller = createReviewCenterController(client(list));
    await expect(controller.loadReviewCenter()).resolves.toBe(true);
    expect(list).toHaveBeenCalledTimes(1);
    expect(list).toHaveBeenCalledWith(0, 50);
    expect(get(controller.reviewQueue)).toHaveLength(50);
    expect(get(controller.reviewCenterState)).toMatchObject({
      status: 'ready',
      totalCount: 50,
      returnedCount: 50,
      truncated: false,
      nextOffset: null
    });
  });

  it('aggregates 51 items across two pages before exposing ready state', async () => {
    const items = reviewSummaries(51);
    const list = vi.fn(async (offset: number, limit: number) =>
      pagedListEnvelope(items, offset, limit)
    );
    const getReview = vi.fn(async (identity: string) => getEnvelope(identity));
    const controller = createReviewCenterController(client(list, getReview));
    await expect(controller.loadReviewCenter()).resolves.toBe(true);
    expect(list.mock.calls).toEqual([[0, 50], [50, 50]]);
    expect(get(controller.reviewQueue)).toHaveLength(51);
    expect(get(controller.reviewCenterState)).toMatchObject({
      status: 'ready',
      totalCount: 51,
      returnedCount: 51,
      truncated: false,
      nextOffset: null
    });
    expect(getReview).toHaveBeenCalledWith(reviewIdentity(1));
  });

  it('aggregates the full hard maximum of 128 items without persistence', async () => {
    const items = reviewSummaries(128);
    const list = vi.fn(async (offset: number, limit: number) =>
      pagedListEnvelope(items, offset, limit)
    );
    const controller = createReviewCenterController(client(list));
    await expect(controller.loadReviewCenter()).resolves.toBe(true);
    expect(list.mock.calls).toEqual([[0, 50], [50, 50], [100, 50]]);
    expect(get(controller.reviewQueue)).toHaveLength(128);
    expect(get(controller.reviewCenterState)).toMatchObject({
      totalCount: 128,
      returnedCount: 128,
      truncated: false,
      nextOffset: null
    });
  });

  it('rejects malformed and repeated pagination continuations', async () => {
    const items = reviewSummaries(52);
    const malformed = createReviewCenterController(
      client(async () => ({
        ...pagedListEnvelope(items, 0),
        next_offset: 49
      }))
    );
    await expect(malformed.loadReviewCenter()).resolves.toBe(false);
    expect(get(malformed.reviewCenterState)).toMatchObject({
      status: 'error',
      error: { code: 'invalid_payload' }
    });

    const repeatedList = vi.fn(async (offset: number) => {
      if (offset === 0) return pagedListEnvelope(items, 0);
      return {
        ...pagedListEnvelope(items, 50),
        truncated: true,
        next_offset: 50
      };
    });
    const repeated = createReviewCenterController(client(repeatedList));
    await expect(repeated.loadReviewCenter()).resolves.toBe(false);
    expect(get(repeated.reviewCenterState)).toMatchObject({
      status: 'error',
      error: { code: 'invalid_payload' }
    });
  });

  it('rejects duplicate identities across pages', async () => {
    const items = [...reviewSummaries(51)];
    items[50] = items[0];
    const controller = createReviewCenterController(
      client(async (offset: number, limit: number) =>
        pagedListEnvelope(items, offset, limit)
      )
    );
    await expect(controller.loadReviewCenter()).resolves.toBe(false);
    expect(get(controller.reviewCenterState)).toMatchObject({
      status: 'error',
      error: { code: 'invalid_payload' },
      returnedCount: 50,
      truncated: true,
      nextOffset: 50
    });
    expect(get(controller.reviewQueue)).toHaveLength(50);
  });

  it('keeps honest partial results when a later page fails and retry reloads all pages', async () => {
    const items = reviewSummaries(51);
    let failedOnce = false;
    const list = vi.fn(async (offset: number, limit: number) => {
      if (offset === 50 && !failedOnce) {
        failedOnce = true;
        throw { code: 'timeout', message: 'second page unavailable' };
      }
      return pagedListEnvelope(items, offset, limit);
    });
    const controller = createReviewCenterController(client(list));
    await expect(controller.loadReviewCenter()).resolves.toBe(false);
    expect(get(controller.reviewCenterState)).toMatchObject({
      status: 'error',
      retryable: true,
      totalCount: 51,
      returnedCount: 50,
      truncated: true,
      nextOffset: 50
    });
    expect(get(controller.reviewQueue)).toHaveLength(50);

    await expect(controller.retryReviewCenter()).resolves.toBe(true);
    expect(get(controller.reviewCenterState)).toMatchObject({
      status: 'ready',
      totalCount: 51,
      returnedCount: 51,
      truncated: false,
      nextOffset: null
    });
    expect(get(controller.reviewQueue)).toHaveLength(51);
  });

  it('preserves a selected identity across a refresh that aggregates later pages', async () => {
    const items = reviewSummaries(51);
    const list = vi.fn(async (offset: number, limit: number) =>
      pagedListEnvelope(items, offset, limit)
    );
    const controller = createReviewCenterController(client(list));
    await controller.loadReviewCenter();
    const lastIdentity = reviewIdentity(51);
    expect(controller.selectReview(lastIdentity)).toBe(true);
    await vi.waitFor(() => {
      expect(get(controller.selectedReview)?.reviewArtifactIdentity).toBe(lastIdentity);
    });
    await expect(controller.refreshReviewCenter()).resolves.toBe(true);
    expect(get(controller.selectedReviewId)).toBe(lastIdentity);
    expect(get(controller.selectedReview)?.reviewArtifactIdentity).toBe(lastIdentity);
  });

  it('search and filters include artifacts beyond index 49', async () => {
    const items = reviewSummaries(51);
    const controller = createReviewCenterController(
      client(async (offset: number, limit: number) =>
        pagedListEnvelope(items, offset, limit)
      )
    );
    await controller.loadReviewCenter();
    const lastIdentity = reviewIdentity(51);
    controller.setReviewQuery(lastIdentity);
    expect(get(controller.filteredReviewQueue).map((item) => item.reviewArtifactIdentity)).toEqual([
      lastIdentity
    ]);
  });

  it('suppresses an out-of-order get response after a newer selection', async () => {
    const first = deferred<KnowledgeReviewGetEnvelope>();
    const second = deferred<KnowledgeReviewGetEnvelope>();
    const getReview = vi.fn((identity: string) =>
      identity === REVIEW_A ? first.promise : second.promise
    );
    const controller = createReviewCenterController(
      client(async () => listEnvelope([summary(REVIEW_A), summary(REVIEW_B)]), getReview)
    );
    const initialLoad = controller.loadReviewCenter();
    await vi.waitFor(() => {
      expect(get(controller.selectedReviewId)).toBe(REVIEW_A);
    });
    expect(controller.selectReview(REVIEW_B)).toBe(true);
    second.resolve(getEnvelope(REVIEW_B));
    await Promise.resolve();
    await Promise.resolve();
    expect(get(controller.selectedReview)?.reviewArtifactIdentity).toBe(REVIEW_B);
    first.resolve(getEnvelope(REVIEW_A));
    await initialLoad;
    expect(get(controller.selectedReview)?.reviewArtifactIdentity).toBe(REVIEW_B);
  });

  it('suppresses an older list response after a newer refresh', async () => {
    const oldList = deferred<KnowledgeReviewListEnvelope>();
    const newList = deferred<KnowledgeReviewListEnvelope>();
    let call = 0;
    const controller = createReviewCenterController(
      client(() => (call++ === 0 ? oldList.promise : newList.promise))
    );
    const oldLoad = controller.loadReviewCenter();
    const newLoad = controller.loadReviewCenter();
    newList.resolve(listEnvelope([]));
    await newLoad;
    oldList.resolve(listEnvelope([summary()]));
    await oldLoad;
    expect(get(controller.reviewCenterState).status).toBe('empty');
    expect(get(controller.reviewQueue)).toEqual([]);
  });

  it('retries transient failures but not invalid payloads', async () => {
    let calls = 0;
    const transient = createReviewCenterController(
      client(async () => {
        calls += 1;
        if (calls === 1) throw { code: 'timeout', message: 'temporarily unavailable' };
        return listEnvelope([]);
      })
    );
    await expect(transient.loadReviewCenter()).resolves.toBe(false);
    expect(get(transient.reviewCenterState)).toMatchObject({ status: 'error', retryable: true });
    await expect(transient.retryReviewCenter()).resolves.toBe(true);
    expect(get(transient.reviewCenterState).status).toBe('empty');

    const invalid = createReviewCenterController(
      client(async () => { throw { code: 'invalid_payload', message: 'bad contract' }; })
    );
    await invalid.loadReviewCenter();
    expect(get(invalid.reviewCenterState)).toMatchObject({ status: 'error', retryable: false });
    await expect(invalid.retryReviewCenter()).resolves.toBe(false);
  });

  it('keeps empty keyboard selection safe', () => {
    const controller = createReviewCenterController(client(async () => listEnvelope([])));
    expect(controller.moveReviewSelection(1)).toBeNull();
    expect(controller.selectReviewBoundary('first')).toBeNull();
    expect(controller.selectReview('missing')).toBe(false);
  });

  it('retains fixture-only decision behavior only for explicit fixture props', () => {
    const controller = createReviewCenterController(client(async () => listEnvelope([])));
    const fixture = REVIEW_FIXTURES[0];
    expect(fixture.fixture).toBe(true);
    expect(controller.openDecisionDialog(fixture, 'REQUEST_CHANGES')).toBe(true);
    controller.setDecisionComment('Explicit fixture review only.');
    expect(controller.confirmFixtureDecision(fixture)).toBe(true);
    expect(get(controller.fixtureDecisionResult)).toMatchObject({ fixture: true, hardStop: true });
  });

  it('creates a real e9c decision and preserves HARD STOP', async () => {
    const createDecision = vi.fn(async (request) => decisionEnvelope(request));
    const controller = createReviewCenterController(
      client(
        async () => listEnvelope([summary()]),
        async () => getEnvelope(REVIEW_A),
        async () => snapshotEnvelope([
          { review_artifact_identity: REVIEW_A, status: 'CLEAR', stale: false }
        ]),
        async () => snapshotEnvelope([
          { review_artifact_identity: REVIEW_A, status: 'CLEAR', stale: false }
        ], true),
        createDecision
      )
    );
    await controller.loadReviewCenter();
    const real = get(controller.selectedReview)!;
    expect(controller.openDecisionDialog(real, 'APPROVE')).toBe(true);
    expect(await controller.confirmDecision(real)).toBe(true);
    expect(createDecision).toHaveBeenCalledOnce();
    expect(get(controller.realDecisionResult)).toMatchObject({
      fixture: false,
      hardStop: true,
      vaultModified: false,
      persistence: false,
      publication: false
    });
    expect(get(controller.reviewActivity).some((event) => event.kind === 'DECISION_CREATED')).toBe(true);
  });

  it('blocks every real decision when the exact review is stale', async () => {
    const controller = createReviewCenterController(
      client(
        async () => listEnvelope([summary()]),
        async () => getEnvelope(REVIEW_A),
        async () => snapshotEnvelope([
          { review_artifact_identity: REVIEW_A, status: 'CLEAR', stale: true }
        ])
      )
    );
    await controller.loadReviewCenter();
    const real = get(controller.selectedReview)!;
    for (const intent of ['APPROVE', 'REJECT', 'REQUEST_CHANGES'] as const) {
      expect(controller.openDecisionDialog(real, intent)).toBe(false);
      expect(get(controller.decisionDialog).open).toBe(false);
    }
  });

  it('filters and deterministically sorts the bounded queue', async () => {
    const controller = createReviewCenterController(
      client(async () => listEnvelope([
        summary(REVIEW_A, 'BLOCKED'),
        summary(REVIEW_B, 'CLEAR')
      ]))
    );
    await controller.loadReviewCenter();
    expect(get(controller.filteredReviewQueue).map((item) => item.status)).toEqual([
      'BLOCKED',
      'CLEAR'
    ]);
    controller.toggleReviewStatus('CLEAR');
    expect(get(controller.filteredReviewQueue).map((item) => item.reviewArtifactIdentity)).toEqual([
      REVIEW_B
    ]);
    controller.setReviewQuery('no-match');
    expect(get(controller.filteredReviewQueue)).toEqual([]);
    controller.clearReviewFilters();
    expect(get(controller.filteredReviewQueue)).toHaveLength(2);
  });

  it('reset invalidates pending work without persistence or duplicate state', async () => {
    const pending = deferred<KnowledgeReviewListEnvelope>();
    const controller = createReviewCenterController(client(() => pending.promise));
    const load = controller.loadReviewCenter();
    controller.resetReviewCenterStore();
    pending.resolve(listEnvelope([summary()]));
    await load;
    expect(get(controller.reviewCenterState).status).toBe('idle');
    expect(get(controller.reviewQueue)).toEqual([]);
  });
});
