import { derived, get, writable } from 'svelte/store';
import {
  HUMAN_REVIEW_DECISION_CONTRACT,
  KNOWLEDGE_CHANGE_REVIEW_CONTRACT,
  KNOWLEDGE_OPERATIONS_COMMAND_CENTER_VERSION,
  KNOWLEDGE_REVIEW_ACTOR_SOURCE,
  KNOWLEDGE_REVIEW_LIST_LIMIT,
  KNOWLEDGE_REVIEW_LIST_OFFSET,
  MAX_KNOWLEDGE_REVIEW_LIST_OFFSET,
  KNOWLEDGE_REVIEW_PROJECTION_CONTRACT,
  knowledgeReviewClient,
  normalizeKnowledgeReviewError,
  reviewProjectionToCenterItem,
  reviewSummaryToQueueItem,
  type KnowledgeReviewClient
} from '$lib/bridge/knowledgeReview';
import type {
  DecisionDialogState,
  DecisionIntent,
  FixtureDecisionResult,
  KnowledgeReviewSnapshotEnvelope,
  RealDecisionResult,
  RealReviewCenterItem,
  ReviewActivityEvent,
  ReviewCenterItem,
  ReviewCenterState,
  ReviewDecisionResult,
  ReviewDiagnostics,
  ReviewFilterState,
  ReviewOperation,
  ReviewQueueItem,
  ReviewStatus
} from '$lib/types/knowledgeReview';

export const MAX_REVIEW_COMMENT_LENGTH = 2000;
export const MAX_REVIEW_ACTIVITY_ITEMS = 128;
export const DEFAULT_REVIEW_ACTOR_IDENTIFIER = 'local-user';
export const DEFAULT_REVIEW_ACTOR_DISPLAY_NAME = 'Local user';

const INITIAL_DIALOG: DecisionDialogState = Object.freeze({
  open: false,
  intent: null,
  comment: '',
  actorIdentifier: DEFAULT_REVIEW_ACTOR_IDENTIFIER,
  actorDisplayName: DEFAULT_REVIEW_ACTOR_DISPLAY_NAME,
  submitting: false,
  errorKey: null
});

const INITIAL_REVIEW_CENTER_STATE: ReviewCenterState = Object.freeze({
  status: 'idle',
  source: 'LOCAL_CONTROL_PLANE',
  error: null,
  failedRequest: null,
  retryable: false,
  totalCount: 0,
  returnedCount: 0,
  truncated: false,
  nextOffset: null
});

const INITIAL_FILTERS: ReviewFilterState = Object.freeze({
  query: '',
  statuses: Object.freeze([]),
  operations: Object.freeze([]),
  sort: 'STATUS_THEN_IDENTITY'
});

const STATUS_ORDER: Readonly<Record<ReviewStatus, number>> = Object.freeze({
  BLOCKED: 0,
  REVIEW_REQUIRED: 1,
  CLEAR: 2
});

