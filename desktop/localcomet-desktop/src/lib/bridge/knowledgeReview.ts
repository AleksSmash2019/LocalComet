import { invoke } from '@tauri-apps/api/core';
import type {
  BoundedFindingDetailsProjection,
  BoundedReviewFindingsProjection,
  BoundedSourceValidationFindingsProjection,
  BoundedStringCollectionProjection,
  BoundedTextPreviewProjection,
  ConflictSeverity,
  DiffProjection,
  HumanReviewDecisionProjection,
  KnowledgeChangeReviewProjection,
  KnowledgeReviewDecisionCreateEnvelope,
  KnowledgeReviewDecisionRequest,
  KnowledgeReviewGetEnvelope,
  KnowledgeReviewListEnvelope,
  KnowledgeReviewSnapshotEnvelope,
  KnowledgeReviewStateProjection,
  KnowledgeReviewSummaryProjection,
  LineEndingProfileProjection,
  ProposedBodyProjection,
  ProposedContentProjection,
  RealReviewCenterItem,
  RepresentationDeltaProjection,
  ReviewCenterError,
  ReviewOperation,
  ReviewQueueItem,
  ReviewStatus,
  ValidationSnapshotProjection,
  ValidationValueProjection
} from '$lib/types/knowledgeReview';

export const KNOWLEDGE_REVIEW_LIST_CONTRACT = 'localcomet.knowledge-review-list/1.0';
export const KNOWLEDGE_REVIEW_GET_CONTRACT = 'localcomet.knowledge-review-get/1.0';
export const KNOWLEDGE_REVIEW_SNAPSHOT_CONTRACT = 'localcomet.knowledge-review-snapshot/1.0';
export const KNOWLEDGE_REVIEW_REFRESH_CONTRACT = 'localcomet.knowledge-review-refresh/1.0';
export const KNOWLEDGE_REVIEW_DECISION_CREATE_CONTRACT =
  'localcomet.knowledge-review-decision-create/1.0';
export const KNOWLEDGE_REVIEW_PROJECTION_CONTRACT = 'localcomet.knowledge-review-ui/1.0';
export const KNOWLEDGE_CHANGE_REVIEW_CONTRACT = 'localcomet.knowledge-change-review/1.0';
export const HUMAN_REVIEW_DECISION_CONTRACT =
  'localcomet.knowledge-change-review-decision/1.0';
export const KNOWLEDGE_OPERATIONS_COMMAND_CENTER_VERSION = 'v6.84.6';
export const KNOWLEDGE_REVIEW_ACTOR_SOURCE = 'LOCALCOMET_REVIEW_CENTER';
export const KNOWLEDGE_REVIEW_SOURCE = 'LOCAL_CONTROL_PLANE';
export const KNOWLEDGE_REVIEW_LIST_OFFSET = 0;
export const KNOWLEDGE_REVIEW_LIST_LIMIT = 50;
export const MAX_KNOWLEDGE_REVIEW_LIST_LIMIT = 50;
export const MAX_KNOWLEDGE_REVIEW_LIST_OFFSET = 128;
export const MAX_KNOWLEDGE_REVIEW_RESPONSE_BYTES = 1_048_576;
export const MAX_KNOWLEDGE_REVIEW_PROJECTION_BYTES = 262_144;

const MAX_GENERAL_STRING_BYTES = 32_768;
const MAX_COLLECTION_ITEMS = 128;
const MAX_VALIDATION_DEPTH = 16;
const MAX_VALIDATION_NODES = 1_024;
const MAX_VALIDATION_ITEMS = 128;
const MAX_FINDINGS = 16;
const MAX_FINDING_DETAILS = 16;
const MAX_SOURCE_FINDINGS = 128;
const REVIEW_STATUSES = ['CLEAR', 'REVIEW_REQUIRED', 'BLOCKED'] as const;
const REVIEW_OPERATIONS = [
  'UPDATE_EXISTING',
  'CREATE_NEW',
  'DELETE',
  'MOVE',
  'RENAME',
  'SUPERSEDE'
] as const;
const VALIDATION_OUTCOMES = ['VALID', 'INVALID', 'STALE'] as const;
const CONFLICT_SEVERITIES = ['BLOCKING', 'REVIEW'] as const;
const VALIDATION_TYPE_TAGS = ['mapping', 'sequence', 'null', 'bool', 'int', 'string'] as const;

const SHA256_RE = /^sha256:[0-9a-f]{64}$/;
const PROPOSAL_ID_RE = /^kprop:[0-9a-f]{64}$/;
const REVIEW_ID_RE = /^kreview:[0-9a-f]{64}$/;
const CHANGE_ID_RE = /^kchange:[0-9a-f]{64}$/;
const DECISION_ID_RE = /^kdecision:[0-9a-f]{64}$/;
const STABLE_ID_RE = /^[a-z0-9]+(?:[._-][a-z0-9]+)*$/;
const WINDOWS_DRIVE_RE = /^[A-Za-z]:/;
const textEncoder = new TextEncoder();

type JsonRecord = Readonly<Record<string, unknown>>;

export interface KnowledgeReviewClient {
  list(offset: number, limit: number): Promise<KnowledgeReviewListEnvelope>;
  get(reviewArtifactIdentity: string): Promise<KnowledgeReviewGetEnvelope>;
  snapshot(): Promise<KnowledgeReviewSnapshotEnvelope>;
  refresh(): Promise<KnowledgeReviewSnapshotEnvelope>;
  createDecision(
    request: KnowledgeReviewDecisionRequest
  ): Promise<KnowledgeReviewDecisionCreateEnvelope>;
}

export async function listKnowledgeReviews(
  offset = KNOWLEDGE_REVIEW_LIST_OFFSET,
  limit = KNOWLEDGE_REVIEW_LIST_LIMIT
): Promise<KnowledgeReviewListEnvelope> {
  ensureListRequest(offset, limit);
  let raw: unknown;
  try {
    raw = await invoke<unknown>('knowledge_review_list', { offset, limit });
  } catch (error) {
    throw normalizeKnowledgeReviewError(error);
  }
  const serialized = serializeBounded(
    raw,
    MAX_KNOWLEDGE_REVIEW_RESPONSE_BYTES,
    'Review list response exceeds its byte limit'
  );
  validateListEnvelope(raw, offset, limit);
  return deepFreeze(JSON.parse(serialized) as KnowledgeReviewListEnvelope);
}

export async function getKnowledgeReview(
  reviewArtifactIdentity: string
): Promise<KnowledgeReviewGetEnvelope> {
  ensureReviewIdentity(reviewArtifactIdentity);
  let raw: unknown;
  try {
    raw = await invoke<unknown>('knowledge_review_get', { reviewArtifactIdentity });
  } catch (error) {
    throw normalizeKnowledgeReviewError(error);
  }
  const serialized = serializeBounded(
    raw,
    MAX_KNOWLEDGE_REVIEW_RESPONSE_BYTES,
    'Review get response exceeds its byte limit'
  );
  validateGetEnvelope(raw, reviewArtifactIdentity);
  return deepFreeze(JSON.parse(serialized) as KnowledgeReviewGetEnvelope);
}

export async function getKnowledgeReviewSnapshot(): Promise<KnowledgeReviewSnapshotEnvelope> {
  return invokeSnapshot('knowledge_review_snapshot', false);
}

