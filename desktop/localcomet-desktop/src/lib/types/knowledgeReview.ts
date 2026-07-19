export type ReviewStatus = 'CLEAR' | 'REVIEW_REQUIRED' | 'BLOCKED';
export type ConflictSeverity = 'BLOCKING' | 'REVIEW';
export type DecisionIntent = 'APPROVE' | 'REJECT' | 'REQUEST_CHANGES';
export type ReviewOperation =
  | 'UPDATE_EXISTING'
  | 'CREATE_NEW'
  | 'DELETE'
  | 'MOVE'
  | 'RENAME'
  | 'SUPERSEDE';
export type ReviewSource = 'FIXTURE' | 'LOCAL_CONTROL_PLANE';
export type ReviewCenterLoadStatus = 'idle' | 'loading' | 'empty' | 'ready' | 'error';
export type ReviewFreshness = 'FRESH' | 'STALE' | 'UNKNOWN';
export type ReviewActivityKind =
  | 'INBOX_REFRESH'
  | 'ARTIFACT_OPENED'
  | 'STALE_REVIEW'
  | 'DECISION_CREATED'
  | 'ERROR'
  | 'SIDECAR_RECONNECT';

export interface BoundedTextPreviewProjection {
  readonly preview_text: string;
  readonly is_preview: boolean;
  readonly truncated: boolean;
  readonly original_utf8_bytes: number;
  readonly original_line_count: number;
  readonly preview_utf8_bytes: number;
  readonly preview_line_count: number;
}

export interface ProposedBodyProjection extends BoundedTextPreviewProjection {
  readonly raw_text_hash: string;
  readonly semantic_text_hash: string;
}

export interface BoundedStringCollectionProjection {
  readonly items: readonly string[];
  readonly original_count: number;
  readonly truncated: boolean;
}

export interface ValidationMappingEntryProjection {
  readonly key: string;
  readonly value: ValidationValueProjection;
}

export interface ValidationValueProjection {
  readonly type_tag: 'mapping' | 'sequence' | 'null' | 'bool' | 'int' | 'string';
  readonly scalar_value: string | number | boolean | null;
  readonly mapping_items: readonly ValidationMappingEntryProjection[];
  readonly sequence_items: readonly ValidationValueProjection[];
}

export interface ValidationSnapshotProjection {
  readonly value: ValidationValueProjection;
  readonly truncated: boolean;
}

export interface SourceValidationFindingProjection {
  readonly code: string;
  readonly severity: string;
}

export interface BoundedSourceValidationFindingsProjection {
  readonly items: readonly SourceValidationFindingProjection[];
  readonly original_count: number;
  readonly truncated: boolean;
}

export interface FindingDetailProjection {
  readonly key: string;
  readonly value: string;
}

export interface BoundedFindingDetailsProjection {
  readonly items: readonly FindingDetailProjection[];
  readonly original_count: number;
  readonly truncated: boolean;
}

export interface ReviewFindingProjection {
  readonly code: string;
  readonly severity: ConflictSeverity;
  readonly message: BoundedTextPreviewProjection;
  readonly details: BoundedFindingDetailsProjection;
}

export interface BoundedReviewFindingsProjection {
  readonly items: readonly ReviewFindingProjection[];
  readonly original_count: number;
  readonly truncated: boolean;
}

export interface LineEndingProfileProjection {
  readonly crlf_count: number;
  readonly lf_count: number;
  readonly cr_count: number;
  readonly terminal_newline: boolean;
}

export interface RepresentationDeltaProjection {
  readonly before_present: boolean;
  readonly after_present: boolean;
  readonly before_line_endings: LineEndingProfileProjection | null;
  readonly after_line_endings: LineEndingProfileProjection;
  readonly terminal_newline_changed: boolean;
  readonly after_source_bytes_known: boolean;
  readonly source_bytes_changed_text_identical: boolean;
  readonly raw_text_changed_semantic_equal: boolean;
  readonly semantic_content_changed: boolean;
  readonly identity: string;
}