export function createReviewCenterController(client: KnowledgeReviewClient = knowledgeReviewClient) {
  const reviewCenterState = writable<ReviewCenterState>(INITIAL_REVIEW_CENTER_STATE);
  const reviewQueue = writable<readonly ReviewQueueItem[]>([]);
  const selectedReviewId = writable<string | null>(null);
  const selectedReview = writable<ReviewCenterItem | null>(null);
  const reviewSnapshot = writable<KnowledgeReviewSnapshotEnvelope | null>(null);
  const decisionDialog = writable<DecisionDialogState>(INITIAL_DIALOG);
  const decisionResult = writable<ReviewDecisionResult | null>(null);
  const fixtureDecisionResult = derived(decisionResult, ($result) =>
    $result?.fixture === true ? $result : null
  );
  const realDecisionResult = derived(decisionResult, ($result) =>
    $result?.fixture === false ? $result : null
  );
  const reviewFilters = writable<ReviewFilterState>(INITIAL_FILTERS);
  const reviewActivity = writable<readonly ReviewActivityEvent[]>([]);

  const filteredReviewQueue = derived(
    [reviewQueue, reviewFilters],
    ([$queue, $filters]) => filterAndSortQueue($queue, $filters)
  );

  const reviewDiagnostics = derived(
    [reviewSnapshot, reviewCenterState],
    ([$snapshot, $state]): ReviewDiagnostics => Object.freeze({
      commandCenterVersion: KNOWLEDGE_OPERATIONS_COMMAND_CENTER_VERSION,
      frontendContractVersion: KNOWLEDGE_REVIEW_PROJECTION_CONTRACT,
      tauriBridgeStatus:
        $state.status === 'idle'
          ? 'IDLE'
          : $state.status === 'loading'
            ? 'CONNECTING'
            : $state.status === 'error'
              ? 'ERROR'
              : 'CONNECTED',
      sidecarConnectionState:
        $state.status === 'idle'
          ? 'IDLE'
          : $state.status === 'loading'
            ? 'CONNECTING'
            : $state.error?.code === 'sidecar_unavailable'
              ? 'UNAVAILABLE'
              : $state.status === 'error'
                ? 'ERROR'
                : 'CONNECTED',
      pythonRuntimeContractVersion: $snapshot?.sidecar_runtime_version ?? null,
      inboxCount: $snapshot?.inbox_count ?? $state.totalCount,
      staleCount: $snapshot?.stale_count ?? 0,
      blockedCount: $snapshot?.blocked_count ?? 0,
      sessionDecisionCount: $snapshot?.session_decision_count ?? 0,
      currentVaultRevision: $snapshot?.current_vault_revision ?? null,
      freshnessKnown: $snapshot?.freshness_known ?? false,
      lastErrorCode: $snapshot?.last_error_code ?? $state.error?.code ?? null
    })
  );

  let listGeneration = 0;
  let getGeneration = 0;
  let decisionGeneration = 0;
  let activitySequence = 0;
  let listMetadata = {
    totalCount: 0,
    returnedCount: 0,
    truncated: false,
    nextOffset: null as number | null
  };

  function appendActivity(
    kind: ReviewActivityEvent['kind'],
    messageKey: string,
    reviewArtifactIdentity: string | null = null,
    errorCode: string | null = null
  ): void {
    activitySequence += 1;
    const event: ReviewActivityEvent = Object.freeze({
      id: `review-activity-${activitySequence}`,
      sequence: activitySequence,
      kind,
      messageKey,
      reviewArtifactIdentity,
      errorCode
    });
    reviewActivity.update((items) =>
      Object.freeze([...items, event].slice(-MAX_REVIEW_ACTIVITY_ITEMS))
    );
  }

  function setLoading(failedRequest: ReviewCenterState['failedRequest'] = null): void {
    reviewCenterState.set({
      status: 'loading',
      source: 'LOCAL_CONTROL_PLANE',
      error: null,
      failedRequest,
      retryable: false,
      ...listMetadata
    });
  }

  function setError(
    error: unknown,
    failedRequest: NonNullable<ReviewCenterState['failedRequest']>
  ): void {
    const normalized = normalizeKnowledgeReviewError(error);
    reviewCenterState.set({
      status: 'error',
      source: 'LOCAL_CONTROL_PLANE',
      error: normalized,
      failedRequest,
      retryable: isTransientReviewError(normalized.code),
      ...listMetadata
    });
    appendActivity('ERROR', 'review.activity.error', get(selectedReviewId), normalized.code);
  }

  function applySnapshot(
    queue: readonly ReviewQueueItem[],
    snapshot: KnowledgeReviewSnapshotEnvelope
  ): readonly ReviewQueueItem[] {
    const staleByIdentity = new Map(
      snapshot.review_states.map((item) => [item.review_artifact_identity, item.stale] as const)
    );
    return Object.freeze(
      queue.map((item) =>
        Object.freeze({
          ...item,
          stale: staleByIdentity.get(item.reviewArtifactIdentity) ?? null
        })
      )
    );
  }

  function applySelectedFreshness(
    review: RealReviewCenterItem,
    snapshot: KnowledgeReviewSnapshotEnvelope | null
  ): RealReviewCenterItem {
    const state = snapshot?.review_states.find(
      (candidate) => candidate.review_artifact_identity === review.reviewArtifactIdentity
    );
    return Object.freeze({ ...review, stale: state?.stale ?? null });
  }

  async function loadReviewCenter(options: { refresh?: boolean } = {}): Promise<boolean> {
    const currentListGeneration = ++listGeneration;
    getGeneration += 1;
    decisionGeneration += 1;
    const previousSelectedIdentity = get(selectedReviewId);
    listMetadata = { totalCount: 0, returnedCount: 0, truncated: false, nextOffset: null };
    setLoading(options.refresh ? 'refresh' : 'list');
    reviewQueue.set([]);
    selectedReviewId.set(null);
    selectedReview.set(null);
    decisionResult.set(null);
    closeDecisionDialog();

    let snapshot: KnowledgeReviewSnapshotEnvelope | null = null;
    const collected: ReviewQueueItem[] = [];
    const seenOffsets = new Set<number>();
    const seenIdentities = new Set<string>();
    let expectedTotalCount: number | null = null;
    let requestedOffset = KNOWLEDGE_REVIEW_LIST_OFFSET;
    let lastIdentity: string | null = null;

    try {
      snapshot = options.refresh ? await client.refresh() : await client.snapshot();

      while (true) {
        if (seenOffsets.has(requestedOffset)) {
          throw reviewPaginationError('Review pagination repeated an offset');
        }
        seenOffsets.add(requestedOffset);

        const envelope = await client.list(requestedOffset, KNOWLEDGE_REVIEW_LIST_LIMIT);
        if (expectedTotalCount === null) {
          expectedTotalCount = envelope.total_count;
        } else if (envelope.total_count !== expectedTotalCount) {
          throw reviewPaginationError('Review pagination total changed between pages');
        }
        if (
          envelope.offset !== requestedOffset ||
          envelope.returned_count !== envelope.items.length ||
          collected.length + envelope.returned_count > MAX_KNOWLEDGE_REVIEW_LIST_OFFSET
        ) {
          throw reviewPaginationError('Review pagination metadata is inconsistent');
        }

        for (const summary of envelope.items) {
          if (seenIdentities.has(summary.review_artifact_identity)) {
            throw reviewPaginationError('Review pagination returned a duplicate identity');
          }
          if (
            lastIdentity !== null &&
            summary.review_artifact_identity <= lastIdentity
          ) {
            throw reviewPaginationError('Review pagination order is not deterministic');
          }
          seenIdentities.add(summary.review_artifact_identity);
          lastIdentity = summary.review_artifact_identity;
          collected.push(reviewSummaryToQueueItem(summary));
        }

        listMetadata = {
          totalCount: expectedTotalCount,
          returnedCount: collected.length,
          truncated: collected.length < expectedTotalCount,
          nextOffset: envelope.next_offset
        };

        if (!envelope.truncated) {
          if (
            envelope.next_offset !== null ||
            collected.length !== expectedTotalCount
          ) {
            throw reviewPaginationError('Review pagination ended before the complete inbox');
          }
          break;
        }

        const nextOffset = envelope.next_offset;
        if (
          nextOffset === null ||
          nextOffset <= requestedOffset ||
          nextOffset !== requestedOffset + envelope.returned_count ||
          nextOffset !== collected.length ||
          nextOffset > MAX_KNOWLEDGE_REVIEW_LIST_OFFSET
        ) {
          throw reviewPaginationError('Review pagination continuation is invalid');
        }
        requestedOffset = nextOffset;
      }
    } catch (error) {
      if (currentListGeneration !== listGeneration) return false;
      if (snapshot !== null) reviewSnapshot.set(snapshot);
      const partialQueue =
        snapshot === null ? Object.freeze([...collected]) : applySnapshot(collected, snapshot);
      reviewQueue.set(partialQueue);
      listMetadata = {
        totalCount: expectedTotalCount ?? collected.length,
        returnedCount: collected.length,
        truncated: (expectedTotalCount ?? collected.length) > collected.length,
        nextOffset:
          expectedTotalCount !== null && collected.length < expectedTotalCount
            ? requestedOffset
            : null
      };
      setError(error, options.refresh ? 'refresh' : 'list');
      return false;
    }
    if (currentListGeneration !== listGeneration || snapshot === null) return false;

    appendActivity(
      options.refresh ? 'INBOX_REFRESH' : 'SIDECAR_RECONNECT',
      options.refresh ? 'review.activity.inbox_refresh' : 'review.activity.connected'
    );
    reviewSnapshot.set(snapshot);
    listMetadata = {
      totalCount: expectedTotalCount ?? collected.length,
      returnedCount: collected.length,
      truncated: false,
      nextOffset: null
    };
    const queue = applySnapshot(collected, snapshot);
    reviewQueue.set(queue);
    if (queue.length === 0) {
      reviewCenterState.set({
        status: 'empty',
        source: 'LOCAL_CONTROL_PLANE',
        error: null,
        failedRequest: null,
        retryable: false,
        ...listMetadata
      });
      return true;
    }

    const selectedIdentity =
      previousSelectedIdentity !== null &&
      queue.some((item) => item.reviewArtifactIdentity === previousSelectedIdentity)
        ? previousSelectedIdentity
        : queue[0].reviewArtifactIdentity;
    selectedReviewId.set(selectedIdentity);
    return loadRealReview(selectedIdentity, currentListGeneration, ++getGeneration);
  }

  async function loadRealReview(
    reviewArtifactIdentity: string,
    expectedListGeneration: number,
    expectedGetGeneration: number
  ): Promise<boolean> {
    let envelope;
    try {
      envelope = await client.get(reviewArtifactIdentity);
    } catch (error) {
      if (
        expectedListGeneration !== listGeneration ||
        expectedGetGeneration !== getGeneration ||
        get(selectedReviewId) !== reviewArtifactIdentity
      ) {
        return false;
      }
      selectedReview.set(null);
      setError(error, 'get');
      return false;
    }
    if (
      expectedListGeneration !== listGeneration ||
      expectedGetGeneration !== getGeneration ||
      get(selectedReviewId) !== reviewArtifactIdentity
    ) {
      return false;
    }
    if (envelope.projection.review_artifact_identity !== reviewArtifactIdentity) {
      selectedReview.set(null);
      setError(
        Object.freeze({ code: 'invalid_payload', message: 'Review get identity mismatch' }),
        'get'
      );
      return false;
    }
    const realReview = applySelectedFreshness(
      reviewProjectionToCenterItem(envelope),
      get(reviewSnapshot)
    );
    selectedReview.set(realReview);
    reviewCenterState.set({
      status: 'ready',
      source: 'LOCAL_CONTROL_PLANE',
      error: null,
      failedRequest: null,
      retryable: false,
      ...listMetadata
    });
    appendActivity(
      realReview.stale === true ? 'STALE_REVIEW' : 'ARTIFACT_OPENED',
      realReview.stale === true
        ? 'review.activity.stale_review'
        : 'review.activity.artifact_opened',
      reviewArtifactIdentity
    );
    return true;
  }

  function selectReview(reviewId: string): boolean {
    const queueItem = get(reviewQueue).find((review) => review.id === reviewId);
    if (!queueItem) return false;
    selectedReviewId.set(reviewId);
    decisionResult.set(null);
    closeDecisionDialog();
    selectedReview.set(null);
    setLoading('get');
    void loadRealReview(reviewId, listGeneration, ++getGeneration);
    return true;
  }

  function moveReviewSelection(delta: -1 | 1): string | null {
    const reviews = get(filteredReviewQueue);
    if (reviews.length === 0) return null;
    const currentId = get(selectedReviewId);
    const currentIndex = Math.max(0, reviews.findIndex((review) => review.id === currentId));
    const nextIndex = (currentIndex + delta + reviews.length) % reviews.length;
    const nextId = reviews[nextIndex].id;
    selectReview(nextId);
    return nextId;
  }

  function selectReviewBoundary(boundary: 'first' | 'last'): string | null {
    const reviews = get(filteredReviewQueue);
    if (reviews.length === 0) return null;
    const target = boundary === 'first' ? reviews[0] : reviews[reviews.length - 1];
    selectReview(target.id);
    return target.id;
  }

  async function refreshReviewCenter(): Promise<boolean> {
    return loadReviewCenter({ refresh: true });
  }

  async function retryReviewCenter(): Promise<boolean> {
    const state = get(reviewCenterState);
    if (state.status !== 'error' || !state.retryable) return false;
    if (state.failedRequest === 'list' || state.failedRequest === 'snapshot') {
      return loadReviewCenter();
    }
    if (state.failedRequest === 'refresh') return loadReviewCenter({ refresh: true });
    if (state.failedRequest !== 'get') return false;
    const reviewId = get(selectedReviewId);
    if (!reviewId) return false;
    setLoading('get');
    return loadRealReview(reviewId, listGeneration, ++getGeneration);
  }

  function openDecisionDialog(review: ReviewCenterItem, intent: DecisionIntent): boolean {
    decisionResult.set(null);
    if (intent === 'APPROVE' && review.status === 'BLOCKED') {
      decisionDialog.set({ ...INITIAL_DIALOG, errorKey: 'review.decision.blocked_approval' });
      return false;
    }
    if (review.fixture === false && review.stale !== false) {
      decisionDialog.set({
        ...INITIAL_DIALOG,
        errorKey:
          review.stale === true
            ? 'review.decision.stale'
            : 'review.decision.freshness_unknown'
      });
      return false;
    }
    decisionDialog.set({
      ...INITIAL_DIALOG,
      open: true,
      intent
    });
    return true;
  }

  function closeDecisionDialog(): void {
    decisionDialog.set(INITIAL_DIALOG);
  }

  function setDecisionComment(rawComment: string): void {
    const comment = rawComment.slice(0, MAX_REVIEW_COMMENT_LENGTH);
    decisionDialog.update((state) => ({ ...state, comment, errorKey: null }));
  }

  function setDecisionActorIdentifier(rawValue: string): void {
    decisionDialog.update((state) => ({
      ...state,
      actorIdentifier: rawValue.slice(0, 256),
      errorKey: null
    }));
  }

  function setDecisionActorDisplayName(rawValue: string): void {
    decisionDialog.update((state) => ({
      ...state,
      actorDisplayName: rawValue.slice(0, 256),
      errorKey: null
    }));
  }

  function validateDialog(review: ReviewCenterItem, state: DecisionDialogState): string | null {
    if (!state.open || state.intent === null) return 'review.decision.unavailable';
    if (state.intent === 'APPROVE' && review.status === 'BLOCKED') {
      return 'review.decision.blocked_approval';
    }
    if (review.fixture === false && review.stale !== false) {
      return review.stale === true
        ? 'review.decision.stale'
        : 'review.decision.freshness_unknown';
    }
    if (state.intent === 'REQUEST_CHANGES' && state.comment.trim().length === 0) {
      return 'review.decision.comment_required';
    }
    if (
      state.actorIdentifier.trim().length === 0 ||
      state.actorDisplayName.trim().length === 0
    ) {
      return 'review.decision.actor_required';
    }
    return null;
  }

  function confirmFixtureDecision(review: ReviewCenterItem): boolean {
    if (review.fixture !== true) return false;
    const state = get(decisionDialog);
    const errorKey = validateDialog(review, state);
    if (errorKey) {
      decisionDialog.update((current) => ({ ...current, errorKey }));
      return false;
    }
    const result: FixtureDecisionResult = Object.freeze({
      fixture: true,
      hardStop: true,
      proposalId: review.proposalId,
      reviewArtifactIdentity: review.reviewArtifactIdentity,
      intent: state.intent as DecisionIntent,
      comment: state.comment,
      messageKey: 'review.decision.fixture_hard_stop'
    });
    decisionResult.set(result);
    closeDecisionDialog();
    return true;
  }

  async function confirmDecision(review: ReviewCenterItem): Promise<boolean> {
    if (review.fixture) return confirmFixtureDecision(review);
    const state = get(decisionDialog);
    const errorKey = validateDialog(review, state);
    if (errorKey) {
      decisionDialog.update((current) => ({ ...current, errorKey }));
      return false;
    }
    const generation = ++decisionGeneration;
    decisionDialog.update((current) => ({ ...current, submitting: true, errorKey: null }));
    try {
      const envelope = await client.createDecision({
        reviewContractVersion: KNOWLEDGE_CHANGE_REVIEW_CONTRACT,
        proposalId: review.proposalId,
        reviewArtifactIdentity: review.reviewArtifactIdentity,
        changeIdentity: review.changeIdentity,
        observedVaultRevision: review.observedVaultRevision,
        decision: state.intent as DecisionIntent,
        comment: state.comment,
        actorIdentifier: state.actorIdentifier,
        actorDisplayName: state.actorDisplayName,
        actorSource: KNOWLEDGE_REVIEW_ACTOR_SOURCE
      });
      if (
        generation !== decisionGeneration ||
        get(selectedReviewId) !== review.reviewArtifactIdentity
      ) {
        return false;
      }
      const result: RealDecisionResult = Object.freeze({
        fixture: false,
        hardStop: true,
        duplicate: envelope.duplicate,
        vaultModified: false,
        persistence: false,
        publication: false,
        currentVaultRevision: envelope.current_vault_revision,
        decision: envelope.decision,
        messageKey: 'review.decision.real_hard_stop'
      });
      decisionResult.set(result);
      appendActivity(
        'DECISION_CREATED',
        'review.activity.decision_created',
        review.reviewArtifactIdentity
      );
      closeDecisionDialog();
      try {
        const snapshot = await client.snapshot();
        if (generation === decisionGeneration) reviewSnapshot.set(snapshot);
      } catch (snapshotError) {
        const normalizedSnapshotError = normalizeKnowledgeReviewError(snapshotError);
        appendActivity(
          'ERROR',
          'review.activity.snapshot_refresh_failed',
          review.reviewArtifactIdentity,
          normalizedSnapshotError.code
        );
      }
      return true;
    } catch (error) {
      if (generation !== decisionGeneration) return false;
      const normalized = normalizeKnowledgeReviewError(error);
      decisionDialog.update((current) => ({
        ...current,
        submitting: false,
        errorKey:
          normalized.code === 'policy_blocked'
            ? 'review.decision.policy_blocked'
            : 'review.decision.failed'
      }));
      appendActivity(
        'ERROR',
        'review.activity.error',
        review.reviewArtifactIdentity,
        normalized.code
      );
      return false;
    }
  }

  function handleDecisionDialogEscape(key: string): boolean {
    if (key !== 'Escape' || !get(decisionDialog).open || get(decisionDialog).submitting) {
      return false;
    }
    closeDecisionDialog();
    return true;
  }

  function setReviewQuery(query: string): void {
    reviewFilters.update((state) => ({ ...state, query: query.slice(0, 200) }));
  }

  function toggleReviewStatus(status: ReviewStatus): void {
    reviewFilters.update((state) => {
      const next = state.statuses.includes(status)
        ? state.statuses.filter((item) => item !== status)
        : [...state.statuses, status];
      return { ...state, statuses: Object.freeze(next) };
    });
  }

  function toggleReviewOperation(operation: ReviewOperation): void {
    reviewFilters.update((state) => {
      const next = state.operations.includes(operation)
        ? state.operations.filter((item) => item !== operation)
        : [...state.operations, operation];
      return { ...state, operations: Object.freeze(next) };
    });
  }

  function setReviewSort(sort: ReviewFilterState['sort']): void {
    reviewFilters.update((state) => ({ ...state, sort }));
  }

  function clearReviewFilters(): void {
    reviewFilters.set(INITIAL_FILTERS);
  }

  function resetReviewCenterStore(): void {
    listGeneration += 1;
    getGeneration += 1;
    decisionGeneration += 1;
    activitySequence = 0;
    listMetadata = { totalCount: 0, returnedCount: 0, truncated: false, nextOffset: null };
    reviewCenterState.set(INITIAL_REVIEW_CENTER_STATE);
    reviewQueue.set([]);
    selectedReviewId.set(null);
    selectedReview.set(null);
    reviewSnapshot.set(null);
    decisionDialog.set(INITIAL_DIALOG);
    decisionResult.set(null);
    reviewFilters.set(INITIAL_FILTERS);
    reviewActivity.set([]);
  }

  return {
    reviewCenterState,
    reviewQueue,
    filteredReviewQueue,
    selectedReviewId,
    selectedReview,
    reviewSnapshot,
    reviewDiagnostics,
    reviewFilters,
    reviewActivity,
    decisionDialog,
    decisionResult,
    fixtureDecisionResult,
    realDecisionResult,
    loadReviewCenter,
    refreshReviewCenter,
    retryReviewCenter,
    selectReview,
    moveReviewSelection,
    selectReviewBoundary,
    openDecisionDialog,
    closeDecisionDialog,
    setDecisionComment,
    setDecisionActorIdentifier,
    setDecisionActorDisplayName,
    confirmFixtureDecision,
    confirmDecision,
    handleDecisionDialogEscape,
    setReviewQuery,
    toggleReviewStatus,
    toggleReviewOperation,
    setReviewSort,
    clearReviewFilters,
    resetReviewCenterStore
  };
}