export async function refreshKnowledgeReviews(): Promise<KnowledgeReviewSnapshotEnvelope> {
  return invokeSnapshot('knowledge_review_refresh', true);
}

async function invokeSnapshot(
  command: 'knowledge_review_snapshot' | 'knowledge_review_refresh',
  refreshRequested: boolean
): Promise<KnowledgeReviewSnapshotEnvelope> {
  let raw: unknown;
  try {
    raw = await invoke<unknown>(command);
  } catch (error) {
    throw normalizeKnowledgeReviewError(error);
  }
  const serialized = serializeBounded(
    raw,
    MAX_KNOWLEDGE_REVIEW_RESPONSE_BYTES,
    'Review snapshot response exceeds its byte limit'
  );
  validateSnapshotEnvelope(raw, refreshRequested);
  return deepFreeze(JSON.parse(serialized) as KnowledgeReviewSnapshotEnvelope);
}

export async function createKnowledgeReviewDecision(
  request: KnowledgeReviewDecisionRequest
): Promise<KnowledgeReviewDecisionCreateEnvelope> {
  validateDecisionRequest(request);
  let raw: unknown;
  try {
    raw = await invoke<unknown>('knowledge_review_decision_create', {
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
    });
  } catch (error) {
    throw normalizeKnowledgeReviewError(error);
  }
  const serialized = serializeBounded(
    raw,
    MAX_KNOWLEDGE_REVIEW_RESPONSE_BYTES,
    'Review decision response exceeds its byte limit'
  );
  validateDecisionCreateEnvelope(raw, request);
  return deepFreeze(JSON.parse(serialized) as KnowledgeReviewDecisionCreateEnvelope);
}

export const knowledgeReviewClient: KnowledgeReviewClient = Object.freeze({
  list: listKnowledgeReviews,
  get: getKnowledgeReview,
  snapshot: getKnowledgeReviewSnapshot,
  refresh: refreshKnowledgeReviews,
  createDecision: createKnowledgeReviewDecision
});

export function reviewSummaryToQueueItem(
  summary: KnowledgeReviewSummaryProjection
): ReviewQueueItem {
  return Object.freeze({
    id: summary.review_artifact_identity,
    fixture: false,
    source: KNOWLEDGE_REVIEW_SOURCE,
    status: summary.status,
    blocked: summary.blocked,
    proposalId: summary.proposal_id,
    targetStableId: summary.target_stable_id,
    operation: summary.operation,
    expectedVaultRevision: summary.expected_vault_revision,
    observedVaultRevision: summary.observed_vault_revision,
    reviewArtifactIdentity: summary.review_artifact_identity,
    changeIdentity: summary.change_identity,
    findingCount: summary.finding_count,
    normalChangeMaterialPresent: summary.normal_change_material_present,
    detailProjectionTruncated: summary.detail_projection_truncated,
    stale: null
  });
}

export function reviewProjectionToCenterItem(
  envelope: KnowledgeReviewGetEnvelope
): RealReviewCenterItem {
  const projection = envelope.projection;
  const snapshotText = formatValidationSnapshot(projection.validation_snapshot.value);
  const boundedSnapshot = snapshotText.slice(0, 8_192);
  const snapshotRoot = projection.validation_snapshot.value;
  const validationContract = validationScalar(snapshotRoot, 'contract_version');
  const validationContentHash = validationScalar(snapshotRoot, 'proposal_content_hash');
  const validatedRevision = validationScalar(snapshotRoot, 'validated_vault_revision');

  return deepFreeze({
    id: projection.review_artifact_identity,
    fixture: false,
    source: KNOWLEDGE_REVIEW_SOURCE,
    detailProjectionTruncated: hasTruncatedReviewDetail(projection),
    stale: null,
    status: projection.status,
    proposalId: projection.proposal_id,
    proposalContentHash: projection.proposal_content_hash,
    reviewArtifactIdentity: projection.review_artifact_identity,
    changeIdentity: projection.change_identity,
    operation: projection.operation,
    targetStableId: projection.target_stable_id,
    expectedVaultRevision: projection.expected_vault_revision,
    observedVaultRevision: projection.observed_vault_revision,
    validation: {
      outcome: projection.validation_outcome,
      contractVersion: typeof validationContract === 'string'
        ? validationContract
        : projection.contract_version,
      proposalContentHash: typeof validationContentHash === 'string'
        ? validationContentHash
        : projection.proposal_content_hash,
      validatedVaultRevision: typeof validatedRevision === 'string'
        ? validatedRevision
        : projection.observed_vault_revision,
      sourceFindings: projection.source_validation_findings.items.map(
        (finding) => [finding.code, finding.severity] as const
      ),
      snapshotTruncated:
        projection.validation_snapshot.truncated || snapshotText.length > boundedSnapshot.length,
      snapshotSummary: boundedSnapshot
    },
    findings: projection.findings.items.map((finding) => ({
      code: finding.code,
      severity: finding.severity,
      message: finding.message.preview_text,
      details: finding.details.items.map((detail) => [detail.key, detail.value] as const)
    })),
    proposedContent: {
      title: projection.proposed_content_snapshot.title,
      body_text: projection.proposed_content_snapshot.body_text.preview_text,
      type: projection.proposed_content_snapshot.type,
      status: projection.proposed_content_snapshot.status,
      knowledge_layer: projection.proposed_content_snapshot.knowledge_layer,
      evidence_class: projection.proposed_content_snapshot.evidence_class,
      authority: projection.proposed_content_snapshot.authority,
      canonical: projection.proposed_content_snapshot.canonical,
      canonical_scope: projection.proposed_content_snapshot.canonical_scope,
      aliases: projection.proposed_content_snapshot.aliases.items,
      releases: projection.proposed_content_snapshot.releases.items,
      source_paths: projection.proposed_content_snapshot.source_paths.items,
      evidence_refs: projection.proposed_content_snapshot.evidence_refs.items,
      supersedes: projection.proposed_content_snapshot.supersedes.items,
      superseded_by: projection.proposed_content_snapshot.superseded_by.items,
      updated: projection.proposed_content_snapshot.updated,
      last_reviewed: projection.proposed_content_snapshot.last_reviewed,
      verified_at: projection.proposed_content_snapshot.verified_at
    },
    metadataChanges: [],
    beforeSourceByteHash: projection.before_source_byte_hash,
    beforeTextRawHash: projection.before_text_raw_hash,
    beforeSemanticTextHash: projection.before_semantic_text_hash,
    proposedTextRawHash: projection.proposed_text_raw_hash,
    proposedSemanticTextHash: projection.proposed_semantic_text_hash,
    textDiff: projection.diff === null
      ? {
          preview: null,
          previewTruncated: false,
          fullDiffAvailable: false,
          fullDiffHash: null,
          fullDiffUtf8Bytes: null
        }
      : {
          preview: projection.diff.preview.preview_text,
          previewTruncated: projection.diff.preview_truncated,
          fullDiffAvailable: projection.diff.full_diff_present,
          fullDiffHash: projection.diff.full_diff_hash,
          fullDiffUtf8Bytes: projection.diff.full_diff_utf8_bytes
        },
    representationDelta: projection.representation_delta === null
      ? null
      : {
          identity: projection.representation_delta.identity,
          beforePresent: projection.representation_delta.before_present,
          afterPresent: projection.representation_delta.after_present,
          beforeLineEndings: projection.representation_delta.before_line_endings === null
            ? null
            : lineEndingView(projection.representation_delta.before_line_endings),
          afterLineEndings: lineEndingView(projection.representation_delta.after_line_endings),
          terminalNewlineChanged: projection.representation_delta.terminal_newline_changed,
          afterSourceBytesKnown: projection.representation_delta.after_source_bytes_known,
          sourceBytesChangedTextIdentical:
            projection.representation_delta.source_bytes_changed_text_identical,
          rawTextChangedSemanticEqual:
            projection.representation_delta.raw_text_changed_semantic_equal,
          semanticContentChanged: projection.representation_delta.semantic_content_changed
        },
    humanReviewPreview: {
      text: projection.human_review_preview.preview_text,
      truncated: projection.human_review_preview.truncated
    },
    rawProjection: projection
  });
}