export interface ProposedContentProjection {
  readonly title: string;
  readonly body_text: ProposedBodyProjection;
  readonly type: string;
  readonly status: string;
  readonly knowledge_layer: string;
  readonly evidence_class: string;
  readonly authority: string;
  readonly canonical: boolean;
  readonly canonical_scope: string | null;
  readonly aliases: BoundedStringCollectionProjection;
  readonly releases: BoundedStringCollectionProjection;
  readonly source_paths: BoundedStringCollectionProjection;
  readonly evidence_refs: BoundedStringCollectionProjection;
  readonly supersedes: BoundedStringCollectionProjection;
  readonly superseded_by: BoundedStringCollectionProjection;
  readonly updated: string;
  readonly last_reviewed: string;
  readonly verified_at: string | null;
}

export interface DiffProjection {
  readonly preview: BoundedTextPreviewProjection;
  readonly preview_truncated: boolean;
  readonly preview_is_full_diff: boolean;
  readonly full_diff_present: boolean;
  readonly full_diff_hash: string;
  readonly full_diff_utf8_bytes: number;
}

export interface KnowledgeChangeReviewProjection {
  readonly projection_contract: 'localcomet.knowledge-review-ui/1.0';
  readonly kind: 'KNOWLEDGE_CHANGE_REVIEW';
  readonly contract_version: string;
  readonly status: ReviewStatus;
  readonly proposal_id: string;
  readonly proposal_content_hash: string;
  readonly operation: ReviewOperation;
  readonly target_stable_id: string;
  readonly expected_vault_revision: string;
  readonly observed_vault_revision: string;
  readonly validation_outcome: 'VALID' | 'INVALID' | 'STALE';
  readonly validation_snapshot: ValidationSnapshotProjection;
  readonly source_validation_findings: BoundedSourceValidationFindingsProjection;
  readonly stable_id_set_hash: string;
  readonly proposed_content_snapshot: ProposedContentProjection;
  readonly findings: BoundedReviewFindingsProjection;
  readonly before_source_byte_hash: string | null;
  readonly before_text_raw_hash: string | null;
  readonly before_semantic_text_hash: string | null;
  readonly proposed_text_raw_hash: string;
  readonly proposed_semantic_text_hash: string;
  readonly diff: DiffProjection | null;
  readonly representation_delta: RepresentationDeltaProjection | null;
  readonly change_identity: string | null;
  readonly review_artifact_identity: string;
  readonly human_review_preview: BoundedTextPreviewProjection;
}

export interface KnowledgeReviewSummaryProjection {
  readonly projection_contract: 'localcomet.knowledge-review-ui/1.0';
  readonly kind: 'KNOWLEDGE_CHANGE_REVIEW_SUMMARY';
  readonly contract_version: string;
  readonly status: ReviewStatus;
  readonly blocked: boolean;
  readonly proposal_id: string;
  readonly target_stable_id: string;
  readonly operation: ReviewOperation;
  readonly expected_vault_revision: string;
  readonly observed_vault_revision: string;
  readonly review_artifact_identity: string;
  readonly change_identity: string | null;
  readonly finding_count: number;
  readonly normal_change_material_present: boolean;
  readonly detail_projection_truncated: boolean;
}

export interface KnowledgeReviewListEnvelope {
  readonly contract: 'localcomet.knowledge-review-list/1.0';
  readonly source: 'LOCAL_CONTROL_PLANE';
  readonly fixture: false;
  readonly offset: number;
  readonly limit: number;
  readonly total_count: number;
  readonly returned_count: number;
  readonly truncated: boolean;
  readonly next_offset: number | null;
  readonly items: readonly KnowledgeReviewSummaryProjection[];
}

export interface KnowledgeReviewGetEnvelope {
  readonly contract: 'localcomet.knowledge-review-get/1.0';
  readonly source: 'LOCAL_CONTROL_PLANE';
  readonly fixture: false;
  readonly projection: KnowledgeChangeReviewProjection;
}

export interface KnowledgeReviewStateProjection {
  readonly review_artifact_identity: string;
  readonly status: ReviewStatus;
  readonly stale: boolean | null;
}

