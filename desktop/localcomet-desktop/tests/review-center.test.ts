import { render } from 'svelte/server';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DecisionConfirmationDialog from '../src/lib/components/review/DecisionConfirmationDialog.svelte';
import RepresentationDeltaPanel from '../src/lib/components/review/RepresentationDeltaPanel.svelte';
import ReviewCenterWorkspace from '../src/lib/components/review/ReviewCenterWorkspace.svelte';
import ReviewDecisionPanel from '../src/lib/components/review/ReviewDecisionPanel.svelte';
import ReviewFindingsPanel from '../src/lib/components/review/ReviewFindingsPanel.svelte';
import ReviewIdentityPanel, {
  getReviewIdentityRows,
  isReviewCopyActivationKey,
  writeReviewValueToClipboard
} from '../src/lib/components/review/ReviewIdentityPanel.svelte';
import ReviewMetadataPanel from '../src/lib/components/review/ReviewMetadataPanel.svelte';
import ReviewQueueSidebar from '../src/lib/components/review/ReviewQueueSidebar.svelte';
import ReviewTextDiffPanel from '../src/lib/components/review/ReviewTextDiffPanel.svelte';
import { REVIEW_FIXTURES } from '../src/lib/data/reviewFixtures';
import { en } from '../src/lib/i18n/en';
import { ru } from '../src/lib/i18n/ru';
import { setLocale } from '../src/lib/i18n';
import {
  resetReviewCenterStore,
  reviewCenterState,
  reviewQueue,
  selectedReview,
  selectedReviewId
} from '../src/lib/stores/reviewCenter';
import {
  PROPOSED_CONTENT_FIELDS,
  sortReviewFindings,
  type FixtureReviewCenterItem,
  type KnowledgeChangeReviewProjection,
  type RealReviewCenterItem,
  type ReviewCenterItem
} from '../src/lib/types/knowledgeReview';

const implementationFiles = [
  '../src/lib/types/knowledgeReview.ts',
  '../src/lib/bridge/knowledgeReview.ts',
  '../src/lib/data/reviewFixtures.ts',
  '../src/lib/stores/reviewCenter.ts',
  '../src/lib/components/review/ReviewCenterWorkspace.svelte',
  '../src/lib/components/review/ReviewQueueSidebar.svelte',
  '../src/lib/components/review/ReviewIdentityPanel.svelte',
  '../src/lib/components/review/ReviewValidationPanel.svelte',
  '../src/lib/components/review/ReviewFindingsPanel.svelte',
  '../src/lib/components/review/ReviewMetadataPanel.svelte',
  '../src/lib/components/review/ReviewTextDiffPanel.svelte',
  '../src/lib/components/review/RepresentationDeltaPanel.svelte',
  '../src/lib/components/review/ReviewDecisionPanel.svelte',
  '../src/lib/components/review/DecisionConfirmationDialog.svelte',
  '../src/lib/components/review/ReviewCommandBar.svelte',
  '../src/lib/components/review/ReviewDiagnosticsPanel.svelte',
  '../src/lib/components/review/ReviewActivityTimeline.svelte',
  '../src/lib/stores/shellStore.ts',
  '../src/lib/components/shell/NavigationRail.svelte',
  '../src/lib/components/shell/AppShell.svelte'
] as const;

const sourceModules = import.meta.glob('../src/**/*.{css,svelte,ts}', {
  eager: true,
  query: '?raw',
  import: 'default'
}) as Record<string, string>;

function source(relativePath: string): string {
  const content = sourceModules[relativePath];
  if (typeof content !== 'string') {
    throw new Error(`Source fixture not found: ${relativePath}`);
  }
  return content;
}

function asRealReview(fixtureReview: ReviewCenterItem): RealReviewCenterItem {
  const {
    fixture: _fixture,
    fixtureLabel: _fixtureLabel,
    source: _source,
    ...review
  } = fixtureReview as FixtureReviewCenterItem;
  return {
    ...review,
    fixture: false,
    source: 'LOCAL_CONTROL_PLANE',
    stale: false,
    detailProjectionTruncated: false,
    rawProjection: {} as KnowledgeChangeReviewProjection
  };
}