export function normalizeKnowledgeReviewError(error: unknown): ReviewCenterError {
  if (isRecord(error)) {
    const code = typeof error.code === 'string' ? error.code : 'review_bridge_error';
    const message = typeof error.message === 'string'
      ? error.message
      : 'Knowledge review bridge error';
    return Object.freeze({
      code: boundedSanitized(code, 64),
      message: boundedSanitized(message, 240)
    });
  }
  return Object.freeze({
    code: 'review_bridge_error',
    message: 'Knowledge review bridge error'
  });
}

function validateSnapshotEnvelope(value: unknown, refreshRequested: boolean): void {
  const object = exactRecord(value, [
    'contract',
    'command_center_version',
    'control_plane_version',
    'sidecar_runtime_version',
    'source',
    'fixture',
    'refresh_requested',
    'refresh_succeeded',
    'current_vault_revision',
    'freshness_known',
    'knowledge_state',
    'last_error_code',
    'inbox_count',
    'stale_count',
    'blocked_count',
    'session_decision_count',
    'review_states',
    'hard_stop',
    'persistence',
    'vault_write_authority',
    'publication_authority'
  ], 'review snapshot envelope');
  const expectedContract = refreshRequested
    ? KNOWLEDGE_REVIEW_REFRESH_CONTRACT
    : KNOWLEDGE_REVIEW_SNAPSHOT_CONTRACT;
  if (object.contract !== expectedContract) invalid('Wrong review snapshot contract');
  if (object.command_center_version !== KNOWLEDGE_OPERATIONS_COMMAND_CENTER_VERSION) {
    invalid('Wrong command center version');
  }
  boundedString(object.control_plane_version, 'control plane version', 64);
  boundedString(object.sidecar_runtime_version, 'sidecar runtime version', 64);
  if (object.source !== KNOWLEDGE_REVIEW_SOURCE || object.fixture !== false) {
    invalid('Wrong review snapshot source');
  }
  if (object.refresh_requested !== refreshRequested) {
    invalid('Review snapshot refresh binding mismatch');
  }
  const refreshSucceeded = booleanValue(object.refresh_succeeded, 'refresh success');
  if (!refreshRequested && refreshSucceeded) {
    invalid('Snapshot cannot report refresh success');
  }
  optionalPatternString(object.current_vault_revision, SHA256_RE, 'current Vault revision');
  const freshnessKnown = booleanValue(object.freshness_known, 'freshness known');
  if (freshnessKnown !== (object.current_vault_revision !== null)) {
    invalid('Freshness knowledge is inconsistent');
  }
  boundedString(object.knowledge_state, 'knowledge state', 64);
  optionalBoundedString(object.last_error_code, 'last error code', 64);
  const inboxCount = nonNegativeInteger(object.inbox_count, 'inbox count');
  const staleCount = nonNegativeInteger(object.stale_count, 'stale count');
  const blockedCount = nonNegativeInteger(object.blocked_count, 'blocked count');
  const decisionCount = nonNegativeInteger(
    object.session_decision_count,
    'session decision count'
  );
  if (
    inboxCount > MAX_KNOWLEDGE_REVIEW_LIST_OFFSET ||
    staleCount > inboxCount ||
    blockedCount > inboxCount ||
    decisionCount > MAX_KNOWLEDGE_REVIEW_LIST_OFFSET
  ) {
    invalid('Review snapshot counts exceed bounds');
  }
  const states = arrayValue(
    object.review_states,
    MAX_KNOWLEDGE_REVIEW_LIST_OFFSET,
    'review states'
  );
  if (states.length !== inboxCount) invalid('Review state count mismatch');
  const identities = new Set<string>();
  let observedStale = 0;
  let observedBlocked = 0;
  for (const stateValue of states) {
    const state = validateReviewState(stateValue);
    if (identities.has(state.review_artifact_identity)) {
      invalid('Duplicate review state identity');
    }
    identities.add(state.review_artifact_identity);
    if (state.stale === true) observedStale += 1;
    if (state.status === 'BLOCKED') observedBlocked += 1;
    if (!freshnessKnown && state.stale !== null) {
      invalid('Unknown freshness must use null stale state');
    }
  }
  if (observedStale !== staleCount || observedBlocked !== blockedCount) {
    invalid('Review snapshot aggregate counts are inconsistent');
  }
  if (
    object.hard_stop !== true ||
    object.persistence !== false ||
    object.vault_write_authority !== false ||
    object.publication_authority !== false
  ) {
    invalid('Review snapshot authority boundary mismatch');
  }
}

function validateReviewState(value: unknown): KnowledgeReviewStateProjection {
  const object = exactRecord(
    value,
    ['review_artifact_identity', 'status', 'stale'],
    'review freshness state'
  );
  patternString(object.review_artifact_identity, REVIEW_ID_RE, 'review identity');
  enumValue(object.status, REVIEW_STATUSES, 'review status');
  if (object.stale !== null && typeof object.stale !== 'boolean') {
    invalid('Review stale state must be boolean or null');
  }
  return object as unknown as KnowledgeReviewStateProjection;
}

function validateDecisionRequest(request: KnowledgeReviewDecisionRequest): void {
  const object = exactRecord(request, [
    'reviewContractVersion',
    'proposalId',
    'reviewArtifactIdentity',
    'changeIdentity',
    'observedVaultRevision',
    'decision',
    'comment',
    'actorIdentifier',
    'actorDisplayName',
    'actorSource'
  ], 'review decision request');
  if (object.reviewContractVersion !== KNOWLEDGE_CHANGE_REVIEW_CONTRACT) {
    invalid('Wrong review contract version');
  }
  patternString(object.proposalId, PROPOSAL_ID_RE, 'proposal identity');
  patternString(object.reviewArtifactIdentity, REVIEW_ID_RE, 'review identity');
  optionalPatternString(object.changeIdentity, CHANGE_ID_RE, 'change identity');
  patternString(object.observedVaultRevision, SHA256_RE, 'observed Vault revision');
  const decision = enumValue(
    object.decision,
    ['APPROVE', 'REJECT', 'REQUEST_CHANGES'] as const,
    'review decision'
  );
  const comment = boundedString(object.comment, 'review comment', 4_096);
  if (comment.length > 2_000) {
    invalid('Review comment exceeds its character bound');
  }
  if (decision === 'REQUEST_CHANGES' && comment.trim().length === 0) {
    invalid('Request changes requires a comment');
  }
  if (decision === 'APPROVE' && object.changeIdentity === null) {
    invalid('Approval requires a change identity');
  }
  const actorIdentifier = boundedString(
    object.actorIdentifier,
    'actor identifier',
    512
  );
  const actorDisplayName = boundedString(
    object.actorDisplayName,
    'actor display name',
    512
  );
  if (
    actorIdentifier.trim().length === 0 ||
    actorDisplayName.trim().length === 0 ||
    actorIdentifier.length > 256 ||
    actorDisplayName.length > 256
  ) {
    invalid('Reviewer metadata is invalid');
  }
  if (object.actorSource !== KNOWLEDGE_REVIEW_ACTOR_SOURCE) {
    invalid('Wrong reviewer source');
  }
}