export interface KnowledgeReviewSnapshotEnvelope {
  readonly contract:
    | 'localcomet.knowledge-review-snapshot/1.0'
    | 'localcomet.knowledge-review-refresh/1.0';
  readonly command_center_version: 'v6.84.6';
  readonly control_plane_version: string;
  readonly sidecar_runtime_version: string;
  readonly source: 'LOCAL_CONTROL_PLANE';
  readonly fixture: false;
  readonly refresh_requested: boolean;
  readonly refresh_succeeded: boolean;
  readonly current_vault_revision: string | null;
  readonly freshness_known: boolean;
  readonly knowledge_state: string;
  readonly last_error_code: string | null;
  readonly inbox_count: number;
  readonly stale_count: number;
  readonly blocked_count: number;
  readonly session_decision_count: number;
  readonly review_states: readonly KnowledgeReviewStateProjection[];
  readonly hard_stop: true;
  readonly persistence: false;
  readonly vault_write_authority: false;
  readonly publication_authority: false;
}

export interface HumanReviewerMetadataProjection {
  readonly actor_identifier: string;
  readonly display_name: string;
  readonly source: string;
}

export interface HumanReviewDecisionProjection {
  readonly projection_contract: 'localcomet.knowledge-review-ui/1.0';
  readonly kind: 'HUMAN_REVIEW_DECISION';
  readonly contract_version: 'localcomet.knowledge-change-review-decision/1.0';
  readonly review_contract_version: 'localcomet.knowledge-change-review/1.0';
  readonly review_status: ReviewStatus;
  readonly proposal_id: string;
  readonly review_artifact_identity: string;
  readonly change_identity: string | null;
  readonly observed_vault_revision: string;
  readonly decision: DecisionIntent;
  readonly comment: string;
  readonly actor: HumanReviewerMetadataProjection;
  readonly decision_identity: string;
  readonly hard_stop: true;
  readonly review_decision_only: true;
  readonly actor_metadata_evidence_only: true;
  readonly human_identity_authenticated: false;
  readonly grants_write_authority: false;
  readonly grants_vault_write_authority: false;
  readonly grants_persistence_authority: false;
  readonly grants_publication_authority: false;
  readonly grants_merge_authority: false;
  readonly grants_rebase_authority: false;
  readonly grants_execution_authority: false;
  readonly grants_policy_authority: false;
  readonly grants_model_gateway_authority: false;
  readonly grants_tauri_frontend_authority: false;
  readonly grants_automatic_approval_authority: false;
}

export interface KnowledgeReviewDecisionRequest {
  readonly reviewContractVersion: 'localcomet.knowledge-change-review/1.0';
  readonly proposalId: string;
  readonly reviewArtifactIdentity: string;
  readonly changeIdentity: string | null;
  readonly observedVaultRevision: string;
  readonly decision: DecisionIntent;
  readonly comment: string;
  readonly actorIdentifier: string;
  readonly actorDisplayName: string;
  readonly actorSource: 'LOCALCOMET_REVIEW_CENTER';
}

export interface KnowledgeReviewDecisionCreateEnvelope {
  readonly contract: 'localcomet.knowledge-review-decision-create/1.0';
  readonly command_center_version: 'v6.84.6';
  readonly control_plane_version: string;
  readonly sidecar_runtime_version: string;
  readonly source: 'LOCAL_CONTROL_PLANE';
  readonly fixture: false;
  readonly duplicate: boolean;
  readonly current_vault_revision: string;
  readonly decision: HumanReviewDecisionProjection;
  readonly hard_stop: true;
  readonly vault_modified: false;
  readonly persistence: false;
  readonly publication: false;
}

export interface ReviewActivityEvent {
  readonly id: string;
  readonly sequence: number;
  readonly kind: ReviewActivityKind;
  readonly messageKey: string;
  readonly reviewArtifactIdentity: string | null;
  readonly errorCode: string | null;
}

export interface ReviewFilterState {
  readonly query: string;
  readonly statuses: readonly ReviewStatus[];
  readonly operations: readonly ReviewOperation[];
  readonly sort: 'IDENTITY_ASC' | 'STATUS_THEN_IDENTITY';
}

export interface ReviewDiagnostics {
  readonly commandCenterVersion: 'v6.84.6';
  readonly frontendContractVersion: 'localcomet.knowledge-review-ui/1.0';
  readonly tauriBridgeStatus: 'IDLE' | 'CONNECTING' | 'CONNECTED' | 'UNAVAILABLE' | 'ERROR';
  readonly sidecarConnectionState: 'IDLE' | 'CONNECTING' | 'CONNECTED' | 'UNAVAILABLE' | 'ERROR';
  readonly pythonRuntimeContractVersion: string | null;
  readonly inboxCount: number;
  readonly staleCount: number;
  readonly blockedCount: number;
  readonly sessionDecisionCount: number;
  readonly currentVaultRevision: string | null;
  readonly freshnessKnown: boolean;
  readonly lastErrorCode: string | null;
}

