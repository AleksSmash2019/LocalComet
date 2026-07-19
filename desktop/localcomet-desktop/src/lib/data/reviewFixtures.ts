import type {
  ProposedNoteContentView,
  ReviewCenterItem
} from '$lib/types/knowledgeReview';

function deepFreeze<T>(value: T): T {
  if (value !== null && typeof value === 'object' && !Object.isFrozen(value)) {
    for (const child of Object.values(value as Record<string, unknown>)) {
      deepFreeze(child);
    }
    Object.freeze(value);
  }
  return value;
}

const REVISION_A = "sha256:db3aa6c2ed8046f6f57fe11178d8529cfda2116cfff7ae01b4b579eee999a61a";
const REVISION_B = "sha256:bc06395bf0601ffe3d4e25b951bd613494b6912d1b9adfd033ebf439fda9c093";
const REVISION_C = "sha256:df62512408de6bd5c196570651c10cfbc4a247247f7e1054c4c717de3e3580e2";

function proposedContent(overrides: Partial<ProposedNoteContentView> = {}): ProposedNoteContentView {
  return {
    title: 'Knowledge review lifecycle',
    body_text: '# Knowledge review lifecycle\n\nReview artifacts stop before authority.\n',
    type: 'architecture',
    status: 'accepted',
    knowledge_layer: 'canonical',
    evidence_class: 'source-grounded',
    authority: 'maintainer-reviewed',
    canonical: true,
    canonical_scope: 'architecture.knowledge-layer',
    aliases: ['Review lifecycle'],
    releases: ['v6.84.5.1e9b'],
    source_paths: ['modules/knowledge_change_review_ru.py'],
    evidence_refs: ['evidence.e9b.focused-tests'],
    supersedes: [],
    superseded_by: [],
    updated: '2026-07-16',
    last_reviewed: '2026-07-16',
    verified_at: '2026-07-16T09:00:00Z',
    ...overrides
  };
}

const metadataOnly: ReviewCenterItem = {
  id: 'review-metadata-only',
  fixture: true,
  fixtureLabel: 'Metadata-only fixture',
  status: 'CLEAR',
  proposalId: 'kprop:39770887b8effed001546e4f8ca3960be0dac8b61f40ebde55ba68895540c37a',
  proposalContentHash: 'sha256:400075069c197bbcb0114c66fdcaefa53e224de63bbe58f67f9af54691c996fa',
  reviewArtifactIdentity: 'kreview:57692c300ea9ff7be50e89b7bf9e8303cdaaa03ab52d4f290c8f8b0e1feabcdf',
  changeIdentity: 'kchange:fb09d978dcca99cc4829f433524865416de42cb0eca5b20eb1052ec3b591e4e7',
  operation: 'UPDATE_EXISTING',
  targetStableId: 'architecture.knowledge-review',
  expectedVaultRevision: REVISION_A,
  observedVaultRevision: REVISION_A,
  validation: {
    outcome: 'VALID',
    contractVersion: 'localcomet.knowledge-change-proposal/1.0',
    proposalContentHash: 'sha256:400075069c197bbcb0114c66fdcaefa53e224de63bbe58f67f9af54691c996fa',
    validatedVaultRevision: REVISION_A,
    sourceFindings: [],
    snapshotTruncated: false,
    snapshotSummary: 'Type-tagged validation snapshot verified.'
  },
  findings: [],
  proposedContent: proposedContent({
    title: 'Human-readable knowledge review lifecycle',
    aliases: ['Review lifecycle', 'Human review boundary']
  }),
  metadataChanges: [
    {
      field: 'title',
      before: 'Knowledge review lifecycle',
      after: 'Human-readable knowledge review lifecycle'
    },
    {
      field: 'aliases',
      before: ['Review lifecycle'],
      after: ['Review lifecycle', 'Human review boundary']
    }
  ],
  beforeSourceByteHash: 'sha256:580e36de86fe5fde24c0d67de903eacf0531bedc5c7e15020580624bf3fbd2f5',
  beforeTextRawHash: 'sha256:f1b639bcb63b3e122acdbf8a2efbe99e45c0491a75767dfaef1d83623bae6b30',
  beforeSemanticTextHash: 'sha256:f1b639bcb63b3e122acdbf8a2efbe99e45c0491a75767dfaef1d83623bae6b30',
  proposedTextRawHash: 'sha256:f1b639bcb63b3e122acdbf8a2efbe99e45c0491a75767dfaef1d83623bae6b30',
  proposedSemanticTextHash: 'sha256:f1b639bcb63b3e122acdbf8a2efbe99e45c0491a75767dfaef1d83623bae6b30',
  textDiff: {
    preview: '',
    previewTruncated: false,
    fullDiffAvailable: true,
    fullDiffHash: 'sha256:48384b29c366033e1b206fc1de04846397400cf4c360816e192739f63b1c7cc6',
    fullDiffUtf8Bytes: 0
  },
  representationDelta: {
    identity: 'sha256:e8fa02b7dfa54f9e1890e6e4fe1cfed03d390bd19d1698c4fbdc72df2735f8fe',
    beforePresent: true,
    afterPresent: true,
    beforeLineEndings: {
      label: 'LF',
      crlfCount: 0,
      lfCount: 3,
      crCount: 0,
      terminalNewline: true
    },
    afterLineEndings: {
      label: 'LF',
      crlfCount: 0,
      lfCount: 3,
      crCount: 0,
      terminalNewline: true
    },
    terminalNewlineChanged: false,
    afterSourceBytesKnown: false,
    sourceBytesChangedTextIdentical: false,
    rawTextChangedSemanticEqual: false,
    semanticContentChanged: false
  },
  humanReviewPreview: {
    text: 'Metadata changed while the semantic body diff remained empty. Review all structured fields.',
    truncated: false
  }
};