function validateDecisionCreateEnvelope(
  value: unknown,
  request: KnowledgeReviewDecisionRequest
): void {
  const object = exactRecord(value, [
    'contract',
    'command_center_version',
    'control_plane_version',
    'sidecar_runtime_version',
    'source',
    'fixture',
    'duplicate',
    'current_vault_revision',
    'decision',
    'hard_stop',
    'vault_modified',
    'persistence',
    'publication'
  ], 'review decision envelope');
  if (object.contract !== KNOWLEDGE_REVIEW_DECISION_CREATE_CONTRACT) {
    invalid('Wrong review decision response contract');
  }
  if (object.command_center_version !== KNOWLEDGE_OPERATIONS_COMMAND_CENTER_VERSION) {
    invalid('Wrong command center version');
  }
  boundedString(object.control_plane_version, 'control plane version', 64);
  boundedString(object.sidecar_runtime_version, 'sidecar runtime version', 64);
  if (object.source !== KNOWLEDGE_REVIEW_SOURCE || object.fixture !== false) {
    invalid('Wrong review decision source');
  }
  booleanValue(object.duplicate, 'decision duplicate flag');
  patternString(object.current_vault_revision, SHA256_RE, 'current Vault revision');
  if (object.current_vault_revision !== request.observedVaultRevision) {
    invalid('Decision response is stale');
  }
  const decision = validateHumanReviewDecisionProjection(object.decision);
  if (
    decision.review_contract_version !== request.reviewContractVersion ||
    decision.proposal_id !== request.proposalId ||
    decision.review_artifact_identity !== request.reviewArtifactIdentity ||
    decision.change_identity !== request.changeIdentity ||
    decision.observed_vault_revision !== request.observedVaultRevision ||
    decision.decision !== request.decision ||
    decision.comment !== request.comment ||
    decision.actor.actor_identifier !== request.actorIdentifier ||
    decision.actor.display_name !== request.actorDisplayName ||
    decision.actor.source !== request.actorSource
  ) {
    invalid('Decision response binding mismatch');
  }
  if (
    object.hard_stop !== true ||
    object.vault_modified !== false ||
    object.persistence !== false ||
    object.publication !== false
  ) {
    invalid('Decision response authority boundary mismatch');
  }
}

function validateHumanReviewDecisionProjection(
  value: unknown
): HumanReviewDecisionProjection {
  const object = exactRecord(value, [
    'projection_contract',
    'kind',
    'contract_version',
    'review_contract_version',
    'review_status',
    'proposal_id',
    'review_artifact_identity',
    'change_identity',
    'observed_vault_revision',
    'decision',
    'comment',
    'actor',
    'decision_identity',
    'hard_stop',
    'review_decision_only',
    'actor_metadata_evidence_only',
    'human_identity_authenticated',
    'grants_write_authority',
    'grants_vault_write_authority',
    'grants_persistence_authority',
    'grants_publication_authority',
    'grants_merge_authority',
    'grants_rebase_authority',
    'grants_execution_authority',
    'grants_policy_authority',
    'grants_model_gateway_authority',
    'grants_tauri_frontend_authority',
    'grants_automatic_approval_authority'
  ], 'human review decision projection');
  if (
    object.projection_contract !== KNOWLEDGE_REVIEW_PROJECTION_CONTRACT ||
    object.kind !== 'HUMAN_REVIEW_DECISION' ||
    object.contract_version !== HUMAN_REVIEW_DECISION_CONTRACT ||
    object.review_contract_version !== KNOWLEDGE_CHANGE_REVIEW_CONTRACT
  ) {
    invalid('Wrong human review decision contract');
  }
  const status = enumValue(object.review_status, REVIEW_STATUSES, 'review status');
  patternString(object.proposal_id, PROPOSAL_ID_RE, 'proposal identity');
  patternString(object.review_artifact_identity, REVIEW_ID_RE, 'review identity');
  optionalPatternString(object.change_identity, CHANGE_ID_RE, 'change identity');
  patternString(object.observed_vault_revision, SHA256_RE, 'observed Vault revision');
  const decision = enumValue(
    object.decision,
    ['APPROVE', 'REJECT', 'REQUEST_CHANGES'] as const,
    'review decision'
  );
  const comment = boundedString(object.comment, 'review comment', 4_096);
  if (comment.length > 2_000) invalid('Review comment character limit exceeded');
  if (decision === 'REQUEST_CHANGES' && comment.trim().length === 0) {
    invalid('Request changes requires a comment');
  }
  if (status === 'BLOCKED' && decision === 'APPROVE') {
    invalid('BLOCKED review cannot be approved');
  }
  if (decision === 'APPROVE' && object.change_identity === null) {
    invalid('Approval requires a change identity');
  }
  const actor = exactRecord(
    object.actor,
    ['actor_identifier', 'display_name', 'source'],
    'reviewer metadata'
  );
  const actorIdentifier = boundedString(actor.actor_identifier, 'actor identifier', 512);
  const actorDisplayName = boundedString(actor.display_name, 'actor display name', 512);
  if (actorIdentifier.length > 256 || actorDisplayName.length > 256) {
    invalid('Reviewer metadata character limit exceeded');
  }
  if (actor.source !== KNOWLEDGE_REVIEW_ACTOR_SOURCE) {
    invalid('Wrong reviewer source');
  }
  patternString(object.decision_identity, DECISION_ID_RE, 'decision identity');
  const expectedTrue = [
    'hard_stop',
    'review_decision_only',
    'actor_metadata_evidence_only'
  ] as const;
  for (const key of expectedTrue) {
    if (object[key] !== true) invalid(`Decision ${key} boundary mismatch`);
  }
  const expectedFalse = [
    'human_identity_authenticated',
    'grants_write_authority',
    'grants_vault_write_authority',
    'grants_persistence_authority',
    'grants_publication_authority',
    'grants_merge_authority',
    'grants_rebase_authority',
    'grants_execution_authority',
    'grants_policy_authority',
    'grants_model_gateway_authority',
    'grants_tauri_frontend_authority',
    'grants_automatic_approval_authority'
  ] as const;
  for (const key of expectedFalse) {
    if (object[key] !== false) invalid(`Decision ${key} boundary mismatch`);
  }
  return object as unknown as HumanReviewDecisionProjection;
}