export interface ReviewQueueItem {
  readonly id: string;
  readonly fixture: boolean;
  readonly source: ReviewSource;
  readonly fixtureLabel?: string;
  readonly status: ReviewStatus;
  readonly blocked: boolean;
  readonly proposalId: string;
  readonly targetStableId: string;
  readonly operation: ReviewOperation;
  readonly expectedVaultRevision: string;
  readonly observedVaultRevision: string;
  readonly reviewArtifactIdentity: string;
  readonly changeIdentity: string | null;
  readonly findingCount: number;
  readonly normalChangeMaterialPresent: boolean;
  readonly detailProjectionTruncated: boolean;
  readonly stale: boolean | null;
}

export interface ReviewCenterError {
  readonly code: string;
  readonly message: string;
}

export interface ReviewCenterState {
  readonly status: ReviewCenterLoadStatus;
  readonly source: ReviewSource;
  readonly error: ReviewCenterError | null;
  readonly failedRequest: 'list' | 'get' | 'snapshot' | 'refresh' | 'decision' | null;
  readonly retryable: boolean;
  readonly totalCount: number;
  readonly returnedCount: number;
  readonly truncated: boolean;
  readonly nextOffset: number | null;
}

export const PROPOSED_CONTENT_FIELDS = [
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
] as const;

export type ProposedContentField = (typeof PROPOSED_CONTENT_FIELDS)[number];

export interface ProposedNoteContentView {
  readonly title: string;
  readonly body_text: string;
  readonly type: string;
  readonly status: string;
  readonly knowledge_layer: string;
  readonly evidence_class: string;
  readonly authority: string;
  readonly canonical: boolean;
  readonly canonical_scope: string | null;
  readonly aliases: readonly string[];
  readonly releases: readonly string[];
  readonly source_paths: readonly string[];
  readonly evidence_refs: readonly string[];
  readonly supersedes: readonly string[];
  readonly superseded_by: readonly string[];
  readonly updated: string;
  readonly last_reviewed: string;
  readonly verified_at: string | null;
}

export type MetadataValue = string | boolean | null | readonly string[];

export interface MetadataChange {
  readonly field: ProposedContentField;
  readonly before: MetadataValue;
  readonly after: MetadataValue;
}

export interface ReviewFinding {
  readonly code: string;
  readonly severity: ConflictSeverity;
  readonly message: string;
  readonly details: readonly (readonly [string, string])[];
}

export interface LineEndingProfileView {
  readonly label: 'NONE' | 'LF' | 'CRLF' | 'CR' | 'CRLF+LF' | 'CRLF+CR' | 'LF+CR' | 'CRLF+LF+CR';
  readonly crlfCount: number;
  readonly lfCount: number;
  readonly crCount: number;
  readonly terminalNewline: boolean;
}

export interface RepresentationDeltaView {
  readonly identity: string;
  readonly beforePresent: boolean;
  readonly afterPresent: boolean;
  readonly beforeLineEndings: LineEndingProfileView | null;
  readonly afterLineEndings: LineEndingProfileView;
  readonly terminalNewlineChanged: boolean;
  readonly afterSourceBytesKnown: boolean;
  readonly sourceBytesChangedTextIdentical: boolean;
  readonly rawTextChangedSemanticEqual: boolean;
  readonly semanticContentChanged: boolean;
}

export interface ValidationView {
  readonly outcome: 'VALID' | 'INVALID' | 'STALE';
  readonly contractVersion: string;
  readonly proposalContentHash: string;
  readonly validatedVaultRevision: string;
  readonly sourceFindings: readonly (readonly [string, string])[];
  readonly snapshotTruncated: boolean;
  readonly snapshotSummary: string;
}

export interface DiffPreviewView {
  readonly preview: string | null;
  readonly previewTruncated: boolean;
  readonly fullDiffAvailable: boolean;
  readonly fullDiffHash: string | null;
  readonly fullDiffUtf8Bytes: number | null;
}

export interface HumanReviewPreviewView {
  readonly text: string;
  readonly truncated: boolean;
}