function reviewPaginationError(message: string): Readonly<{ code: string; message: string }> {
  return Object.freeze({
    code: 'invalid_payload',
    message: message.slice(0, 240)
  });
}

function filterAndSortQueue(
  queue: readonly ReviewQueueItem[],
  filters: ReviewFilterState
): readonly ReviewQueueItem[] {
  const query = filters.query.trim().toLowerCase();
  const filtered = queue.filter((item) => {
    if (filters.statuses.length > 0 && !filters.statuses.includes(item.status)) return false;
    if (filters.operations.length > 0 && !filters.operations.includes(item.operation)) return false;
    if (!query) return true;
    return [
      item.proposalId,
      item.reviewArtifactIdentity,
      item.changeIdentity ?? '',
      item.targetStableId,
      item.operation,
      item.status
    ].some((value) => value.toLowerCase().includes(query));
  });
  filtered.sort((left, right) => {
    if (filters.sort === 'STATUS_THEN_IDENTITY') {
      const statusDifference = STATUS_ORDER[left.status] - STATUS_ORDER[right.status];
      if (statusDifference !== 0) return statusDifference;
    }
    if (left.reviewArtifactIdentity < right.reviewArtifactIdentity) return -1;
    if (left.reviewArtifactIdentity > right.reviewArtifactIdentity) return 1;
    return 0;
  });
  return Object.freeze(filtered);
}