function ensureListRequest(offset: number, limit: number): void {
  if (!isSafeNonNegativeInteger(offset) || offset > MAX_KNOWLEDGE_REVIEW_LIST_OFFSET) {
    invalid('Review list offset is invalid');
  }
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > MAX_KNOWLEDGE_REVIEW_LIST_LIMIT) {
    invalid('Review list limit is invalid');
  }
}

function validateListEnvelope(value: unknown, requestedOffset: number, requestedLimit: number): void {
  const object = exactRecord(value, [
    'contract',
    'source',
    'fixture',
    'offset',
    'limit',
    'total_count',
    'returned_count',
    'truncated',
    'next_offset',
    'items'
  ], 'review list envelope');
  if (object.contract !== KNOWLEDGE_REVIEW_LIST_CONTRACT) invalid('Wrong review list contract');
  if (object.source !== KNOWLEDGE_REVIEW_SOURCE || object.fixture !== false) {
    invalid('Wrong review list source');
  }
  const offset = nonNegativeInteger(object.offset, 'review list offset');
  const limit = positiveInteger(object.limit, 'review list limit');
  const totalCount = nonNegativeInteger(object.total_count, 'review list total count');
  const returnedCount = nonNegativeInteger(object.returned_count, 'review list returned count');
  const truncated = booleanValue(object.truncated, 'review list truncation');
  if (offset !== requestedOffset || limit !== requestedLimit || limit > MAX_KNOWLEDGE_REVIEW_LIST_LIMIT) {
    invalid('Review list request binding mismatch');
  }
  const items = arrayValue(object.items, requestedLimit, 'review list items');
  if (
    totalCount > MAX_KNOWLEDGE_REVIEW_LIST_OFFSET ||
    returnedCount !== items.length ||
    returnedCount > limit ||
    (returnedCount > 0 && offset + returnedCount > totalCount)
  ) {
    invalid('Review list counts are inconsistent');
  }
  const expectedTruncated = offset + returnedCount < totalCount;
  if (truncated !== expectedTruncated) invalid('Review list truncation is inconsistent');
  if (truncated) {
    const nextOffset = nonNegativeInteger(object.next_offset, 'review list continuation');
    if (
      returnedCount === 0 ||
      nextOffset !== offset + returnedCount ||
      nextOffset > MAX_KNOWLEDGE_REVIEW_LIST_OFFSET
    ) {
      invalid('Review list continuation is invalid');
    }
  } else if (object.next_offset !== null) {
    invalid('Review list continuation must be null');
  }
  const identities = new Set<string>();
  for (const item of items) {
    const summary = validateSummary(item);
    if (identities.has(summary.review_artifact_identity)) {
      invalid('Duplicate review identity in list response');
    }
    identities.add(summary.review_artifact_identity);
  }
}

function validateSummary(value: unknown): KnowledgeReviewSummaryProjection {
  const object = exactRecord(value, [
    'projection_contract',
    'kind',
    'contract_version',
    'status',
    'blocked',
    'proposal_id',
    'target_stable_id',
    'operation',
    'expected_vault_revision',
    'observed_vault_revision',
    'review_artifact_identity',
    'change_identity',
    'finding_count',
    'normal_change_material_present',
    'detail_projection_truncated'
  ], 'review summary');
  if (object.projection_contract !== KNOWLEDGE_REVIEW_PROJECTION_CONTRACT) {
    invalid('Wrong review summary projection contract');
  }
  if (object.kind !== 'KNOWLEDGE_CHANGE_REVIEW_SUMMARY') {
    invalid('Wrong review summary projection kind');
  }
  if (object.contract_version !== KNOWLEDGE_CHANGE_REVIEW_CONTRACT) {
    invalid('Wrong knowledge review contract');
  }
  const status = enumValue(object.status, REVIEW_STATUSES, 'review status');
  const blocked = booleanValue(object.blocked, 'review blocked flag');
  if (blocked !== (status === 'BLOCKED')) invalid('Review blocked flag is inconsistent');
  patternString(object.proposal_id, PROPOSAL_ID_RE, 'proposal identity');
  stableId(object.target_stable_id);
  enumValue(object.operation, REVIEW_OPERATIONS, 'review operation');
  patternString(object.expected_vault_revision, SHA256_RE, 'expected Vault revision');
  patternString(object.observed_vault_revision, SHA256_RE, 'observed Vault revision');
  patternString(object.review_artifact_identity, REVIEW_ID_RE, 'review identity');
  optionalPatternString(object.change_identity, CHANGE_ID_RE, 'change identity');
  nonNegativeInteger(object.finding_count, 'finding count');
  const normalMaterial = booleanValue(
    object.normal_change_material_present,
    'normal change material flag'
  );
  booleanValue(object.detail_projection_truncated, 'detail projection truncation');
  if (blocked && (normalMaterial || object.change_identity !== null)) {
    invalid('BLOCKED summary exposes normal change material');
  }
  if (!blocked && (!normalMaterial || object.change_identity === null)) {
    invalid('Non-BLOCKED summary is missing normal change material');
  }
  return object as unknown as KnowledgeReviewSummaryProjection;
}

function validateGetEnvelope(value: unknown, requestedIdentity: string): void {
  const object = exactRecord(
    value,
    ['contract', 'source', 'fixture', 'projection'],
    'review get envelope'
  );
  if (object.contract !== KNOWLEDGE_REVIEW_GET_CONTRACT) invalid('Wrong review get contract');
  if (object.source !== KNOWLEDGE_REVIEW_SOURCE || object.fixture !== false) {
    invalid('Wrong review get source');
  }
  const projectionBytes = textEncoder.encode(
    serializeBounded(
      object.projection,
      MAX_KNOWLEDGE_REVIEW_PROJECTION_BYTES,
      'Review projection exceeds its byte limit'
    )
  ).length;
  if (projectionBytes > MAX_KNOWLEDGE_REVIEW_PROJECTION_BYTES) {
    invalid('Review projection exceeds its byte limit');
  }
  const projection = validateProjection(object.projection);
  if (projection.review_artifact_identity !== requestedIdentity) {
    invalid('Review get identity mismatch');
  }
}