interface ReviewCenterItemBase {
  readonly id: string;
  readonly status: ReviewStatus;
  readonly proposalId: string;
  readonly proposalContentHash: string;
  readonly reviewArtifactIdentity: string;
  readonly changeIdentity: string | null;
  readonly operation: ReviewOperation;
  readonly targetStableId: string;
  readonly expectedVaultRevision: string;
  readonly observedVaultRevision: string;
  readonly validation: ValidationView;
  readonly findings: readonly ReviewFinding[];
  readonly proposedContent: ProposedNoteContentView;
  readonly metadataChanges: readonly MetadataChange[];
  readonly beforeSourceByteHash: string | null;
  readonly beforeTextRawHash: string | null;
  readonly beforeSemanticTextHash: string | null;
  readonly proposedTextRawHash: string;
  readonly proposedSemanticTextHash: string;
  readonly textDiff: DiffPreviewView;
  readonly representationDelta: RepresentationDeltaView | null;
  readonly humanReviewPreview: HumanReviewPreviewView;
}

export interface FixtureReviewCenterItem extends ReviewCenterItemBase {
  readonly fixture: true;
  readonly source?: 'FIXTURE';
  readonly fixtureLabel: string;
  readonly detailProjectionTruncated?: false;
  readonly rawProjection?: never;
}

export interface RealReviewCenterItem extends ReviewCenterItemBase {
  readonly fixture: false;
  readonly source: 'LOCAL_CONTROL_PLANE';
  readonly fixtureLabel?: never;
  readonly detailProjectionTruncated: boolean;
  readonly stale: boolean | null;
  readonly rawProjection: KnowledgeChangeReviewProjection;
}

export type ReviewCenterItem = FixtureReviewCenterItem | RealReviewCenterItem;

export interface DecisionDialogState {
  readonly open: boolean;
  readonly intent: DecisionIntent | null;
  readonly comment: string;
  readonly actorIdentifier: string;
  readonly actorDisplayName: string;
  readonly submitting: boolean;
  readonly errorKey: string | null;
}

export interface FixtureDecisionResult {
  readonly fixture: true;
  readonly hardStop: true;
  readonly proposalId: string;
  readonly reviewArtifactIdentity: string;
  readonly intent: DecisionIntent;
  readonly comment: string;
  readonly messageKey: 'review.decision.fixture_hard_stop';
}

export interface RealDecisionResult {
  readonly fixture: false;
  readonly hardStop: true;
  readonly duplicate: boolean;
  readonly vaultModified: false;
  readonly persistence: false;
  readonly publication: false;
  readonly currentVaultRevision: string;
  readonly decision: HumanReviewDecisionProjection;
  readonly messageKey: 'review.decision.real_hard_stop';
}

export type ReviewDecisionResult = FixtureDecisionResult | RealDecisionResult;

export const CONFLICT_CODE_ORDER: Readonly<Record<string, number>> = Object.freeze({
  VALIDATION_RESULT_PROPOSAL_MISMATCH: 0,
  UNSUPPORTED_OPERATION: 1,
  STALE_VAULT_REVISION: 2,
  TARGET_MISSING: 3,
  UNVERIFIED_TEXT_INPUT: 4,
  TARGET_CHANGED_SINCE_PROPOSAL: 5,
  TARGET_SOURCE_BYTES_CHANGED_TEXT_IDENTICAL: 6,
  TARGET_STATE_COMPARISON_UNAVAILABLE: 7,
  STABLE_ID_COLLISION: 8,
  PROPOSED_CONTENT_ALREADY_IDENTICAL: 9,
  PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT: 10
});

export function sortReviewFindings(findings: readonly ReviewFinding[]): readonly ReviewFinding[] {
  return [...findings].sort((left, right) => {
    const leftOrder = CONFLICT_CODE_ORDER[left.code] ?? Number.MAX_SAFE_INTEGER;
    const rightOrder = CONFLICT_CODE_ORDER[right.code] ?? Number.MAX_SAFE_INTEGER;
    if (leftOrder !== rightOrder) return leftOrder - rightOrder;
    return left.code.localeCompare(right.code);
  });
}

export function isBlocked(review: ReviewCenterItem): boolean {
  return review.status === 'BLOCKED';
}