const productionReviewCenter = createReviewCenterController();

function isTransientReviewError(code: string): boolean {
  return ['busy', 'sidecar_shutdown', 'sidecar_unavailable', 'timeout'].includes(code);
}

export const reviewCenterState = productionReviewCenter.reviewCenterState;
export const reviewQueue = productionReviewCenter.reviewQueue;
export const filteredReviewQueue = productionReviewCenter.filteredReviewQueue;
export const selectedReviewId = productionReviewCenter.selectedReviewId;
export const selectedReview = productionReviewCenter.selectedReview;
export const reviewSnapshot = productionReviewCenter.reviewSnapshot;
export const reviewDiagnostics = productionReviewCenter.reviewDiagnostics;
export const reviewFilters = productionReviewCenter.reviewFilters;
export const reviewActivity = productionReviewCenter.reviewActivity;
export const decisionDialog = productionReviewCenter.decisionDialog;
export const decisionResult = productionReviewCenter.decisionResult;
export const fixtureDecisionResult = productionReviewCenter.fixtureDecisionResult;
export const realDecisionResult = productionReviewCenter.realDecisionResult;
export const loadReviewCenter = productionReviewCenter.loadReviewCenter;
export const refreshReviewCenter = productionReviewCenter.refreshReviewCenter;
export const retryReviewCenter = productionReviewCenter.retryReviewCenter;
export const selectReview = productionReviewCenter.selectReview;
export const moveReviewSelection = productionReviewCenter.moveReviewSelection;
export const selectReviewBoundary = productionReviewCenter.selectReviewBoundary;
export const openDecisionDialog = productionReviewCenter.openDecisionDialog;
export const closeDecisionDialog = productionReviewCenter.closeDecisionDialog;
export const setDecisionComment = productionReviewCenter.setDecisionComment;
export const setDecisionActorIdentifier = productionReviewCenter.setDecisionActorIdentifier;
export const setDecisionActorDisplayName = productionReviewCenter.setDecisionActorDisplayName;
export const confirmFixtureDecision = productionReviewCenter.confirmFixtureDecision;
export const confirmDecision = productionReviewCenter.confirmDecision;
export const handleDecisionDialogEscape = productionReviewCenter.handleDecisionDialogEscape;
export const setReviewQuery = productionReviewCenter.setReviewQuery;
export const toggleReviewStatus = productionReviewCenter.toggleReviewStatus;
export const toggleReviewOperation = productionReviewCenter.toggleReviewOperation;
export const setReviewSort = productionReviewCenter.setReviewSort;
export const clearReviewFilters = productionReviewCenter.clearReviewFilters;
export const resetReviewCenterStore = productionReviewCenter.resetReviewCenterStore;

export function cycleDialogFocusIndex(
  currentIndex: number,
  focusableCount: number,
  shiftKey: boolean
): number {
  if (!Number.isInteger(focusableCount) || focusableCount <= 0) return -1;
  const boundedCurrent = Number.isInteger(currentIndex) && currentIndex >= 0
    ? currentIndex % focusableCount
    : 0;
  return shiftKey
    ? (boundedCurrent - 1 + focusableCount) % focusableCount
    : (boundedCurrent + 1) % focusableCount;
}