const representationOnly: ReviewCenterItem = {
  id: 'review-representation-only',
  fixture: true,
  fixtureLabel: 'Representation-only fixture',
  status: 'REVIEW_REQUIRED',
  proposalId: 'kprop:56f33f21c910d48109c8ece14e4e4b45f3044224f2026e4d29d7cf202fa3b4ff',
  proposalContentHash: 'sha256:580e36de86fe5fde24c0d67de903eacf0531bedc5c7e15020580624bf3fbd2f5',
  reviewArtifactIdentity: 'kreview:94d955f5d8f4cf06ff1044bab1358323fccb4cde8e09db0c48aac28f7419b173',
  changeIdentity: 'kchange:d3a244e82013faa1fd052142affd4df6b84423661e09448735498a0c038b834a',
  operation: 'UPDATE_EXISTING',
  targetStableId: 'canonical.current-state',
  expectedVaultRevision: REVISION_A,
  observedVaultRevision: REVISION_A,
  validation: {
    outcome: 'VALID',
    contractVersion: 'localcomet.knowledge-change-proposal/1.0',
    proposalContentHash: 'sha256:580e36de86fe5fde24c0d67de903eacf0531bedc5c7e15020580624bf3fbd2f5',
    validatedVaultRevision: REVISION_A,
    sourceFindings: [],
    snapshotTruncated: false,
    snapshotSummary: 'Validation is exact; no trusted historical baseline was supplied.'
  },
  findings: [
    {
      code: 'TARGET_STATE_COMPARISON_UNAVAILABLE',
      severity: 'REVIEW',
      message: 'Historical target drift is not claimed without a trusted baseline.',
      details: [['expected_vault_revision', REVISION_A]]
    }
  ],
  proposedContent: proposedContent({
    title: 'Current state',
    body_text: '# Current state\n\nReview artifacts stop before authority.\n',
    canonical_scope: 'canonical.current-state'
  }),
  metadataChanges: [],
  beforeSourceByteHash: 'sha256:48384b29c366033e1b206fc1de04846397400cf4c360816e192739f63b1c7cc6',
  beforeTextRawHash: 'sha256:b6171bd597f888487926af6d62f1275f8d1e07f6dff4d89766ab60a73049d5da',
  beforeSemanticTextHash: 'sha256:4188cb7d894dcd814c8e997f4061b565b3b19dc3b5d9a78daf1a4d9eb3600885',
  proposedTextRawHash: 'sha256:400075069c197bbcb0114c66fdcaefa53e224de63bbe58f67f9af54691c996fa',
  proposedSemanticTextHash: 'sha256:4188cb7d894dcd814c8e997f4061b565b3b19dc3b5d9a78daf1a4d9eb3600885',
  textDiff: {
    preview: '',
    previewTruncated: false,
    fullDiffAvailable: true,
    fullDiffHash: 'sha256:b6171bd597f888487926af6d62f1275f8d1e07f6dff4d89766ab60a73049d5da',
    fullDiffUtf8Bytes: 0
  },
  representationDelta: {
    identity: 'sha256:e976645f880f2e82fe084434ab3a7352ca62cf777b6ddf124e8f54116e3b2da5',
    beforePresent: true,
    afterPresent: true,
    beforeLineEndings: {
      label: 'CRLF',
      crlfCount: 3,
      lfCount: 0,
      crCount: 0,
      terminalNewline: true
    },
    afterLineEndings: {
      label: 'LF',
      crlfCount: 0,
      lfCount: 3,
      crCount: 0,
      terminalNewline: true
    },
    terminalNewlineChanged: false,
    afterSourceBytesKnown: false,
    sourceBytesChangedTextIdentical: false,
    rawTextChangedSemanticEqual: true,
    semanticContentChanged: false
  },
  humanReviewPreview: {
    text: 'Semantic body diff is empty, but line endings change from CRLF to LF.',
    truncated: false
  }
};