function validateProjection(value: unknown): KnowledgeChangeReviewProjection {
  const object = exactRecord(value, [
    'projection_contract',
    'kind',
    'contract_version',
    'status',
    'proposal_id',
    'proposal_content_hash',
    'operation',
    'target_stable_id',
    'expected_vault_revision',
    'observed_vault_revision',
    'validation_outcome',
    'validation_snapshot',
    'source_validation_findings',
    'stable_id_set_hash',
    'proposed_content_snapshot',
    'findings',
    'before_source_byte_hash',
    'before_text_raw_hash',
    'before_semantic_text_hash',
    'proposed_text_raw_hash',
    'proposed_semantic_text_hash',
    'diff',
    'representation_delta',
    'change_identity',
    'review_artifact_identity',
    'human_review_preview'
  ], 'knowledge review projection');
  if (object.projection_contract !== KNOWLEDGE_REVIEW_PROJECTION_CONTRACT) {
    invalid('Wrong review projection contract');
  }
  if (object.kind !== 'KNOWLEDGE_CHANGE_REVIEW') invalid('Wrong review projection kind');
  if (object.contract_version !== KNOWLEDGE_CHANGE_REVIEW_CONTRACT) {
    invalid('Wrong knowledge review contract');
  }
  const status = enumValue(object.status, REVIEW_STATUSES, 'review status');
  patternString(object.proposal_id, PROPOSAL_ID_RE, 'proposal identity');
  patternString(object.proposal_content_hash, SHA256_RE, 'proposal content hash');
  enumValue(object.operation, REVIEW_OPERATIONS, 'review operation');
  stableId(object.target_stable_id);
  patternString(object.expected_vault_revision, SHA256_RE, 'expected Vault revision');
  patternString(object.observed_vault_revision, SHA256_RE, 'observed Vault revision');
  enumValue(object.validation_outcome, VALIDATION_OUTCOMES, 'validation outcome');
  validateValidationSnapshot(object.validation_snapshot);
  validateSourceFindings(object.source_validation_findings);
  patternString(object.stable_id_set_hash, SHA256_RE, 'stable ID set hash');
  validateProposedContent(object.proposed_content_snapshot);
  validateReviewFindings(object.findings);
  optionalPatternString(object.before_source_byte_hash, SHA256_RE, 'before source byte hash');
  optionalPatternString(object.before_text_raw_hash, SHA256_RE, 'before raw text hash');
  optionalPatternString(object.before_semantic_text_hash, SHA256_RE, 'before semantic hash');
  patternString(object.proposed_text_raw_hash, SHA256_RE, 'proposed raw text hash');
  patternString(object.proposed_semantic_text_hash, SHA256_RE, 'proposed semantic hash');
  if (object.diff !== null) validateDiff(object.diff);
  if (object.representation_delta !== null) validateRepresentation(object.representation_delta);
  optionalPatternString(object.change_identity, CHANGE_ID_RE, 'change identity');
  patternString(object.review_artifact_identity, REVIEW_ID_RE, 'review identity');
  validateBoundedText(object.human_review_preview, 'human review preview', 8_192);

  const normalParts = [object.diff, object.representation_delta, object.change_identity];
  if (status === 'BLOCKED' && normalParts.some((part) => part !== null)) {
    invalid('BLOCKED projection exposes normal change material');
  }
  if (status !== 'BLOCKED' && normalParts.some((part) => part === null)) {
    invalid('Non-BLOCKED projection is missing normal change material');
  }
  return object as unknown as KnowledgeChangeReviewProjection;
}

function validateProposedContent(value: unknown): ProposedContentProjection {
  const object = exactRecord(value, [
    'title',
    'body_text',
    'type',
    'status',
    'knowledge_layer',
    'evidence_class',
    'authority',
    'canonical',
    'canonical_scope',
    'aliases',
    'releases',
    'source_paths',
    'evidence_refs',
    'supersedes',
    'superseded_by',
    'updated',
    'last_reviewed',
    'verified_at'
  ], 'proposed content projection');
  boundedString(object.title, 'proposed title');
  validateProposedBody(object.body_text);
  boundedString(object.type, 'proposed type');
  boundedString(object.status, 'proposed status');
  boundedString(object.knowledge_layer, 'knowledge layer');
  boundedString(object.evidence_class, 'evidence class');
  boundedString(object.authority, 'authority');
  booleanValue(object.canonical, 'canonical flag');
  optionalBoundedString(object.canonical_scope, 'canonical scope');
  validateStringCollection(object.aliases, 'aliases');
  validateStringCollection(object.releases, 'releases');
  const sourcePaths = validateStringCollection(object.source_paths, 'source paths');
  for (const path of sourcePaths.items) ensureSafeRelativePath(path);
  validateStringCollection(object.evidence_refs, 'evidence references');
  validateStringCollection(object.supersedes, 'supersedes');
  validateStringCollection(object.superseded_by, 'superseded by');
  boundedString(object.updated, 'updated date');
  boundedString(object.last_reviewed, 'last reviewed date');
  optionalBoundedString(object.verified_at, 'verified date');
  return object as unknown as ProposedContentProjection;
}

function validateProposedBody(value: unknown): ProposedBodyProjection {
  const object = exactRecord(value, [
    'preview_text',
    'is_preview',
    'truncated',
    'original_utf8_bytes',
    'original_line_count',
    'preview_utf8_bytes',
    'preview_line_count',
    'raw_text_hash',
    'semantic_text_hash'
  ], 'proposed body projection');
  validateBoundedTextFields(object, 'proposed body', 16_384);
  patternString(object.raw_text_hash, SHA256_RE, 'proposed body raw hash');
  patternString(object.semantic_text_hash, SHA256_RE, 'proposed body semantic hash');
  return object as unknown as ProposedBodyProjection;
}

function validateBoundedText(
  value: unknown,
  label: string,
  maxPreviewBytes = MAX_GENERAL_STRING_BYTES
): BoundedTextPreviewProjection {
  const object = exactRecord(value, [
    'preview_text',
    'is_preview',
    'truncated',
    'original_utf8_bytes',
    'original_line_count',
    'preview_utf8_bytes',
    'preview_line_count'
  ], label);
  validateBoundedTextFields(object, label, maxPreviewBytes);
  return object as unknown as BoundedTextPreviewProjection;
}

function validateBoundedTextFields(
  object: JsonRecord,
  label: string,
  maxPreviewBytes: number
): void {
  const preview = boundedString(object.preview_text, `${label} text`, maxPreviewBytes);
  if (!booleanValue(object.is_preview, `${label} preview flag`)) {
    invalid(`${label} must be explicitly marked as a preview`);
  }
  const truncated = booleanValue(object.truncated, `${label} truncation`);
  const originalBytes = nonNegativeInteger(object.original_utf8_bytes, `${label} original bytes`);
  const originalLines = nonNegativeInteger(object.original_line_count, `${label} original lines`);
  const previewBytes = nonNegativeInteger(object.preview_utf8_bytes, `${label} preview bytes`);
  const previewLines = nonNegativeInteger(object.preview_line_count, `${label} preview lines`);
  if (textEncoder.encode(preview).length !== previewBytes) invalid(`${label} byte count mismatch`);
  if (previewBytes > originalBytes || previewLines > originalLines) {
    invalid(`${label} bounds are inconsistent`);
  }
  if (!truncated && (previewBytes !== originalBytes || previewLines !== originalLines)) {
    invalid(`${label} non-truncated counts are inconsistent`);
  }
}

function validateStringCollection(value: unknown, label: string): BoundedStringCollectionProjection {
  const object = exactRecord(value, ['items', 'original_count', 'truncated'], label);
  const items = arrayValue(object.items, MAX_COLLECTION_ITEMS, `${label} items`);
  const originalCount = nonNegativeInteger(object.original_count, `${label} original count`);
  const truncated = booleanValue(object.truncated, `${label} truncation`);
  if (originalCount < items.length || truncated !== (originalCount > items.length)) {
    invalid(`${label} counts are inconsistent`);
  }
  for (const item of items) boundedString(item, `${label} item`);
  return object as unknown as BoundedStringCollectionProjection;
}

function validateValidationSnapshot(value: unknown): ValidationSnapshotProjection {
  const object = exactRecord(value, ['value', 'truncated'], 'validation snapshot');
  booleanValue(object.truncated, 'validation snapshot truncation');
  validateValidationValue(object.value, 0, { nodes: 0 });
  return object as unknown as ValidationSnapshotProjection;
}