describe('Knowledge Operations Command Center components and boundaries', () => {
  beforeEach(() => {
    setLocale('en');
    resetReviewCenterStore();
  });

  it('renders a truthful empty production queue without fixture fallback', () => {
    const html = render(ReviewQueueSidebar).body;
    expect(html).toContain('0/0');
    expect(html).toContain('No review artifacts');
    expect(html).toContain('disabled');
    expect(html).not.toContain('aria-current="true"');
    expect(html).toContain('role="listbox"');
  });

  it('renders the idle workspace truthfully before its on-mount request', () => {
    const html = render(ReviewCenterWorkspace).body;
    expect(html).toContain('<main');
    expect(html).toContain('<article');
    expect(html).toContain('<section');
    expect(html).toContain('LocalComet Review Center workspace');
    expect(html).toContain('Idle');
    expect(html).toContain('has not been requested yet');
    expect(html).toContain('LOCAL CONTROL PLANE');
    expect(html).not.toContain('FIXTURE');
  });

  it('renders every exact identity field with wrapping and Copy actions', () => {
    const review = REVIEW_FIXTURES[0];
    const html = render(ReviewIdentityPanel, { props: { review } }).body;
    expect(html).toContain(review.proposalId);
    expect(html).toContain(review.reviewArtifactIdentity);
    expect(html).toContain(review.changeIdentity);
    expect(html).toContain(review.expectedVaultRevision);
    expect(html).toContain(review.observedVaultRevision);
    expect(html).toContain(review.targetStableId);
    expect(html.match(/>Copy</g)?.length).toBeGreaterThanOrEqual(5);

    const css = source('../src/lib/components/review/ReviewIdentityPanel.svelte');
    expect(css).toContain('overflow-wrap: anywhere');
    expect(css).toContain('min-height: 44px');
  });

  it('derives identity rows from the currently selected review', () => {
    const clear = REVIEW_FIXTURES[0];
    const blocked = REVIEW_FIXTURES.find((review) => review.status === 'BLOCKED')!;
    const clearRows = Object.fromEntries(
      getReviewIdentityRows(clear).map((row) => [row.key, row.value])
    );
    const blockedRows = Object.fromEntries(
      getReviewIdentityRows(blocked).map((row) => [row.key, row.value])
    );

    expect(clearRows.change).toBe(clear.changeIdentity);
    expect(blockedRows.proposal).toBe(blocked.proposalId);
    expect(blockedRows.review).toBe(blocked.reviewArtifactIdentity);
    expect(blockedRows.change).toBeNull();
    expect(blockedRows.proposal).not.toBe(clearRows.proposal);

    const componentSource = source('../src/lib/components/review/ReviewIdentityPanel.svelte');
    expect(componentSource).toContain('$: rows = getReviewIdentityRows(review);');
  });

  it('reports clipboard success and failure without swallowing rejected writes', async () => {
    const successfulWrite = vi.fn().mockResolvedValue(undefined);
    const rejectedWrite = vi.fn().mockRejectedValue(new Error('clipboard denied'));
    const pendingWrite = vi.fn(() => new Promise<void>(() => {}));

    await expect(
      writeReviewValueToClipboard('kprop:test', { writeText: successfulWrite })
    ).resolves.toBe(true);
    expect(successfulWrite).toHaveBeenCalledWith('kprop:test');

    await expect(
      writeReviewValueToClipboard('kprop:test', { writeText: rejectedWrite })
    ).resolves.toBe(false);
    await expect(
      writeReviewValueToClipboard('kprop:test', { writeText: pendingWrite }, 1)
    ).resolves.toBe(false);
    await expect(writeReviewValueToClipboard('kprop:test', undefined)).resolves.toBe(false);

    expect(isReviewCopyActivationKey('Enter')).toBe(true);
    expect(isReviewCopyActivationKey(' ')).toBe(true);
    expect(isReviewCopyActivationKey('Tab')).toBe(false);

    const html = render(ReviewIdentityPanel, { props: { review: REVIEW_FIXTURES[0] } }).body;
    expect(html).toContain('aria-live="polite"');
    expect(html).toContain('aria-atomic="true"');
    const componentSource = source('../src/lib/components/review/ReviewIdentityPanel.svelte');
    expect(componentSource).toContain('onkeydown={(event) => handleCopyKeydown(event, key, value)}');
  });

  it('renders all 18 ProposedNoteContent fields and metadata-only changes', () => {
    const review = REVIEW_FIXTURES[0];
    const html = render(ReviewMetadataPanel, { props: { review } }).body;
    expect(PROPOSED_CONTENT_FIELDS).toHaveLength(18);
    for (const field of PROPOSED_CONTENT_FIELDS) {
      expect(html).toContain(`>${field}</code>`);
    }
    expect(html).toContain('Human-readable knowledge review lifecycle');
    expect(html).toContain('Knowledge review lifecycle');
    expect(html).toContain('Before');
    expect(html).toContain('After');
  });

  it('sorts findings by the fixed e9b order before rendering', () => {
    const base = REVIEW_FIXTURES[1];
    const review: ReviewCenterItem = {
      ...base,
      findings: [
        {
          code: 'PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT',
          severity: 'REVIEW',
          message: 'semantic',
          details: []
        },
        {
          code: 'STALE_VAULT_REVISION',
          severity: 'BLOCKING',
          message: 'stale',
          details: []
        },
        {
          code: 'TARGET_STATE_COMPARISON_UNAVAILABLE',
          severity: 'REVIEW',
          message: 'baseline',
          details: []
        }
      ]
    };
    expect(sortReviewFindings(review.findings).map((finding) => finding.code)).toEqual([
      'STALE_VAULT_REVISION',
      'TARGET_STATE_COMPARISON_UNAVAILABLE',
      'PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT'
    ]);
    const html = render(ReviewFindingsPanel, { props: { review } }).body;
    expect(html.indexOf('STALE_VAULT_REVISION')).toBeLessThan(
      html.indexOf('TARGET_STATE_COMPARISON_UNAVAILABLE')
    );
    expect(html.indexOf('TARGET_STATE_COMPARISON_UNAVAILABLE')).toBeLessThan(
      html.indexOf('PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT')
    );
  });

  it('renders BLOCKED review without normal change identity, diff, or representation material', () => {
    const blocked = REVIEW_FIXTURES.find((review) => review.status === 'BLOCKED')!;
    const identityHtml = render(ReviewIdentityPanel, { props: { review: blocked } }).body;
    const diffHtml = render(ReviewTextDiffPanel, { props: { review: blocked } }).body;
    const representationHtml = render(RepresentationDeltaPanel, { props: { review: blocked } }).body;
    expect(identityHtml).toContain('Unavailable');
    expect(identityHtml).not.toContain('kchange:');
    expect(diffHtml).toContain('No normal change material');
    expect(representationHtml).toContain('unavailable for this BLOCKED review');
  });

  it('keeps a representation-only change visible when the semantic body diff is empty', () => {
    const review = REVIEW_FIXTURES.find(
      (item) => item.id === 'review-representation-only'
    )!;
    const diffHtml = render(ReviewTextDiffPanel, { props: { review } }).body;
    const representationHtml = render(RepresentationDeltaPanel, { props: { review } }).body;
    expect(diffHtml).toContain('(semantic body diff is empty)');
    expect(representationHtml).toContain('REPRESENTATION-ONLY CHANGE');
    expect(representationHtml).toContain('CRLF');
    expect(representationHtml).toContain('LF');
    expect(representationHtml).toContain('Raw text changed with semantic equality');
  });

  it('labels truncated previews and never presents the preview as the complete diff', () => {
    const review = REVIEW_FIXTURES.find((item) => item.id === 'review-truncated-diff')!;
    const html = render(ReviewTextDiffPanel, { props: { review } }).body;
    expect(html).toContain('TRUNCATED');
    expect(html).toContain('Diff preview');
    expect(html).toContain('Bounded preview — not the full diff.');
    expect(html).toContain('REVIEW_DIFF_PREVIEW_TRUNCATED');
    expect(html).not.toContain('>Full diff<');
  });

  it('surfaces aggregate bounded-detail truth for a rendered real artifact', () => {
    const realReview = {
      ...asRealReview(REVIEW_FIXTURES[0]),
      detailProjectionTruncated: true
    };
    reviewQueue.set(Object.freeze([{
      id: realReview.id,
      fixture: false,
      source: 'LOCAL_CONTROL_PLANE',
      status: realReview.status,
      blocked: realReview.status === 'BLOCKED',
      proposalId: realReview.proposalId,
      targetStableId: realReview.targetStableId,
      operation: realReview.operation,
      expectedVaultRevision: realReview.expectedVaultRevision,
      observedVaultRevision: realReview.observedVaultRevision,
      reviewArtifactIdentity: realReview.reviewArtifactIdentity,
      changeIdentity: realReview.changeIdentity,
      findingCount: realReview.findings.length,
      normalChangeMaterialPresent: realReview.changeIdentity !== null,
      detailProjectionTruncated: true,
      stale: false
    }]));
    selectedReviewId.set(realReview.id);
    selectedReview.set(realReview);
    reviewCenterState.set({
      status: 'ready',
      source: 'LOCAL_CONTROL_PLANE',
      error: null,
      failedRequest: null,
      retryable: false,
      totalCount: 1,
      returnedCount: 1,
      truncated: false,
      nextOffset: null
    });

    const queueHtml = render(ReviewQueueSidebar).body;
    const workspaceHtml = render(ReviewCenterWorkspace).body;
    expect(queueHtml).toContain('BOUNDED DETAIL');
    expect(workspaceHtml).toContain('Projected detail is bounded');
    expect(workspaceHtml).toContain('previews, not complete source material');
    expect(workspaceHtml).toContain('LOCAL CONTROL PLANE');
  });

  it('renders an accessible modal confirmation contract', () => {
    const review = REVIEW_FIXTURES[0];
    const html = render(DecisionConfirmationDialog, {
      props: {
        review,
        intent: 'REQUEST_CHANGES',
        comment: '',
        errorKey: 'review.decision.comment_required'
      }
    }).body;
    expect(html).toContain('role="dialog"');
    expect(html).toContain('aria-modal="true"');
    expect(html).toContain('aria-labelledby="review-decision-dialog-title"');
    expect(html).toContain('REQUEST CHANGES requires a non-empty comment.');
    expect(html).toContain('HARD STOP');
  });

  it('wires Escape, focus trap, and focus return into the actual dialog component', () => {
    const dialogSource = source('../src/lib/components/review/DecisionConfirmationDialog.svelte');
    expect(dialogSource).toContain("event.key === 'Escape'");
    expect(dialogSource).toContain("event.key !== 'Tab'");
    expect(dialogSource).toContain('cycleDialogFocusIndex');
    expect(dialogSource).toContain('querySelectorAll<HTMLElement>(focusableSelector)');
    expect(dialogSource).toContain('(triggerElement ?? previousFocus)?.focus()');
    expect(dialogSource).toContain('aria-modal="true"');
  });

  it('disables APPROVE visibly for BLOCKED reviews', () => {
    const blocked = REVIEW_FIXTURES.find((review) => review.status === 'BLOCKED')!;
    const html = render(ReviewDecisionPanel, { props: { review: blocked } }).body;
    expect(html).toContain('disabled');
    expect(html).toContain('aria-disabled="true"');
    expect(html).toContain('APPROVE is unavailable for a BLOCKED review.');
  });

  it('enables exact fresh real e9c decisions while retaining HARD STOP', () => {
    const realReview = asRealReview(REVIEW_FIXTURES[0]);
    const decisionHtml = render(ReviewDecisionPanel, { props: { review: realReview } }).body;
    const identityHtml = render(ReviewIdentityPanel, { props: { review: realReview } }).body;
    expect(decisionHtml).toContain('REAL e9c DECISION');
    expect(decisionHtml).toContain('genuine immutable e9c HumanReviewDecision');
    expect(decisionHtml).toContain('HARD STOP');
    expect(decisionHtml).toContain('no authoritative action occurs');
    expect(identityHtml).toContain('LOCAL CONTROL PLANE');
    expect(identityHtml).not.toContain('FIXTURE');
  });

  it('has complete EN and RU key parity including Review Center keys', () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(ru).sort());
    const reviewKeys = Object.keys(en).filter((key) =>
      key === 'nav.review_center' || key.startsWith('review.')
    );
    expect(reviewKeys.length).toBeGreaterThan(120);
    for (const key of reviewKeys) {
      expect(en[key]).toBeTruthy();
      expect(ru[key]).toBeTruthy();
    }
  });

  it('contains exactly the five fixed bounded Knowledge Operations commands', () => {
    const bridgePath = '../src/lib/bridge/knowledgeReview.ts';
    const bridge = source(bridgePath);
    const nonBridge = implementationFiles
      .filter((path) => path !== bridgePath)
      .map(source)
      .join('\n');
    expect(bridge).toContain("invoke<unknown>('knowledge_review_list', { offset, limit })");
    expect(bridge).toContain(
      "invoke<unknown>('knowledge_review_get', { reviewArtifactIdentity })"
    );
    expect(bridge).toContain("invokeSnapshot('knowledge_review_snapshot', false)");
    expect(bridge).toContain("invokeSnapshot('knowledge_review_refresh', true)");
    expect(bridge).toContain("invoke<unknown>('knowledge_review_decision_create', {");
    expect(bridge).not.toContain('registerReviewArtifact');
    expect(bridge).not.toContain('knowledge_review_raw');
    expect(nonBridge).not.toMatch(/\binvoke\s*(?:<[^>]+>)?\s*\(/);
    expect(nonBridge).not.toContain('@tauri-apps/api');
  });

  it('keeps production loading independent of fixture registration and fallback', () => {
    const store = source('../src/lib/stores/reviewCenter.ts');
    expect(store).not.toContain('REVIEW_FIXTURES');
    expect(store).not.toContain('installReviewFixturesForTest');
    expect(store).not.toContain('registerReviewArtifact');
    expect(store).toContain('status: \'loading\'');
    expect(store).toContain('status: \'empty\'');
    expect(store).toContain('status: \'ready\'');
    expect(store).toContain('status: \'error\'');
  });

  it('contains no Review Center persistence through browser storage', () => {
    const combined = implementationFiles.map(source).join('\n');
    expect(combined).not.toMatch(/\blocalStorage\b/);
    expect(combined).not.toMatch(/\bsessionStorage\b/);
    expect(combined).not.toMatch(/\bindexedDB\b/);
  });

  it('creates decision evidence without filesystem, Vault-write, publication, or execution APIs', () => {
    const combined = implementationFiles.map(source).join('\n');
    expect(combined).not.toMatch(/\bwriteFile(Sync)?\s*\(/);
    expect(combined).not.toMatch(/\bappendFile(Sync)?\s*\(/);
    expect(combined).not.toMatch(/\bpublish[A-Z_a-z]*\s*\(/);
    expect(combined).not.toMatch(/\bmerge[A-Z_a-z]*\s*\(/);
    expect(combined).not.toMatch(/\bexecute[A-Z_a-z]*\s*\(/);
    expect(combined).toContain('HumanReviewDecision');
    expect(combined).toContain('kdecision:');
    expect(combined).toContain('vault_modified');
    expect(combined).toContain('hard_stop');
    expect(combined).not.toContain('knowledge.review.publish');
    expect(combined).not.toContain('knowledge.review.write');
  });

  it('contains no runtime network transport in the Knowledge Operations surface', () => {
    const combined = implementationFiles.map(source).join('\n');
    expect(combined).not.toMatch(/\bfetch\s*\(/);
    expect(combined).not.toMatch(/\bWebSocket\s*\(/);
    expect(combined).not.toMatch(/\bEventSource\s*\(/);
    expect(combined).not.toMatch(/\bXMLHttpRequest\b/);
    expect(combined).not.toMatch(/https?:\/\//);
  });

  it('keeps session activity bounded and excludes decision comments and actor metadata', () => {
    const store = source('../src/lib/stores/reviewCenter.ts');
    expect(store).toContain('MAX_REVIEW_ACTIVITY_ITEMS');
    expect(store).toContain('.slice(-MAX_REVIEW_ACTIVITY_ITEMS)');
    expect(store).not.toMatch(/activity[^\n]*(?:comment|actorIdentifier|actorDisplayName)/i);
    expect(store).not.toContain('rawProjection: activity');
  });

  it('retains exact source-level gates for blocked approval, paths, contracts, and truncation', () => {
    const store = source('../src/lib/stores/reviewCenter.ts');
    const bridge = source('../src/lib/bridge/knowledgeReview.ts');
    expect(store).toContain("if (intent === 'APPROVE' && review.status === 'BLOCKED')");
    expect(bridge).toContain("value.startsWith('/')");
    expect(bridge).toContain('previewTruncated: projection.diff.preview_truncated');
    expect(bridge).toContain(
      'object.contract !== KNOWLEDGE_REVIEW_DECISION_CREATE_CONTRACT'
    );
  });

  it('implements the 920 px queue selector and 760 px single-column decision layout', () => {
    const queueSource = source('../src/lib/components/review/ReviewQueueSidebar.svelte');
    const workspaceSource = source('../src/lib/components/review/ReviewCenterWorkspace.svelte');
    const decisionSource = source('../src/lib/components/review/ReviewDecisionPanel.svelte');
    expect(queueSource).toContain('@media (max-width: 920px)');
    expect(queueSource).toContain('.review-queue-mobile');
    expect(workspaceSource).toContain('@media (max-width: 760px)');
    expect(workspaceSource).toContain('grid-template-columns: 1fr');
    expect(decisionSource).toContain('@media (max-width: 760px)');
    expect(decisionSource).toContain('grid-template-columns: 1fr');
  });

  it('provides visible focus styles and minimum 44 px touch targets', () => {
    const reviewSources = implementationFiles
      .filter((path) => path.includes('/components/'))
      .map(source)
      .join('\n');
    expect(reviewSources).toContain(':focus-visible');
    expect(reviewSources).toContain('box-shadow: var(--focus-ring)');
    expect(reviewSources).toContain('min-height: 44px');
  });

  it('preserves chat and uses the existing Audit rail slot for Review Center', () => {
    const appShell = source('../src/lib/components/shell/AppShell.svelte');
    const navigation = source('../src/lib/components/shell/NavigationRail.svelte');
    expect(appShell).toContain("$activeWorkspace === 'chat'");
    expect(appShell).toContain('<MessageList />');
    expect(appShell).toContain('<MessageComposer />');
    expect(appShell).toContain('<ReviewCenterWorkspace />');
    expect(navigation).toContain("icon: 'audit'");
    expect(navigation).toContain("workspace: 'review'");
    expect(navigation).toContain("key: 'nav.review_center'");
    expect(navigation).toContain("key: 'nav.diagnostics', enabled: true, workspace: 'chat'");
  });
});