const blocked: ReviewCenterItem = {
  id: 'review-blocked-stale',
  fixture: true,
  fixtureLabel: 'Blocked stale fixture',
  status: 'BLOCKED',
  proposalId: 'kprop:3a64d96ee9d7be5db2b308b21ae96adbb589a371afad93a3af50fbfd4669c68b',
  proposalContentHash: 'sha256:f1b639bcb63b3e122acdbf8a2efbe99e45c0491a75767dfaef1d83623bae6b30',
  reviewArtifactIdentity: 'kreview:ee7038ee6bebee660b01f0d4e81ebc2ba0e219e4e38f1dec9cc79644adf1d270',
  changeIdentity: null,
  operation: 'UPDATE_EXISTING',
  targetStableId: 'architecture.control-plane',
  expectedVaultRevision: REVISION_A,
  observedVaultRevision: REVISION_B,
  validation: {
    outcome: 'STALE',
    contractVersion: 'localcomet.knowledge-change-proposal/1.0',
    proposalContentHash: 'sha256:f1b639bcb63b3e122acdbf8a2efbe99e45c0491a75767dfaef1d83623bae6b30',
    validatedVaultRevision: REVISION_A,
    sourceFindings: [['STALE_BASE_REVISION', 'error']],
    snapshotTruncated: false,
    snapshotSummary: 'Validation result is stale relative to the observed Vault revision.'
  },
  findings: [
    {
      code: 'STALE_VAULT_REVISION',
      severity: 'BLOCKING',
      message: 'The proposal or validation result is stale relative to the observed Vault revision.',
      details: [
        ['expected', REVISION_A],
        ['observed', REVISION_B],
        ['validated', REVISION_A]
      ]
    }
  ],
  proposedContent: proposedContent({
    title: 'Control plane boundary',
    canonical_scope: 'architecture.control-plane'
  }),
  metadataChanges: [],
  beforeSourceByteHash: null,
  beforeTextRawHash: null,
  beforeSemanticTextHash: null,
  proposedTextRawHash: 'sha256:48384b29c366033e1b206fc1de04846397400cf4c360816e192739f63b1c7cc6',
  proposedSemanticTextHash: 'sha256:b6171bd597f888487926af6d62f1275f8d1e07f6dff4d89766ab60a73049d5da',
  textDiff: {
    preview: null,
    previewTruncated: false,
    fullDiffAvailable: false,
    fullDiffHash: null,
    fullDiffUtf8Bytes: null
  },
  representationDelta: null,
  humanReviewPreview: {
    text: 'BLOCKED: stale review. Normal change material is suppressed.',
    truncated: false
  }
};