function validateValidationValue(
  value: unknown,
  depth: number,
  budget: { nodes: number }
): ValidationValueProjection {
  if (depth > MAX_VALIDATION_DEPTH) invalid('Validation snapshot is too deep');
  budget.nodes += 1;
  if (budget.nodes > MAX_VALIDATION_NODES) invalid('Validation snapshot has too many nodes');
  const object = exactRecord(
    value,
    ['type_tag', 'scalar_value', 'mapping_items', 'sequence_items'],
    'validation value'
  );
  const typeTag = enumValue(object.type_tag, VALIDATION_TYPE_TAGS, 'validation type tag');
  const mappingItems = arrayValue(object.mapping_items, MAX_VALIDATION_ITEMS, 'validation mapping');
  const sequenceItems = arrayValue(object.sequence_items, MAX_VALIDATION_ITEMS, 'validation sequence');
  if (typeTag === 'mapping') {
    if (object.scalar_value !== null || sequenceItems.length !== 0) invalid('Invalid validation mapping');
    let previousKey: string | null = null;
    for (const item of mappingItems) {
      const entry = exactRecord(item, ['key', 'value'], 'validation mapping entry');
      const key = boundedString(entry.key, 'validation mapping key', 1_024);
      if (previousKey !== null && key <= previousKey) invalid('Validation mapping keys are not ordered');
      previousKey = key;
      validateValidationValue(entry.value, depth + 1, budget);
    }
  } else if (typeTag === 'sequence') {
    if (object.scalar_value !== null || mappingItems.length !== 0) invalid('Invalid validation sequence');
    for (const child of sequenceItems) validateValidationValue(child, depth + 1, budget);
  } else {
    if (mappingItems.length !== 0 || sequenceItems.length !== 0) invalid('Invalid validation scalar');
    if (typeTag === 'null' && object.scalar_value !== null) invalid('Invalid validation null');
    if (typeTag === 'bool' && typeof object.scalar_value !== 'boolean') invalid('Invalid validation bool');
    if (typeTag === 'int' && !Number.isSafeInteger(object.scalar_value)) invalid('Invalid validation integer');
    if (typeTag === 'string') boundedString(object.scalar_value, 'validation string');
  }
  return object as unknown as ValidationValueProjection;
}

function validateSourceFindings(value: unknown): BoundedSourceValidationFindingsProjection {
  const object = exactRecord(value, ['items', 'original_count', 'truncated'], 'source findings');
  const items = arrayValue(object.items, MAX_SOURCE_FINDINGS, 'source finding items');
  const originalCount = nonNegativeInteger(object.original_count, 'source finding count');
  const truncated = booleanValue(object.truncated, 'source finding truncation');
  if (originalCount < items.length || truncated !== (originalCount > items.length)) {
    invalid('Source finding counts are inconsistent');
  }
  for (const item of items) {
    const finding = exactRecord(item, ['code', 'severity'], 'source finding');
    boundedString(finding.code, 'source finding code');
    boundedString(finding.severity, 'source finding severity');
  }
  return object as unknown as BoundedSourceValidationFindingsProjection;
}

function validateReviewFindings(value: unknown): BoundedReviewFindingsProjection {
  const object = exactRecord(value, ['items', 'original_count', 'truncated'], 'review findings');
  const items = arrayValue(object.items, MAX_FINDINGS, 'review finding items');
  const originalCount = nonNegativeInteger(object.original_count, 'review finding count');
  const truncated = booleanValue(object.truncated, 'review finding truncation');
  if (originalCount < items.length || truncated !== (originalCount > items.length)) {
    invalid('Review finding counts are inconsistent');
  }
  for (const item of items) {
    const finding = exactRecord(item, ['code', 'severity', 'message', 'details'], 'review finding');
    boundedString(finding.code, 'review finding code');
    enumValue(finding.severity, CONFLICT_SEVERITIES, 'review finding severity');
    validateBoundedText(finding.message, 'review finding message', 2_048);
    validateFindingDetails(finding.details);
  }
  return object as unknown as BoundedReviewFindingsProjection;
}

function validateFindingDetails(value: unknown): BoundedFindingDetailsProjection {
  const object = exactRecord(value, ['items', 'original_count', 'truncated'], 'finding details');
  const items = arrayValue(object.items, MAX_FINDING_DETAILS, 'finding detail items');
  const originalCount = nonNegativeInteger(object.original_count, 'finding detail count');
  const truncated = booleanValue(object.truncated, 'finding detail truncation');
  if (originalCount < items.length || truncated !== (originalCount > items.length)) {
    invalid('Finding detail counts are inconsistent');
  }
  for (const item of items) {
    const detail = exactRecord(item, ['key', 'value'], 'finding detail');
    boundedString(detail.key, 'finding detail key');
    boundedString(detail.value, 'finding detail value');
  }
  return object as unknown as BoundedFindingDetailsProjection;
}

function validateDiff(value: unknown): DiffProjection {
  const object = exactRecord(value, [
    'preview',
    'preview_truncated',
    'preview_is_full_diff',
    'full_diff_present',
    'full_diff_hash',
    'full_diff_utf8_bytes'
  ], 'diff projection');
  const preview = validateBoundedText(object.preview, 'diff preview', 16_384);
  const truncated = booleanValue(object.preview_truncated, 'diff truncation');
  const isFull = booleanValue(object.preview_is_full_diff, 'full diff preview flag');
  const fullPresent = booleanValue(object.full_diff_present, 'full diff presence');
  patternString(object.full_diff_hash, SHA256_RE, 'full diff hash');
  nonNegativeInteger(object.full_diff_utf8_bytes, 'full diff bytes');
  if (truncated !== preview.truncated || isFull || !fullPresent) {
    invalid('Diff projection flags are inconsistent');
  }
  return object as unknown as DiffProjection;
}

function validateRepresentation(value: unknown): RepresentationDeltaProjection {
  const object = exactRecord(value, [
    'before_present',
    'after_present',
    'before_line_endings',
    'after_line_endings',
    'terminal_newline_changed',
    'after_source_bytes_known',
    'source_bytes_changed_text_identical',
    'raw_text_changed_semantic_equal',
    'semantic_content_changed',
    'identity'
  ], 'representation delta');
  booleanValue(object.before_present, 'before representation presence');
  booleanValue(object.after_present, 'after representation presence');
  if (object.before_line_endings !== null) validateLineEndings(object.before_line_endings);
  validateLineEndings(object.after_line_endings);
  booleanValue(object.terminal_newline_changed, 'terminal newline change');
  booleanValue(object.after_source_bytes_known, 'source bytes known');
  booleanValue(object.source_bytes_changed_text_identical, 'source bytes change');
  booleanValue(object.raw_text_changed_semantic_equal, 'semantic equality');
  booleanValue(object.semantic_content_changed, 'semantic content change');
  patternString(object.identity, SHA256_RE, 'representation identity');
  return object as unknown as RepresentationDeltaProjection;
}

function validateLineEndings(value: unknown): LineEndingProfileProjection {
  const object = exactRecord(
    value,
    ['crlf_count', 'lf_count', 'cr_count', 'terminal_newline'],
    'line ending profile'
  );
  nonNegativeInteger(object.crlf_count, 'CRLF count');
  nonNegativeInteger(object.lf_count, 'LF count');
  nonNegativeInteger(object.cr_count, 'CR count');
  booleanValue(object.terminal_newline, 'terminal newline');
  return object as unknown as LineEndingProfileProjection;
}