const truncated: ReviewCenterItem = {
  id: 'review-truncated-diff',
  fixture: true,
  fixtureLabel: 'Truncated diff fixture',
  status: 'REVIEW_REQUIRED',
  proposalId: 'kprop:1d96a2b9415ca85f4673cd95b327d625b1802f61bd8070458134b841ceaceca2',
  proposalContentHash: 'sha256:b6171bd597f888487926af6d62f1275f8d1e07f6dff4d89766ab60a73049d5da',
  reviewArtifactIdentity: 'kreview:a44e147813d992edd07d328a3bf056b68cbed059b9f379cdaf67e60f1337085c',
  changeIdentity: 'kchange:03a52db9b90dd1f66ca88064ab5481f72c94c8420a913e355fd5b49671d87e21',
  operation: 'UPDATE_EXISTING',
  targetStableId: 'architecture.review-center',
  expectedVaultRevision: REVISION_C,
  observedVaultRevision: REVISION_C,
  validation: {
    outcome: 'VALID',
    contractVersion: 'localcomet.knowledge-change-proposal/1.0',
    proposalContentHash: 'sha256:b6171bd597f888487926af6d62f1275f8d1e07f6dff4d89766ab60a73049d5da',
    validatedVaultRevision: REVISION_C,
    sourceFindings: [],
    snapshotTruncated: true,
    snapshotSummary: 'Validation snapshot preview is bounded; exact review identity remains available.'
  },
  findings: [
    {
      code: 'TARGET_STATE_COMPARISON_UNAVAILABLE',
      severity: 'REVIEW',
      message: 'Historical target drift is not claimed without a trusted baseline.',
      details: [['expected_vault_revision', REVISION_C]]
    }
  ],
  proposedContent: proposedContent({
    title: 'Review Center user interface',
    body_text: '# Review Center\n\nThe fixture contains a bounded diff preview.\n',
    canonical_scope: 'architecture.review-center',
    releases: ['v6.84.5.1e9b', 'Review Center Phase 1'],
    source_paths: ['desktop/localcomet-desktop/src/lib/components/review/ReviewCenterWorkspace.svelte']
  }),
  metadataChanges: [
    {
      field: 'releases',
      before: ['v6.84.5.1e9b'],
      after: ['v6.84.5.1e9b', 'Review Center Phase 1']
    }
  ],
  beforeSourceByteHash: 'sha256:b6171bd597f888487926af6d62f1275f8d1e07f6dff4d89766ab60a73049d5da',
  beforeTextRawHash: 'sha256:4188cb7d894dcd814c8e997f4061b565b3b19dc3b5d9a78daf1a4d9eb3600885',
  beforeSemanticTextHash: 'sha256:4188cb7d894dcd814c8e997f4061b565b3b19dc3b5d9a78daf1a4d9eb3600885',
  proposedTextRawHash: 'sha256:400075069c197bbcb0114c66fdcaefa53e224de63bbe58f67f9af54691c996fa',
  proposedSemanticTextHash: 'sha256:580e36de86fe5fde24c0d67de903eacf0531bedc5c7e15020580624bf3fbd2f5',
  textDiff: {
    preview: '--- before-body/architecture.review-center\n+++ after-body/architecture.review-center\n@@ -1,4 +1,7 @@\n # Review Center\n+\n+Read-only fixture review queue.\n+No Tauri command is called.\n ... REVIEW_DIFF_PREVIEW_TRUNCATED ...\n',
    previewTruncated: true,
    fullDiffAvailable: true,
    fullDiffHash: 'sha256:4188cb7d894dcd814c8e997f4061b565b3b19dc3b5d9a78daf1a4d9eb3600885',
    fullDiffUtf8Bytes: 8192
  },
  representationDelta: {
    identity: 'sha256:34ec938dfc85d8379000a0fd8225dc13a8975dc4b851c920a1a7377c61bde28f',
    beforePresent: true,
    afterPresent: true,
    beforeLineEndings: {
      label: 'LF',
      crlfCount: 0,
      lfCount: 4,
      crCount: 0,
      terminalNewline: true
    },
    afterLineEndings: {
      label: 'LF',
      crlfCount: 0,
      lfCount: 7,
      crCount: 0,
      terminalNewline: true
    },
    terminalNewlineChanged: false,
    afterSourceBytesKnown: false,
    sourceBytesChangedTextIdentical: false,
    rawTextChangedSemanticEqual: false,
    semanticContentChanged: true
  },
  humanReviewPreview: {
    text: 'Review preview is bounded. The truncation marker is explicit and identities remain exact.\n... REVIEW_DIFF_PREVIEW_TRUNCATED ...',
    truncated: true
  }
};

export const REVIEW_FIXTURES: readonly ReviewCenterItem[] = deepFreeze([
  metadataOnly,
  representationOnly,
  blocked,
  truncated
]);

export const REVIEW_FIXTURE_COUNT = REVIEW_FIXTURES.length;