function ensureReviewIdentity(value: unknown): asserts value is string {
  patternString(value, REVIEW_ID_RE, 'review identity');
}

function ensureSafeRelativePath(value: string): void {
  const normalized = value.replace(/\\/g, '/');
  const meaningfulSegments = normalized.split('/').filter((segment) => segment !== '' && segment !== '.');
  if (
    value.length === 0 ||
    [...value].length > 512 ||
    textEncoder.encode(value).length > 2_048 ||
    value.startsWith('/') ||
    value.startsWith('\\') ||
    WINDOWS_DRIVE_RE.test(value) ||
    meaningfulSegments.length === 0 ||
    normalized.split('/').some(
      (segment) =>
        segment === '..' ||
        segment.replace(/ +$/g, '') === '..' ||
        segment.replace(/[. ]+$/g, '') === '..'
    )
  ) {
    invalid('Unsafe source path in review projection');
  }
}

function hasTruncatedReviewDetail(projection: KnowledgeChangeReviewProjection): boolean {
  const proposed = projection.proposed_content_snapshot;
  const collectionTruncated = [
    proposed.aliases,
    proposed.releases,
    proposed.source_paths,
    proposed.evidence_refs,
    proposed.supersedes,
    proposed.superseded_by
  ].some((collection) => collection.truncated);
  const findingDetailTruncated = projection.findings.items.some(
    (finding) => finding.message.truncated || finding.details.truncated
  );
  return (
    projection.validation_snapshot.truncated ||
    projection.source_validation_findings.truncated ||
    proposed.body_text.truncated ||
    collectionTruncated ||
    projection.findings.truncated ||
    findingDetailTruncated ||
    (projection.diff !== null && projection.diff.preview_truncated) ||
    projection.human_review_preview.truncated
  );
}

function lineEndingView(profile: LineEndingProfileProjection) {
  const labels: string[] = [];
  if (profile.crlf_count > 0) labels.push('CRLF');
  if (profile.lf_count > 0) labels.push('LF');
  if (profile.cr_count > 0) labels.push('CR');
  return {
    label: (labels.length === 0 ? 'NONE' : labels.join('+')) as
      | 'NONE'
      | 'LF'
      | 'CRLF'
      | 'CR'
      | 'CRLF+LF'
      | 'CRLF+CR'
      | 'LF+CR'
      | 'CRLF+LF+CR',
    crlfCount: profile.crlf_count,
    lfCount: profile.lf_count,
    crCount: profile.cr_count,
    terminalNewline: profile.terminal_newline
  };
}

function validationScalar(value: ValidationValueProjection, key: string): unknown {
  if (value.type_tag !== 'mapping') return undefined;
  const entry = value.mapping_items.find((item) => item.key === key);
  if (!entry || !['null', 'bool', 'int', 'string'].includes(entry.value.type_tag)) return undefined;
  return entry.value.scalar_value;
}

function formatValidationSnapshot(value: ValidationValueProjection): string {
  try {
    return JSON.stringify(materializeValidationValue(value), null, 2).slice(0, 16_384);
  } catch {
    return '{}';
  }
}

function materializeValidationValue(value: ValidationValueProjection): unknown {
  if (value.type_tag === 'mapping') {
    return Object.fromEntries(
      value.mapping_items.map((entry) => [entry.key, materializeValidationValue(entry.value)])
    );
  }
  if (value.type_tag === 'sequence') {
    return value.sequence_items.map(materializeValidationValue);
  }
  return value.scalar_value;
}

function exactRecord(value: unknown, keys: readonly string[], label: string): JsonRecord {
  if (!isRecord(value)) invalid(`${label} must be an object`);
  const actualKeys = Object.keys(value).sort();
  const expectedKeys = [...keys].sort();
  if (
    actualKeys.length !== expectedKeys.length ||
    actualKeys.some((key, index) => key !== expectedKeys[index])
  ) {
    invalid(`${label} has an unexpected shape`);
  }
  return value;
}

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function arrayValue(value: unknown, limit: number, label: string): readonly unknown[] {
  if (!Array.isArray(value) || value.length > limit) invalid(`${label} is invalid`);
  return value;
}

function booleanValue(value: unknown, label: string): boolean {
  if (typeof value !== 'boolean') invalid(`${label} is invalid`);
  return value;
}

function nonNegativeInteger(value: unknown, label: string): number {
  if (!isSafeNonNegativeInteger(value)) invalid(`${label} is invalid`);
  return value;
}

function positiveInteger(value: unknown, label: string): number {
  if (!Number.isSafeInteger(value) || (value as number) < 1) invalid(`${label} is invalid`);
  return value as number;
}

function isSafeNonNegativeInteger(value: unknown): value is number {
  return Number.isSafeInteger(value) && (value as number) >= 0;
}

function boundedString(value: unknown, label: string, maxBytes = MAX_GENERAL_STRING_BYTES): string {
  if (
    typeof value !== 'string' ||
    value.includes('\0') ||
    textEncoder.encode(value).length > maxBytes
  ) {
    invalid(`${label} is invalid`);
  }
  return value;
}

function optionalBoundedString(
  value: unknown,
  label: string,
  maxBytes = MAX_GENERAL_STRING_BYTES
): string | null {
  if (value === null) return null;
  return boundedString(value, label, maxBytes);
}

function patternString(value: unknown, pattern: RegExp, label: string): string {
  if (typeof value !== 'string' || !pattern.test(value)) invalid(`${label} is invalid`);
  return value;
}

function optionalPatternString(value: unknown, pattern: RegExp, label: string): string | null {
  if (value === null) return null;
  return patternString(value, pattern, label);
}

function stableId(value: unknown): string {
  if (typeof value !== 'string' || value.length > 128 || !STABLE_ID_RE.test(value)) {
    invalid('Target stable ID is invalid');
  }
  return value;
}

function enumValue<const T extends readonly string[]>(
  value: unknown,
  values: T,
  label: string
): T[number] {
  if (typeof value !== 'string' || !(values as readonly string[]).includes(value)) {
    invalid(`${label} is invalid`);
  }
  return value as T[number];
}

function serializeBounded(value: unknown, maxBytes: number, message: string): string {
  let serialized: string | undefined;
  try {
    serialized = JSON.stringify(value);
  } catch {
    invalid('Review bridge response is not JSON-safe');
  }
  if (serialized === undefined || textEncoder.encode(serialized).length > maxBytes) invalid(message);
  return serialized;
}

function deepFreeze<T>(value: T): T {
  if (typeof value !== 'object' || value === null || Object.isFrozen(value)) return value;
  for (const child of Object.values(value as Record<string, unknown>)) deepFreeze(child);
  return Object.freeze(value);
}

function boundedSanitized(value: string, limit: number): string {
  const sanitized = value
    .replace(/\0/g, '')
    .replace(/Traceback[\s\S]*/gi, '<redacted>')
    .replace(/sk-[A-Za-z0-9_-]{8,}/g, '<redacted>')
    .replace(/Bearer\s+[A-Za-z0-9._-]+/gi, '<redacted>');
  return [...sanitized].slice(0, limit).join('');
}

function invalid(message: string): never {
  throw Object.freeze({ code: 'invalid_payload', message });
}
