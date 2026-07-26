# Полный исходный код (продолжение)

### ПУТЬ: desktop/localcomet-desktop/tests/review-center.test.ts (491 строк, 22185 байт)

````typescript
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

  it('preserves chat and Review Center while keeping the primary rail minimal', () => {
    const appShell = source('../src/lib/components/shell/AppShell.svelte');
    const navigation = source('../src/lib/components/shell/NavigationRail.svelte');
    expect(appShell).toContain("$activeWorkspace === 'chat'");
    expect(appShell).toContain('<MessageList />');
    expect(appShell).toContain('<MessageComposer />');
    expect(appShell).toContain('<ReviewCenterWorkspace />');
    expect(navigation).toContain("$t('nav.chat')");
    expect(navigation).toContain("$t('nav.settings')");
    expect(navigation).toContain('data-settings-trigger="true"');
    expect(navigation.match(/type="button"/g)).toHaveLength(3);
    expect(navigation).not.toContain('onkeydown=');
    expect(navigation).not.toContain("'nav.review_center'");
    expect(navigation).not.toContain("'nav.diagnostics'");
    expect(navigation).not.toContain("'nav.tasks'");
  });
});
````

### ПУТЬ: desktop/localcomet-desktop/tests/settings.test.ts (90 строк, 3653 байт)

````typescript
import { render } from 'svelte/server';
import { beforeEach, describe, expect, it } from 'vitest';
import SettingsPanel from '../src/lib/components/shell/SettingsPanel.svelte';
import { setLocale } from '../src/lib/i18n';
import { controlPlaneStore, resetControlPlaneStore } from '../src/lib/stores/controlPlane';
import {
  resetShellStores,
  setDiagnosticsPanelOpen,
  setThemeMode
} from '../src/lib/stores/shellStore';

function settingsHtml(language: 'ru' | 'en' = 'ru'): string {
  setLocale(language);
  return render(SettingsPanel).body;
}

beforeEach(() => {
  resetControlPlaneStore();
  resetShellStores();
  setLocale('ru');
});

describe('minimal Settings surface', () => {
  it('renders the authorized Settings sections including the bounded Models manager', () => {
    const html = settingsHtml('en');
    for (const section of ['Appearance', 'Language', 'Diagnostics', 'Models', 'About']) {
      expect(html).toContain(section);
    }
    expect(html).toContain('Only the approved bootstrap engine and model can be installed here');
    expect(html).toContain('assistant itself does not gain internet access');
    for (const excluded of ['API key', 'Account', 'Cloud', 'Telemetry']) {
      expect(html).not.toContain(excluded);
    }
  });

  it('exposes theme and language choices as semantic pressed buttons', () => {
    const html = settingsHtml('en');
    expect(html).toContain('title="System"');
    expect(html).toContain('title="Light"');
    expect(html).toContain('title="Dark"');
    expect(html).toContain('title="Русский"');
    expect(html).toContain('title="English"');
    expect(html.match(/aria-pressed=/g)?.length).toBeGreaterThanOrEqual(6);
  });

  it('renders repository-proven About values', () => {
    const html = settingsHtml('en');
    expect(html).toContain('LocalComet');
    expect(html).toContain('v6.84.5.1');
    expect(html).toContain('v6.84.5.1b');
    expect(html).toContain('UNSIGNED_INTERNAL_BUILD');
  });

  it('shows localized read-only capability boundaries without enable controls', () => {
    const english = settingsHtml('en');
    for (const value of ['Current capabilities', 'Local chat', 'Local model inference', 'Internet', 'Email', 'Browser', 'Files', 'Vault', 'Computer Use', 'Shell', 'External tools']) {
      expect(english).toContain(value);
    }
    expect(english).toContain('Project context is unavailable');
    expect(english).toContain('This is not long-term memory');
    expect(english).not.toContain('Enable internet');

    const russian = settingsHtml('ru');
    expect(russian).toContain('Текущие возможности');
    expect(russian).toContain('Контекст проекта недоступен');
    expect(russian).toContain('Это не долговременная память');
  });

  it('shows the existing Control Plane state read-only', () => {
    controlPlaneStore.update((state) => ({ ...state, bridgeState: 'READY' }));
    const html = settingsHtml('en');
    expect(html).toContain('Control Plane: Connected');
    expect(html).toContain('<output');
  });

  it('reflects existing theme and Diagnostics state', () => {
    setThemeMode('dark');
    setDiagnosticsPanelOpen(true);
    const html = settingsHtml('en');
    expect(html).toMatch(/aria-pressed="true"[^>]*title="Dark"/);
    expect(html).toContain('Hide Diagnostics');
  });

  it('has a reachable close control and non-modal dialog semantics', () => {
    const html = settingsHtml('en');
    expect(html).toContain('role="dialog"');
    expect(html).toContain('aria-modal="false"');
    expect(html).toContain('aria-label="Close settings"');
  });
});
````

### ПУТЬ: desktop/localcomet-desktop/tests/shellStore.test.ts (310 строк, 10510 байт)

````typescript
import { describe, expect, it, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import { approvalCard, mockCodeBlock, mockToolCall, modeOptions, verificationCard } from '../src/lib/data/mockData';
import {
  MAX_DRAFT_LENGTH,
  activeWorkspace,
  activeInspectorSection,
  appendMockMessage,
  closeCommandPalette,
  closeDiagnosticsPanel,
  closeModelSetup,
  closeSettings,
  commandPaletteOpen,
  handleGlobalEscape,
  inspectorDrawerOpen,
  inspectorVisible,
  mockMessages,
  modelConnected,
  modelSetupDrawerOpen,
  modelSetupMode,
  openSettings,
  openCommandPalette,
  openModelSetup,
  resetShellStores,
  selectedMode,
  selectedModel,
  setSelectedMode,
  setSelectedModel,
  setActiveWorkspace,
  setDiagnosticsPanelOpen,
  setThemeMode,
  settingsPanelOpen,
  settingsSection,
  sidebarExpanded,
  themeMode,
  toolsPopoverOpen
} from '../src/lib/stores/shellStore';
import { UI_PREFERENCES_KEY } from '../src/lib/stores/uiPreferences';

function createMemoryStorage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() { return values.size; },
    clear: () => values.clear(),
    getItem: (key: string) => values.get(key) ?? null,
    key: (index: number) => [...values.keys()][index] ?? null,
    removeItem: (key: string) => { values.delete(key); },
    setItem: (key: string, value: string) => { values.set(key, value); }
  };
}

Object.defineProperty(globalThis, 'localStorage', {
  configurable: true,
  value: createMemoryStorage()
});

describe('shell stores', () => {
  beforeEach(() => {
    localStorage.clear();
    resetShellStores();
  });

  it('defaults theme to system and can change to light and dark', () => {
    expect(get(themeMode)).toBe('system');
    setThemeMode('light');
    expect(get(themeMode)).toBe('light');
    setThemeMode('dark');
    expect(get(themeMode)).toBe('dark');
  });

  it('persists theme in the bounded preference record', () => {
    setThemeMode('light');
    expect(get(themeMode)).toBe('light');
    expect(JSON.parse(localStorage.getItem(UI_PREFERENCES_KEY) ?? '{}')).toEqual({
      theme: 'light',
      locale: 'ru',
      diagnosticsPanel: 'closed'
    });
  });

  it('initializes persisted theme and diagnostics state on reset', () => {
    localStorage.setItem(UI_PREFERENCES_KEY, JSON.stringify({
      theme: 'dark',
      locale: 'en',
      diagnosticsPanel: 'open'
    }));
    resetShellStores();
    expect(get(themeMode)).toBe('dark');
    expect(get(inspectorVisible)).toBe(true);
    expect(get(inspectorDrawerOpen)).toBe(true);
  });

  it('opens and closes Settings without persisting its open state', () => {
    openSettings();
    expect(get(settingsPanelOpen)).toBe(true);
    expect(localStorage.getItem(UI_PREFERENCES_KEY)).toBeNull();
    closeSettings();
    expect(get(settingsPanelOpen)).toBe(false);
  });

  it('opens a requested Settings section and resets it on close', () => {
    openSettings('models');
    expect(get(settingsSection)).toBe('models');
    closeSettings();
    expect(get(settingsSection)).toBe('interface');
  });

  it('changes workspace without silently changing the diagnostics preference', () => {
    setDiagnosticsPanelOpen(true);
    setActiveWorkspace('setup');
    expect(get(activeWorkspace)).toBe('setup');
    expect(get(inspectorVisible)).toBe(true);
    expect(JSON.parse(localStorage.getItem(UI_PREFERENCES_KEY) ?? '{}').diagnosticsPanel).toBe('open');
  });

  it('sets, persists, and closes diagnostics through bounded helpers', () => {
    setDiagnosticsPanelOpen(true);
    expect(get(inspectorVisible)).toBe(true);
    expect(get(inspectorDrawerOpen)).toBe(true);
    expect(JSON.parse(localStorage.getItem(UI_PREFERENCES_KEY) ?? '{}').diagnosticsPanel).toBe('open');

    closeDiagnosticsPanel();
    expect(get(inspectorVisible)).toBe(false);
    expect(get(inspectorDrawerOpen)).toBe(false);
    expect(JSON.parse(localStorage.getItem(UI_PREFERENCES_KEY) ?? '{}').diagnosticsPanel).toBe('closed');
  });

  it('has deterministic sidebar and inspector defaults', () => {
    expect(get(sidebarExpanded)).toBe(true);
    expect(get(inspectorVisible)).toBe(false);
    expect(get(activeInspectorSection)).toBe('Обзор');
  });

  it('keeps model selection in memory only', () => {
    setSelectedModel('Not configured');
    expect(get(selectedModel)).toBe('Not configured');
  });

  it('supports Chat, Plan, and Agent modes', () => {
    expect(modeOptions).toEqual(['Chat', 'Plan', 'Agent']);
    setSelectedMode('Chat');
    expect(get(selectedMode)).toBe('Chat');
    setSelectedMode('Plan');
    expect(get(selectedMode)).toBe('Plan');
    setSelectedMode('Agent');
    expect(get(selectedMode)).toBe('Agent');
  });

  it('blocks empty and whitespace-only messages', () => {
    const count = get(mockMessages).length;
    expect(appendMockMessage('')).toBe(false);
    expect(appendMockMessage('   \n  ')).toBe(false);
    expect(get(mockMessages)).toHaveLength(count);
  });

  it('appends valid bounded user messages without creating an assistant response', () => {
    const count = get(mockMessages).length;
    expect(appendMockMessage('hello desktop shell')).toBe(true);
    const messages = get(mockMessages);
    expect(messages).toHaveLength(count + 1);
    expect(messages.at(-1)?.role).toBe('user');

    appendMockMessage('x'.repeat(MAX_DRAFT_LENGTH + 50));
    expect(get(mockMessages).at(-1)?.body).toHaveLength(MAX_DRAFT_LENGTH);
  });

  it('keeps disabled fixtures truthful and sanitized', () => {
    const fixture = JSON.stringify({ approvalCard, verificationCard, mockCodeBlock, mockToolCall });
    expect(mockToolCall.status).toBe('SKIPPED');
    expect(verificationCard.status).toBe('Не запускалась');
    expect(fixture).toContain('Не настроено');
    expect(fixture).not.toMatch(/[A-Z]:\\\\(?:Users|Windows|Program Files)|\/Users\/|sk-[A-Za-z0-9]|password|private key/i);
  });

  it('closes the mock tools popover on Escape', () => {
    toolsPopoverOpen.set(true);
    expect(handleGlobalEscape('Escape')).toBe(true);
    expect(get(toolsPopoverOpen)).toBe(false);
  });

  it('opens and closes the command palette, with Escape taking priority', () => {
    openSettings();
    openCommandPalette();
    expect(get(commandPaletteOpen)).toBe(true);

    expect(handleGlobalEscape('Escape')).toBe(true);
    expect(get(commandPaletteOpen)).toBe(false);
    expect(get(settingsPanelOpen)).toBe(true);

    openCommandPalette();
    closeCommandPalette();
    expect(get(commandPaletteOpen)).toBe(false);
  });

  it('closes Settings and diagnostics on Escape and reports whether it acted', () => {
    expect(handleGlobalEscape('Escape')).toBe(false);
    openSettings();
    setDiagnosticsPanelOpen(true);
    expect(handleGlobalEscape('Enter')).toBe(false);
    expect(handleGlobalEscape('Escape')).toBe(true);
    expect(get(settingsPanelOpen)).toBe(false);
    expect(get(inspectorVisible)).toBe(false);
    expect(get(inspectorDrawerOpen)).toBe(false);
    expect(handleGlobalEscape('Escape')).toBe(false);
  });

  it('defaults theme mode to system', () => {
    expect(get(themeMode)).toBe('system');
  });

  it('changes theme mode to light', () => {
    setThemeMode('light');
    expect(get(themeMode)).toBe('light');
  });

  it('changes theme mode to dark', () => {
    setThemeMode('dark');
    expect(get(themeMode)).toBe('dark');
  });

  it('keeps sidebar default deterministic', () => {
    expect(get(sidebarExpanded)).toBe(true);
  });

  it('keeps inspector default deterministic', () => {
    expect(get(inspectorVisible)).toBe(false);
    expect(get(activeInspectorSection)).toBe('Обзор');
  });

  it('supports Chat mode directly', () => {
    setSelectedMode('Chat');
    expect(get(selectedMode)).toBe('Chat');
  });

  it('supports Plan mode directly', () => {
    setSelectedMode('Plan');
    expect(get(selectedMode)).toBe('Plan');
  });

  it('supports Agent mode directly', () => {
    setSelectedMode('Agent');
    expect(get(selectedMode)).toBe('Agent');
  });

  it('prevents empty message append', () => {
    const count = get(mockMessages).length;
    appendMockMessage('');
    expect(get(mockMessages)).toHaveLength(count);
  });

  it('prevents whitespace-only message append', () => {
    const count = get(mockMessages).length;
    appendMockMessage('   ');
    expect(get(mockMessages)).toHaveLength(count);
  });

  it('bounds mock message length', () => {
    appendMockMessage('x'.repeat(MAX_DRAFT_LENGTH + 10));
    expect(get(mockMessages).at(-1)?.body).toHaveLength(MAX_DRAFT_LENGTH);
  });

  it('does not append an assistant response after send', () => {
    const beforeAssistantCount = get(mockMessages).filter((message) => message.role === 'assistant').length;
    appendMockMessage('one user-only message');
    const afterAssistantCount = get(mockMessages).filter((message) => message.role === 'assistant').length;
    expect(afterAssistantCount).toBe(beforeAssistantCount);
  });

  it('contains no real project paths in mock fixtures', () => {
    const fixture = JSON.stringify({ approvalCard, verificationCard, mockCodeBlock, mockToolCall });
    expect(fixture).not.toMatch(/[A-Z]:\\\\(?:Users|Windows|Program Files)|\/Users\//i);
  });

  it('contains no secret-like mock fixtures', () => {
    const fixture = JSON.stringify({ approvalCard, verificationCard, mockCodeBlock, mockToolCall });
    expect(fixture).not.toMatch(/sk-[A-Za-z0-9]|password|private key|BEGIN [A-Z ]*KEY/i);
  });

  it('opens model setup drawer in external mode', () => {
    expect(get(modelSetupDrawerOpen)).toBe(false);
    openModelSetup('external');
    expect(get(modelSetupDrawerOpen)).toBe(true);
    expect(get(modelSetupMode)).toBe('external');
  });

  it('opens model setup drawer in managed mode', () => {
    openModelSetup('managed');
    expect(get(modelSetupDrawerOpen)).toBe(true);
    expect(get(modelSetupMode)).toBe('managed');
  });

  it('closes model setup drawer', () => {
    openModelSetup('external');
    closeModelSetup();
    expect(get(modelSetupDrawerOpen)).toBe(false);
  });

  it('sets model connected state', () => {
    expect(get(modelConnected)).toBe(false);
    // modelConnected is set internally when binding succeeds
  });

  it('closes all popovers on Escape', () => {
    toolsPopoverOpen.set(true);
    openModelSetup('external');
    handleGlobalEscape('Escape');
    expect(get(toolsPopoverOpen)).toBe(false);
    expect(get(modelSetupDrawerOpen)).toBe(false);
  });
});
````

### ПУТЬ: desktop/localcomet-desktop/tests/ui-hygiene.test.ts (130 строк, 6353 байт)

````typescript
import { render } from 'svelte/server';
import { beforeEach, describe, expect, it } from 'vitest';
import Diagnostics from '../src/lib/components/agent/Diagnostics.svelte';
import KnowledgeToggle from '../src/lib/components/knowledge/KnowledgeToggle.svelte';
import ConversationSidebar from '../src/lib/components/shell/ConversationSidebar.svelte';
import NavigationRail from '../src/lib/components/shell/NavigationRail.svelte';
import SettingsPanel from '../src/lib/components/shell/SettingsPanel.svelte';
import MessageComposer from '../src/lib/components/chat/MessageComposer.svelte';
import { setLocale } from '../src/lib/i18n';
import { resetShellStores } from '../src/lib/stores/shellStore';

const sourceModules = import.meta.glob('../src/**/*.{css,svelte,ts}', {
  eager: true,
  query: '?raw',
  import: 'default'
}) as Record<string, string>;

function source(relativePath: string): string {
  const content = sourceModules[relativePath];
  if (typeof content !== 'string') throw new Error('Source fixture not found: ' + relativePath);
  return content;
}

function visibleButtonBlocks(relativePath: string): readonly string[] {
  return source(relativePath).match(/<button\b[\s\S]*?<\/button>/g) ?? [];
}

beforeEach(() => {
  resetShellStores();
  setLocale('ru');
});

describe('UP02-WP01-HF2 visible production controls', () => {
  it('uses a recognizable local gear while preserving settings semantics', () => {
    const icon = source('../src/lib/components/common/Icon.svelte');
    const rail = render(NavigationRail).body;
    expect(icon).toContain('M12.22 2h-.44');
    expect(icon).toContain('<circle cx="12" cy="12" r="3"/>');
    expect(rail).toContain('aria-label="Настройки"');
    expect(rail).toContain('title="Настройки"');
    expect(rail).toContain('data-settings-trigger="true"');
  });

  it('keeps only the real local chat and useful pinned identity', () => {
    const html = render(ConversationSidebar).body;
    expect(html).toContain('Новый чат');
    expect(html).toContain('aria-current="page"');
    for (const removed of ['Демо отмены', 'Позже', 'v6.84.5.1b', 'Frontend', 'Русский UX']) {
      expect(html).not.toContain(removed);
    }
  });

  it('localizes header icon actions and avoids the desktop duplicate sidebar control', () => {
    const header = source('../src/lib/components/shell/ChatHeader.svelte');
    expect(header).toContain("aria-label={$t('sidebar.toggle')}");
    expect(header).toContain("aria-label={$t('diag.toggle')}");
    expect(header).toMatch(/\.sidebar-toggle\s*\{\s*display:\s*none;/s);
    expect(header).toMatch(/@media \(max-width: 920px\)[\s\S]*\.sidebar-toggle\s*\{\s*display:\s*grid;/s);
  });

  it('keeps version and build in About but removes redundant shell and sidebar badges', () => {
    const shell = source('../src/lib/components/shell/AppShell.svelte');
    const sidebar = source('../src/lib/components/shell/ConversationSidebar.svelte');
    const about = render(SettingsPanel).body;
    expect(shell).not.toContain('title-version');
    expect(sidebar).not.toContain('projectLabels');
    expect(about).toContain('Версия');
    expect(about).toContain('Сборка');
  });

  it('gates Project Knowledge without a switch, preview request, or memory claim', () => {
    const ru = render(KnowledgeToggle).body;
    const composer = source('../src/lib/components/chat/MessageComposer.svelte');
    expect(ru).toContain('Контекст проекта пока недоступен');
    expect(ru).toContain('Данные проекта не отправляются');
    expect(ru).toContain('Это не долговременная память');
    expect(ru).not.toContain('<button');
    expect(composer).not.toContain('prepareProjectKnowledge');
    expect(composer).not.toContain('createPendingKnowledgeTurn');
    expect(composer).not.toContain('KnowledgePreviewPanel');
    expect(composer).toContain('startLocalModelTurn(draft, $selectedConversationId, $includedFileIds)');
  });

  it('renders the exact English unavailable knowledge state', () => {
    setLocale('en');
    const html = render(KnowledgeToggle).body;
    expect(html).toContain('Project context is currently unavailable');
    expect(html).toContain('No project data is being sent');
    expect(html).toContain('This is not long-term memory');
  });

  it('removes normal-chat debug and unavailable placeholder buttons', () => {
    const composer = render(MessageComposer).body;
    const modelDrawer = source('../src/lib/components/model/ModelSetupDrawer.svelte');
    expect(composer).not.toContain('Tools (not yet available)');
    expect(composer).not.toContain('Инструменты (пока недоступны)');
    expect(composer).not.toContain('request-metrics');
    expect(modelDrawer).not.toContain('class="secondary-button" disabled');
  });

  it('keeps Diagnostics useful and removes demo, policy, verification, and no-op tab controls', () => {
    const html = render(Diagnostics).body;
    expect(html).toContain('Состояние системы');
    expect(html).toContain('Шлюз модели');
    expect(html).not.toContain('Запустить демо');
    expect(html).not.toContain('Отменить демо');
    expect(html).not.toContain('role="tablist"');
    expect(html).not.toContain('Решение политики');
  });

  it('gives every remaining production button in affected surfaces a real handler', () => {
    const files = [
      '../src/lib/components/shell/NavigationRail.svelte',
      '../src/lib/components/shell/ConversationSidebar.svelte',
      '../src/lib/components/shell/ChatHeader.svelte',
      '../src/lib/components/chat/MessageComposer.svelte',
      '../src/lib/components/chat/MessageList.svelte',
      '../src/lib/components/shell/SettingsPanel.svelte',
      '../src/lib/components/agent/Diagnostics.svelte',
      '../src/lib/components/model/ModelSetupDrawer.svelte',
      '../src/lib/components/model/ModelManagerSection.svelte'
    ];
    const buttons = files.flatMap(visibleButtonBlocks);
    expect(buttons.length).toBeGreaterThan(0);
    for (const button of buttons) {
      expect(button, button.slice(0, 120)).toContain('onclick=');
      expect(button).toMatch(/aria-label=|<span>|>\{\$t\(|>\s*\{\$t\(/);
    }
  });
});
````

### ПУТЬ: desktop/localcomet-desktop/tests/uiPreferences.test.ts (152 строк, 5016 байт)

````typescript
import { beforeEach, describe, expect, it } from 'vitest';
import {
  DEFAULT_UI_PREFERENCES,
  LEGACY_LANGUAGE_KEY,
  UI_PREFERENCES_KEY,
  loadUiPreferences,
  updateUiPreferences
} from '../src/lib/stores/uiPreferences';

function createMemoryStorage(initial: Record<string, string> = {}): Storage {
  const values = new Map(Object.entries(initial));
  return {
    get length() { return values.size; },
    clear: () => values.clear(),
    getItem: (key: string) => values.get(key) ?? null,
    key: (index: number) => [...values.keys()][index] ?? null,
    removeItem: (key: string) => { values.delete(key); },
    setItem: (key: string, value: string) => { values.set(key, value); }
  };
}

function installStorage(storage: Storage): void {
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: storage
  });
}

describe('UI preferences', () => {
  beforeEach(() => {
    installStorage(createMemoryStorage());
  });

  it('uses a versioned key and complete safe defaults', () => {
    expect(UI_PREFERENCES_KEY).toBe('localcomet.ui.preferences.v1');
    expect(loadUiPreferences()).toEqual(DEFAULT_UI_PREFERENCES);
    expect(Object.keys(loadUiPreferences())).toEqual(['theme', 'locale', 'diagnosticsPanel']);
  });

  it('loads only valid fields and ignores unknown fields', () => {
    localStorage.setItem(UI_PREFERENCES_KEY, JSON.stringify({
      theme: 'dark',
      locale: 'en',
      diagnosticsPanel: 'open',
      repositoryPath: 'C:\\private',
      futureField: true
    }));
    expect(loadUiPreferences()).toEqual({
      theme: 'dark',
      locale: 'en',
      diagnosticsPanel: 'open'
    });
  });

  it('defaults invalid and missing fields independently', () => {
    localStorage.setItem(UI_PREFERENCES_KEY, JSON.stringify({
      theme: 'sepia',
      locale: 'en',
      diagnosticsPanel: 'floating'
    }));
    expect(loadUiPreferences()).toEqual({
      theme: 'system',
      locale: 'en',
      diagnosticsPanel: 'closed'
    });
  });

  it('falls back safely for malformed or non-object records', () => {
    localStorage.setItem(UI_PREFERENCES_KEY, '{');
    expect(loadUiPreferences()).toEqual(DEFAULT_UI_PREFERENCES);
    localStorage.setItem(UI_PREFERENCES_KEY, JSON.stringify(['dark', 'en', 'open']));
    expect(loadUiPreferences()).toEqual(DEFAULT_UI_PREFERENCES);
  });

  it('reads the legacy language only when the v1 record is absent', () => {
    localStorage.setItem(LEGACY_LANGUAGE_KEY, 'en');
    expect(loadUiPreferences()).toEqual({
      theme: 'system',
      locale: 'en',
      diagnosticsPanel: 'closed'
    });
    expect(localStorage.getItem(UI_PREFERENCES_KEY)).toBeNull();
    expect(localStorage.getItem(LEGACY_LANGUAGE_KEY)).toBe('en');

    localStorage.setItem(UI_PREFERENCES_KEY, '{');
    expect(loadUiPreferences().locale).toBe('ru');
  });

  it('writes a complete bounded record while preserving valid current fields', () => {
    localStorage.setItem(UI_PREFERENCES_KEY, JSON.stringify({
      theme: 'dark',
      locale: 'en',
      diagnosticsPanel: 'closed'
    }));
    expect(updateUiPreferences({ diagnosticsPanel: 'open' })).toEqual({
      theme: 'dark',
      locale: 'en',
      diagnosticsPanel: 'open'
    });
    expect(JSON.parse(localStorage.getItem(UI_PREFERENCES_KEY) ?? '{}')).toEqual({
      theme: 'dark',
      locale: 'en',
      diagnosticsPanel: 'open'
    });
  });

  it('ignores invalid and unknown update fields', () => {
    localStorage.setItem(UI_PREFERENCES_KEY, JSON.stringify({
      theme: 'light',
      locale: 'ru',
      diagnosticsPanel: 'open'
    }));
    const unsafePatch = {
      theme: 'sepia',
      locale: 'fr',
      diagnosticsPanel: 'floating',
      prompt: 'do not persist'
    } as unknown as Parameters<typeof updateUiPreferences>[0];
    expect(updateUiPreferences(unsafePatch)).toEqual({
      theme: 'light',
      locale: 'ru',
      diagnosticsPanel: 'open'
    });
    expect(Object.keys(JSON.parse(localStorage.getItem(UI_PREFERENCES_KEY) ?? '{}'))).toEqual([
      'theme',
      'locale',
      'diagnosticsPanel'
    ]);
  });

  it('never writes or removes the legacy language key', () => {
    localStorage.setItem(LEGACY_LANGUAGE_KEY, 'en');
    updateUiPreferences({ theme: 'dark' });
    expect(localStorage.getItem(LEGACY_LANGUAGE_KEY)).toBe('en');
    expect(JSON.parse(localStorage.getItem(UI_PREFERENCES_KEY) ?? '{}').locale).toBe('en');
  });

  it('survives storage read and write failures', () => {
    installStorage({
      get length() { return 0; },
      clear: () => undefined,
      getItem: () => { throw new Error('blocked'); },
      key: () => null,
      removeItem: () => undefined,
      setItem: () => { throw new Error('blocked'); }
    });
    expect(() => loadUiPreferences()).not.toThrow();
    expect(loadUiPreferences()).toEqual(DEFAULT_UI_PREFERENCES);
    expect(() => updateUiPreferences({ theme: 'dark' })).not.toThrow();
    expect(updateUiPreferences({ theme: 'dark' }).theme).toBe('dark');
  });
});
````

### ПУТЬ: desktop/localcomet-desktop/tsconfig.json (14 строк, 328 байт)

````json
{
  "extends": "./.svelte-kit/tsconfig.json",
  "compilerOptions": {
    "allowJs": false,
    "checkJs": false,
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "skipLibCheck": true,
    "sourceMap": true,
    "strict": true
  }
}
````

### ПУТЬ: desktop/localcomet-desktop/vite.config.ts (17 строк, 322 байт)

````typescript
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  clearScreen: false,
  server: {
    host: '127.0.0.1',
    port: 1420,
    strictPort: true
  },
  preview: {
    host: '127.0.0.1',
    port: 1421,
    strictPort: true
  }
});
````

### ПУТЬ: desktop/localcomet-desktop/vitest.config.ts (11 строк, 249 байт)

````typescript
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [sveltekit()],
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts'],
    globals: true
  }
});
````

### ПУТЬ: docs/agent_operating_layer.md (103 строк, 3533 байт)

````markdown
# LocalComet Agent Operating Layer v1

Passive architecture foundation for agent-based development on LocalComet.

## Task intake

Every task must specify:
- **Baseline version** (current GREEN version before work)
- **Goal** (one sentence, no ambiguity)
- **Allowed files** (explicit paths or globs)
- **Forbidden files** (paths that must not change)
- **Risk level** (see classification below)

If any of these are missing, ask before proceeding.

## Risk classification

| Level | Criteria | Approval |
|---|---|---|
| **doc** | Docs, schemas, skills, config only. No Python edits. | Implicit |
| **config** | Changes to non-Python config files (JSON, YAML, TOML, env). No logic change. | Implicit |
| **safe_code** | Non-breaking Python change covered by existing tests. | Implicit after plan |
| **guarded** | Adds a new module without removing existing functionality. Changes runtime state. | Explicit confirmation |
| **dangerous** | Deletes files. Changes safety policy. Modifies tests to pass without fixing root cause. Changes disk I/O behavior. | Blocked unless explicit per-task override |

When risk level is unclear, default to **guarded**.

## Context pack

Before editing, load:
1. `AGENTS.md` — project operating contract
2. `OPENCODE_RULES.md` — tool-specific rules
3. Current GREEN baseline from `strict_project_stability` output
4. All files listed in "allowed_files" (read at least once)
5. Any file referenced by the task that exists

## Plan contract

Before touching files, produce a plan containing:
```text
task_id: <short unique label>
goal: <one sentence>
risk_level: <doc|config|safe_code|guarded|dangerous>
files_to_edit:
- <path> (reason)
files_to_create:
- <path> (reason)
pre_edit_backup: <path>
test_plan:
- <command 1>
- <command 2>
```

Present the plan. If risk is guarded or dangerous, wait for explicit approval.

## OpenCode implementation prompt

When handing work to an OpenCode agent:
```text
Read AGENTS.md and docs/agent_operating_layer.md.
Use the run_manifest schema at .localcomet/agent/run_manifest.schema.json.
Follow the stability-gate skill at .localcomet/skills/stability-gate/SKILL.md.
Green baseline: <version>
Task: <goal>
Allowed files: <list>
Forbidden files: <list>
Risk level: <level>
```

## Verification gates

After every edit, run in this exact order:

1. `python -m py_compile <every changed .py file>`
2. `python -m py_compile LocalComet_Control_Panel.py`
3. `python tools\localcomet_preflight_audit.py --include-tools`
4. `python -c "from modules.computer_use_core_ru import dispatch; r=dispatch('pc computer contracts'); print(r); assert r['ok']"`
5. `python -c "from modules.strict_project_stability_ru import dispatch; r=dispatch('проверь проект'); assert r['ok'] and r['summary']['hard_failures'] == 0 and r['summary']['warnings'] == 0"`

If any gate fails, stop. Revert or fix. Do not proceed until GREEN.

## Review report

After verification, produce a report with:
```text
task_id: <label>
files_changed:
- <path>
validation:
  py_compile: PASS
  preflight: PASS/FAIL
  contracts: PASS/FAIL
  strict_stability: <score>/<total>, hard_failures=<n>, warnings=<n>
final_status: GREEN|FAILED
risks:
- <any concern about this change>
```

## Accepted GREEN commit / rejected patch decision

- If final_status is GREEN and the change fulfills the goal, the patch is accepted.
- If final_status is GREEN but the change does NOT match the goal, reject and re-plan.
- If final_status is FAILED, reject. Revert all edits. Restore from backup. Re-plan.
````

### ПУТЬ: docs/desktop_architecture_v6841.md (437 строк, 17768 байт)

````markdown
# LocalComet Desktop Architecture v6.84.1

## 1. Purpose and Scope

v6.84.1 defines the contract-first foundation for a professional Windows desktop LocalComet application. It describes the intended desktop architecture and implements only the Python-side IPC protocol helpers in this release.

This release does not scaffold Tauri, Rust, SvelteKit, Node, npm, pnpm, Cargo, a sidecar process, a GUI, a localhost server, or the v6.85 autonomous loop.

## 2. Final Desktop Technology Stack

- Desktop shell: Tauri 2.
- Web runtime: one primary WebView using system WebView2 on Windows.
- Frontend: SvelteKit with TypeScript strict mode.
- Production frontend build: static adapter, no server-side rendering inside the packaged desktop application.
- Trusted native bridge: Rust.
- Core intelligence: existing Python LocalComet modules packaged as a sidecar.
- Production transport: framed JSON over dedicated stdin/stdout pipes.

The application must not embed Chromium, open an external browser window, or expose a production localhost HTTP/WebSocket API.

Open WebUI is only a visual-structure reference; LocalComet is not a source-code fork and must not copy Open WebUI source, branding, component names, styling files, logos, or proprietary assets.

## 3. Trust Boundaries

The frontend is not trusted for policy decisions, filesystem authorization, process execution, approval generation, secret storage, or autonomy-level selection.

Rust is trusted for process lifecycle, native window lifecycle, Tauri capabilities, outer IPC envelope validation, native dialogs, and future Windows child-process containment.

Python is trusted for semantic request validation, planning, policy decisions, action execution, run state, diagnostics, preflight, audit bundles, model orchestration, and redaction.

No layer may trust data merely because it came from another local process.

## 4. Process Topology

The target production topology is:

```text
Tauri window (SvelteKit static UI)
  -> Rust command bridge
    -> one child Python LocalComet sidecar
      -> existing LocalComet modules
```

The Svelte UI communicates only with narrow Rust commands. Rust owns the Python process handle and framed pipe transport. Python owns LocalComet semantics.

## 5. Frontend Responsibilities

SvelteKit owns transient interface state:

- open panels;
- draft composer text;
- selected conversation;
- visible filters;
- local UI affordances;
- optimistic rendering of pending events.

Svelte must not read arbitrary files, execute processes, read environment variables, manufacture approvals, change policy levels, or store sensitive content in browser localStorage.

## 6. Rust Bridge Responsibilities

Rust owns:

- Tauri window setup;
- Tauri command registration;
- native dialog mediation;
- Python sidecar startup and shutdown;
- framed stdin/stdout transport;
- outer-envelope validation;
- bounded outbound event queue;
- future Windows Job Object containment;
- production capability enforcement.

Rust does not make autonomy decisions, reinterpret prompts, or execute arbitrary shell text.

## 7. Python Sidecar Responsibilities

Python remains authoritative for:

- chat/model orchestration;
- planning;
- policy and approvals;
- safe action execution;
- immutable run state;
- diagnostics;
- preflight;
- audit bundle creation and verification;
- redaction and sanitized errors.

stdout must contain only framed IPC messages. stderr is reserved for bounded sanitized diagnostics.

## 8. IPC Framing

Protocol name: `localcomet.ipc`.

Protocol version: `1.0`.

Each frame is:

1. four-byte unsigned big-endian length;
2. exactly that many UTF-8 JSON bytes.

There are no delimiter-based frames. Maximum frame size is 4,194,304 bytes. Zero-length frames, malformed UTF-8, malformed JSON, duplicate keys, NaN, Infinity, oversized payloads, unknown envelope types, and unsupported protocol versions are rejected.

## 9. IPC Message Lifecycle

Rust sends `hello`. Python answers with a `hello` response payload selecting version `1.0`. Requests then flow from Rust to Python, and Python returns exactly one terminal response or error for each request.

Events may appear between request acceptance and terminal completion. Events after terminal completion are rejected or ignored deterministically by stream state.

## 10. Streaming and Backpressure

Streaming uses ordered `event` envelopes with `reply_to` set to the originating request ID. `chat.delta` batches text instead of sending one token per frame. Maximum delta text is 65,536 characters.

Future defaults:

- maximum queued events: 1,000;
- maximum queued text: 8 MB;
- delta coalescing window: 10-30 ms.

Rust pauses sidecar reads or cancels the request if the UI cannot keep up. No layer may use an unbounded event buffer.

## 11. Cancellation

Cancellation is a `cancel` envelope containing `target_request_id` and a bounded reason:

- `user_requested`;
- `window_closing`;
- `timeout`;
- `shutdown`.

Cancellation is idempotent, cannot approve actions, cannot expose process handles, and produces a terminal response or terminal error for the cancelled request.

## 12. Approval Flow

`approval.required` events contain only sanitized metadata: action ID, fingerprint, risk, summary, sanitized target, reversibility, and optional expiration.

`approval.submit` includes action ID, action fingerprint, decision `approve|deny`, and scope `SINGLE_ACTION`.

Frontend text such as "yes" is not approval. The UI cannot change action fingerprints or policy level. Approval cannot override permanent policy blocks.

## 13. File Attachment Flow

Normal IPC messages do not stream arbitrary file bytes.

Future flow:

1. Svelte requests a native file picker through a narrow Tauri command.
2. Rust validates the selection.
3. Rust creates an opaque attachment handle.
4. Svelte sees handle, sanitized filename, size, and media type.
5. Python accesses the file only through an explicitly authorized bridge flow.

Absolute paths are never exposed to Svelte.

## 14. Model Integration Flow

Python owns model configuration and orchestration. Rust forwards bounded requests and streams sanitized events. Svelte renders model state but does not hold authoritative credentials or endpoint configuration.

## 15. Autonomous-Agent Event Flow

Future autonomous events include plan updates, proposed actions, approval requests, policy decisions, budget changes, test results, rollback state, and kill-switch changes. v6.84.1 defines the IPC shape only and does not activate the v6.85 loop.

## 16. Process Startup

Rust starts the Python sidecar after window initialization and capability setup. The first sidecar message must be a framed hello response. Any informal stdout text is a protocol error.

## 17. Process Shutdown

Rust sends `goodbye` or cancellation during shutdown, closes stdin, drains bounded output, and terminates the child if it does not exit. Python should finish active cleanup without writing persistent state unless a later release explicitly owns that state.

## 18. Crash Handling

Rust detects sidecar exit, emits sanitized UI state, and prevents stale approvals. Python error messages must use bounded error codes and sanitized details. Tracebacks are never sent to the frontend.

## 19. Windows Process Containment

Windows Job Object containment is the target mechanism. It is not implemented in v6.84.1. Child-process tree containment belongs to a later release and must be verified before claiming support.

## 20. CSP and Tauri Capabilities

Future Tauri requirements:

- CSP `default-src 'self'`;
- no remote JavaScript;
- no eval;
- no wildcard `connect-src` in production;
- narrow capabilities per window;
- no shell plugin exposed to the frontend;
- no broad filesystem plugin;
- no unrestricted process plugin;
- signature validation for updater endpoints;
- no production debug console unless explicitly enabled;
- disable navigation outside bundled app;
- external URLs opened only through an allowlisted Rust command;
- sanitized drag-and-drop metadata.

## 21. Secret Handling

Secrets remain in Python or OS-native secure storage when later introduced. They are not stored in browser localStorage. Logs, IPC errors, and events must redact tokens, passwords, Authorization headers, private keys, full user paths, raw write content, and attachment paths.

## 22. Logging and Redaction

Rust and Python log only sanitized protocol metadata, bounded IDs, methods, counters, and safe status fields. Payload text is truncated and redacted. stdout from Python is never used for informal logs.

## 23. Data Ownership

Svelte owns transient UI state only.

Rust owns process handles, IPC channel state, window state, and update state. Rust does not own the conversation database.

Python owns conversations, model configuration, planner results, autonomy runs, approvals, tool results, diagnostics, and audit metadata.

## 24. State Persistence Ownership

Persistent LocalComet state remains Python-owned. Svelte may cache cosmetic preferences only if they do not contain sensitive data. Rust may persist window geometry and updater state.

## 25. Error Model

Errors use bounded codes such as `invalid_frame`, `invalid_json`, `invalid_envelope`, `unsupported_version`, `unsupported_method`, `request_cancelled`, `policy_blocked`, `approval_required`, `kill_switch_active`, and `internal_error`.

Error payloads contain code, sanitized message, retryable flag, and bounded details. They never include tracebacks, raw exception reprs, environment variables, full paths, source contents, or secret values.

## 26. Version Negotiation

The initial release supports only protocol `1.0`. Rust sends supported versions in hello. Python selects `1.0` or returns `unsupported_version`.

## 27. Compatibility Strategy

Future minor protocol additions must preserve existing fields and bounded vocabularies. New methods should be additive. Breaking changes require a new protocol version and explicit negotiation.

## 28. Threat Model

Threats include prompt injection, malicious attachments, compromised frontend state, overlarge frames, malformed JSON, duplicate keys, path disclosure, secret leakage, unauthorized approval, sidecar crash, event queue exhaustion, and subprocess containment gaps.

Mitigations include strict framing, schema and Python validation, redaction, opaque handles, exact approval fingerprints, policy recomputation, capability-limited Rust commands, and no exposed production HTTP API.

## 29. Development Mode

Later development workflows may use a Vite development server. That must not alter production trust boundaries. Production loads bundled static assets only.

## 30. Production Mode

Production uses a signed Tauri application, bundled static Svelte assets, one Python sidecar, length-prefixed JSON pipes, no exposed production localhost API, no localhost server, and no external browser window.

## 31. Packaging Plan

Later releases package:

- Tauri binary;
- static Svelte assets;
- Python runtime or validated environment strategy;
- LocalComet Python modules;
- schema files;
- signed updater metadata.

## 32. Installer Plan

The installer should create per-user application files, avoid requiring administrator rights by default, register uninstaller metadata, and not install services or scheduled tasks unless a later release explicitly designs them.

## 33. Signed Updater Plan

Updater metadata and payloads must be signature-verified. Unsigned updater endpoints are not allowed. Rollback and staged rollout policy belong to a later release.

## 34. UI Information Architecture

Navigation rail width: 52-60 px. Items: new chat, search, conversations, projects, autonomous runs, models, tools, diagnostics, settings.

Expandable sidebar width: 240-320 px. Contains conversation history, projects, pinned sessions, filters, and local search.

Center workspace contains header, model selector, mode selector (`Chat`, `Plan`, `Agent`), virtualized message list, Markdown, code blocks, tool-call blocks, attachments, approval cards, and floating composer.

Agent inspector width: 320-420 px. Contains agent status, current plan, current action, risk level, policy decision, approval request, budgets, changed files, diff, test results, preflight, rollback state, and kill-switch status. It is collapsible.

Below about 1,200 px, the inspector hides behind a toggle. Below about 900 px, the history sidebar collapses. The desktop window minimum size target is 900 x 640.

## 35. Component Hierarchy

Future original LocalComet components:

- `AppShell`;
- `NavigationRail`;
- `ConversationSidebar`;
- `WorkspaceHeader`;
- `ModelSelector`;
- `ModeSelector`;
- `MessageTimeline`;
- `MarkdownMessage`;
- `CodeBlock`;
- `ToolCallBlock`;
- `ApprovalCard`;
- `FloatingComposer`;
- `AgentInspector`;
- `BudgetPanel`;
- `DiffPanel`;
- `DiagnosticsPanel`.

These names are LocalComet-owned and are not copied from any external project.

## 36. Accessibility Requirements

All controls require keyboard operation, visible focus rings, semantic labels, high-contrast status colors, screen-reader names for icon buttons, reduced-motion support, and predictable tab order. Approval actions must be confirmable without relying on color alone.

## 37. Performance Targets

Targets:

- first window paint under 1.5 seconds after native startup on a warm machine;
- message list virtualization for long conversations;
- IPC frame validation under 5 ms for ordinary frames;
- no unbounded queues;
- bounded Markdown/code rendering work;
- responsive composer input under streaming load.

## 38. Migration Stages

1. v6.84.1: architecture, schema, Python IPC helpers.
2. v6.84.2: visual Tauri/Svelte shell scaffold.
3. Later: Rust bridge process lifecycle and framing.
4. Later: Python sidecar packaging.
5. Later: model/chat IPC integration.
6. Later: agent inspector and approval flow.
7. Later: signed installer/updater.

The existing Tkinter control panel remains a temporary fallback during this migration and is not modified by the desktop architecture releases.

## 39. Acceptance Criteria

This architecture is acceptable when it preserves LocalComet's current Python authority, avoids production localhost APIs, keeps the frontend untrusted for security decisions, uses bounded framed JSON IPC, documents containment honestly, and reserves future document workflows without implementing them.

## 40. Deferred Capabilities

Deferred capabilities include visual UI implementation, Tauri project scaffolding, SvelteKit build setup, Rust IPC bridge implementation, Python sidecar process management, Windows Job Object containment, signed updater, attachment picker, v6.85 autonomous loop, and document workflow execution.

## 41. Structured Document Workflows

The desktop architecture reserves a future bounded document-workflow subsystem. It is not implemented in v6.84.1.

Future pipeline:

```text
source ingestion
-> content extraction
-> schema selection
-> typed field extraction
-> missing-field detection
-> human confirmation
-> deterministic template rendering
-> artifact verification
-> desktop preview/export
```

Rules:

- LLMs must not render final business documents directly.
- LLMs may classify intent, extract candidate fields, and identify missing data.
- Deterministic code validates structured fields.
- A bounded renderer creates the artifact.
- Typst may be evaluated later as one renderer option.
- Rendering subprocesses must use the v6.84 safe executor.
- No shell execution is permitted.
- Fixed executable and template allowlists are required.
- Timeout and output limits are required.
- Each run uses a unique artifact directory.
- Writes are atomic and verified with SHA-256.
- Sensitive documents remain local by default.
- External model upload requires explicit one-time approval.
- Attachment filenames are never trusted as paths.
- Email and other connectors remain disabled by default.
- Frontend receives opaque attachment and artifact handles, not absolute paths.
- Generated artifacts appear as dedicated UI cards and in the Agent Inspector.
- Missing required fields appear as structured confirmation forms.
- No document, email, or attachment implementation is added in v6.84.1.

Reserved future IPC events:

- `document.ingestion.started`;
- `document.ingestion.completed`;
- `document.fields.extracted`;
- `document.fields.required`;
- `document.confirmation.required`;
- `document.rendering.started`;
- `document.artifact.created`;
- `document.verification.completed`;
- `document.failed`.

Reserved future UI components:

- `DocumentWorkflowCard`;
- `MissingFieldsForm`;
- `ArtifactCard`;
- `ArtifactPreview`;
- `ArtifactVerificationBadge`.

## 42. Visual Tokens

LocalComet visual tokens must be original.

light theme:

- background: `#f7f8fb`;
- surface: `#ffffff`;
- elevated surface: `#f1f4f8`;
- text: `#15202b`;
- muted text: `#637083`;
- border: `#d7dde6`.

dark theme:

- background: `#101316`;
- surface: `#171b20`;
- elevated surface: `#20262d`;
- text: `#eef2f7`;
- muted text: `#a2adbb`;
- border: `#343c46`.

Spacing: 4 px base scale with 8, 12, 16, 24, and 32 px layout steps.

Radii: 4 px for controls, 6 px for panels, 8 px maximum for repeated cards.

Typography: system UI stack, 13-14 px dense controls, 15-16 px reading text, tabular numerals for counters.

Semantic statuses:

- success: green;
- warning: amber;
- danger: red;
- paused: blue;
- neutral: gray.

Risk colors:

- LOW: muted green;
- MEDIUM: amber;
- HIGH: orange-red;
- CRITICAL: red with high-contrast treatment.

Approval colors separate approve, deny, pending, and expired states. Focus rings use a two-layer high-contrast outline. Code surfaces use a monospace font, line wrapping, copy affordance, and no negative letter spacing.
````

### ПУТЬ: docs/engineering/adr-001-architecture-current-state.md (192 строк, 9573 байт)

````markdown
# ADR-001: LocalComet Architecture — Current State Assessment

**Status:** Accepted
**Date:** 2026-07-25
**Author:** OpenCode architectural analysis

## Context

LocalComet / LocalAgent is a local Python agent with a console entry point (`next/app_v5.py`), a Tkinter control panel, and a Tauri/Svelte desktop shell. The codebase has grown organically over multiple build weeks. This ADR records the results of a full architectural audit: dependency analysis, layering violations, god-modules, and pattern compliance.

### Codebase Metrics

| Layer | Files | Lines | Role |
|-------|-------|-------|------|
| `core/` | 7 | 1,087 | Orchestration: router, planner, executor, LLM, state |
| `agents/` | 18 | 1,573 | Thin adapters with `handle(action, data)` |
| `modules/` | 140 | 63,051 | Implementation logic (browser, relay, desktop, knowledge, etc.) |
| `next/` | 5 | 1,862 | v5 console app, goal manager, task planner, queue, observer |
| `desktop/` | — | — | Tauri + Svelte desktop shell (separate runtime) |
| `tools/` | 47 | — | Test scripts, audits, launchers |
| `scripts/` | 2 | — | Utility scripts |
| Root | 3 | ~138 | `app.py` (legacy), `agent.py` (orphan), `config.py` |

## Intended Layering

```
next/app_v5.py  (entry point / CLI)
       │
       ▼
    core/       (orchestration: route → plan → execute)
       │
       ▼
   agents/      (thin adapters: handle(action, data))
       │
       ▼
   modules/     (implementation logic)
       │
       ▼
   config.py    (configuration constants)
```

Dependencies should flow **downward only**. Each layer should depend only on the layer directly below it.

## Findings

### 1. Circular Dependency: core ↔ modules (CRITICAL)

The intended layering is violated bidirectionally:

**core → modules** (4 files):
- `core/planner.py` → `modules.browser_direct`, `modules.natural_command_intents`
- `core/router.py` → `modules.natural_command_intents`
- `core/state.py` → `modules.project_paths`
- `core/executor.py` → `modules.browser_profile_ignore` (conditional)

**modules → core** (76 import sites across ~45 files):
- 40+ files import `core.state` (get_value, set_value)
- 6 files import `core.llm` (ask_llm)
- 3 files import `core.router` + `core.planner` + `core.executor` (full orchestration loop):
  - `modules/stability_test.py` (20 import sites)
  - `modules/automation_center.py` (3 import sites)
  - `modules/regression_commands.py` (3 import sites)

This creates a **circular dependency** between the orchestration layer and the implementation layer. The three modules that re-import the full route→plan→execute pipeline are effectively embedding a second orchestration loop inside `modules/`, bypassing the intended architecture.

### 2. God-Object: next/app_v5.py (HIGH)

`next/app_v5.py` is **2,039 lines**. Approximately 1,600 lines are a command-dispatch chain spread across 12 `_run_direct_*` functions:

- `_run_direct_automation_command()`
- `_run_direct_gpt_browser_command()`
- `_run_direct_chatgpt_relay_command()`
- `_run_direct_gpt_command()`
- `_run_direct_self_edit_command()`
- `_run_direct_maintenance_command()`
- `_run_direct_history_command()`
- `_run_direct_diagnostics_command()`
- `_run_direct_voice_command()`
- `_run_direct_notepad_command()`
- `_run_direct_workspace_command()`
- `_run_direct_browser_action_command()`

Additionally, a `SHORTCUTS` dict with 120+ entries duplicates routing logic that belongs in `core/router`. Every new command requires editing this file. There is no separation between CLI parsing and business logic.

### 3. God-Modules in modules/ (HIGH)

Top 10 largest files in `modules/`:

| File | Lines | Concern |
|------|-------|---------|
| `premium_task_panel_ru.py` | 2,957 | UI panel + LLM calls + state |
| `desktop_control_plane_ru.py` | 2,208 | Desktop control + IPC + state |
| `computer_use_contract_tests_ru.py` | 1,818 | Tests mixed with implementation |
| `local_model_gateway_ru.py` | 1,811 | Model routing + provider abstraction |
| `stability_test.py` | 1,664 | Test harness embedding full orchestration |
| `knowledge_change_review_ru.py` | 1,488 | Review workflow + UI + state |
| `localcomet_functional_test_center_ru.py` | 1,344 | Test center + execution |
| `knowledge_review_ui_projection_ru.py` | 1,291 | UI projection + review logic |
| `computer_use_full_control_mission_ru.py` | 1,117 | Mission control + action planning |
| `computer_use_multistep_loop_ru.py` | 979 | Multi-step execution loop |

Files exceeding ~500 lines likely violate the Single Responsibility Principle. The top 5 files alone account for 10,458 lines (16.6% of all module code).

### 4. Agents Importing core.state Directly (MEDIUM)

5 of 18 agents bypass the adapter pattern by importing `core.state` directly:

- `agents/browser_agent.py`
- `agents/code_agent.py`
- `agents/project_agent.py`
- `agents/system_agent.py`
- `agents/windows_agent.py`

All 5 import `get_value`/`set_value` for persisting last-action metadata. This couples the adapter layer to the orchestration layer's state management.

### 5. Orphan and Legacy Code (MEDIUM)

- **`agent.py`** (96 lines): Fully disconnected prototype. Hardcodes its own LLM URL and model (`google/gemma-4-e4b` vs `config.py`'s `qwen3-14b`). Contains a **command injection risk** in `search_web()` via unsanitized `subprocess.Popen(..., shell=True)`.
- **`app.py`** (37 lines): Legacy v3 entry point. Duplicates the route→plan→execute pipeline from `app_v5.py` without shortcuts, state, or logging.

### 6. Inconsistent Error Handling (LOW)

- `next/goal_manager.py` and `next/task_planner.py` handle LLM offline errors via `is_llm_offline_error()` / `format_llm_offline_message()`.
- `next/observer.py` does not handle LLM offline errors at all.

### 7. Dead Data (LOW)

- `next/goal_manager.py` extracts `success_criteria` from LLM analysis, but `app_v5.py` never consumes it downstream.

## Pattern Compliance

| Pattern | Status | Notes |
|---------|--------|-------|
| Agent adapter (`handle(action, data)`) | **18/18 compliant** | All agents follow the pattern |
| Route → Plan → Execute pipeline | **Compliant in core/** | `loop.py` chains correctly |
| Thin agents delegating to modules | **13/18 compliant** | 5 agents also import `core.state` |
| One-way dependency flow | **Violated** | Circular core ↔ modules |
| Single Responsibility | **Violated** | 10+ god-modules, 1 god-object |
| Configuration centralization | **Partially violated** | `agent.py` hardcodes config |
| No agents importing agents | **Compliant** | 0 cross-agent imports |

## Dependency Graph Summary

```
next/app_v5.py ──→ core/{router,planner,executor,state}
       │                    │
       │                    ├──→ agents/* (18 agents, via executor)
       │                    │         │
       │                    │         ├──→ modules/* (implementation)
       │                    │         │         │
       │                    │         │         └──→ core.state  ← CIRCULAR
       │                    │         │         └──→ core.llm    ← CIRCULAR
       │                    │         │         └──→ core.router ← CIRCULAR (3 files)
       │                    │         │
       │                    │         └──→ core.state (5 agents) ← VIOLATION
       │                    │
       │                    └──→ modules/* (4 core files) ← VIOLATION
       │
       └──→ modules/{history_log,browser_direct,voice_control}
```

## Recommendations

### Priority 1: Break the core ↔ modules cycle
- Extract `core.state` into a standalone `state/` package or a shared `common/` layer that both `core/` and `modules/` can import without circularity.
- Move `modules.project_paths` and `modules.natural_command_intents` into `core/` or a shared layer, since `core/` depends on them.
- Remove `core.router`/`core.planner`/`core.executor` imports from `modules/stability_test.py`, `modules/automation_center.py`, and `modules/regression_commands.py`. These should receive orchestration callbacks via injection rather than importing the orchestrator.

### Priority 2: Decompose app_v5.py
- Replace the 12 `_run_direct_*` functions with a command registry (dict or decorator-based) in `core/router` or a new `core/commands.py`.
- Move the `SHORTCUTS` dict into `core/router`.
- Separate CLI parsing (REPL loop) from command dispatch.

### Priority 3: Split god-modules
- `premium_task_panel_ru.py` (2,957 lines): separate UI rendering from LLM logic and state management.
- `desktop_control_plane_ru.py` (2,208 lines): separate IPC contract handling from control logic.
- `stability_test.py` (1,664 lines): move to `tools/` or `tests/` and inject orchestration dependencies.

### Priority 4: Clean up orphans
- Remove or refactor `agent.py` (security risk, dead code).
- Mark `app.py` as deprecated or remove it.

### Priority 5: Standardize state access in agents
- Provide a `modules/state_store.py` facade so agents never import `core.state` directly.

## Consequences

- The circular dependency makes it impossible to test `core/` or `modules/` in isolation.
- The god-object `app_v5.py` is the single highest-churn file and a merge-conflict hotspot.
- God-modules increase cognitive load and make targeted edits risky.
- The agent adapter pattern is well-followed and should be preserved.
- The route→plan→execute pipeline in `core/` is clean and should remain the canonical orchestration path.
````

### ПУТЬ: docs/engineering/best-of-two-final-report.md (270 строк, 16489 байт)

````markdown
# Best-of-Two Integration: Final Report

**Branch:** `integration/best-of-two-local-agent`
**Base:** `continue/after-build-week-2026` @ `767a7e9`
**Date:** 2026-07-25
**Product:** LocalComet 6.84.6 (Svelte 5 + Tauri 2 + Rust + Python sidecar)
**Status:** CORE SECURITY COMPLETE; **Windows installer BUILT** (U-002 partial: built, not installed); `npm ci` blocked offline (U-001)

---

## 1. Executive Summary

**Что было.** Канонический LocalComet (v6.84.6) и параллельная реализация Local Agent
Desktop (donor, WP-1.45.4). Задача — перенести полезные, совместимые и доказуемые
улучшения donor в LocalComet, не наследуя его дефекты и не создавая дублирующих authority.

**Что сделано (две фазы).**

- *Фаза 1 (Best-of-Two, WP-A…G):* migration matrix, trust-chain (`.gitattributes` +
  EOL/BOM gate), реестры инвариантов и non-authorities, command-parity gate, модули
  `approval.rs` и `workspace.rs`, аудит-архив.
- *Фаза 2 (Studio Engineering Prompt, Tasks A–J):* подключение approval к продуктовому
  пути (Tauri-команды + Svelte bridge), evidence provenance, UI fake-state аудит,
  honest real-sidecar тесты, workspace IPC-схема + WorkspacePolicy, preflight, build.sh,
  bundle-проверка, smoke + harness.
- *Сборка:* **Windows-бандл собран** — `npx tauri build --bundles nsis` → exit 0
  (`LocalComet.exe` + `LocalComet_6.84.6_x64-setup.exe`); `cargo clippy -D warnings` и
  `cargo fmt --check` зелёные; Svelte собирается offline (vendored `node_modules`).

**Что осталось.** Установка/запуск инсталлятора и smoke установленного приложения
(требует GUI-сессии), `npm ci` (блокирован offline registry — U-001), полный GUI-флоу
approval (ждёт появления fs-tool исполнения в sidecar), CI workflow (отсутствует в
чекауте). См. `docs/unverified-ledger.md`.

**Главный итог:** security-ядро (approval, evidence, UI-integrity, real-sidecar honesty)
реализовано и **доказано инъекциями**. Критические дефекты donor не унаследованы.

---

## 2. Baseline

- LocalComet canonical: v6.84.6, Svelte 5 + Tauri 2 + Rust + Python monorepo
- Donor: Local Agent Desktop WP-1.45.4 (React 18 + Zustand, отдельный Python sidecar)
- Donor-архивы в среде: `lad-wp1454.tar.gz` + WP-брифы (в `audit/donor-briefs/`);
  2 материала отсутствуют (см. `audit/evidence-ledger.md`, DONOR-001)

### LocalComet уже реализует или превосходит donor

| Область | LocalComet | Donor |
|---|---|---|
| Windows Job Object (KILL_ON_JOB_CLOSE, ACTIVE_PROCESS=1) | Implemented | Not implemented |
| Process supervisor + active health probe | Implemented | Partially |
| Bounded stderr reader (4096 ring) | Implemented | Not implemented |
| IPC framing (4 MiB max, length-prefix) | Implemented | Partially |
| Artifact trust (SHA-256, GGUF, catalog guard, reparse rejection) | Implemented | Partially |
| Bounded pipe writes с таймаутом | Implemented | Not implemented |
| Sanitized sidecar env (-I, -B, PYTHONNOUSERSITE) | Implemented | Partially |
| Python discovery (фильтр WindowsApps stubs) | Implemented | Not implemented |
| Control plane bridge (request registry + timeouts) | Implemented | Partially |
| Model request lifecycle с watchdogs | Implemented | Not present |
| Correlated IPC (reply_to, type routing, sequence) | Implemented | Broken (dual transport) |
| TOCTOU (handles открыты при запуске) | Implemented | Not implemented |

---

## 3. Таблица задач A–J (Studio Engineering Prompt)

| Задача | Статус | Результат (верифицировано) |
|---|---|---|
| **A. Approval wiring** | ✅ DONE | `tool_risk_levels.toml` + gate (injection-proven); `approval_commands.rs` (`request_approval`/`execute_approved`/`set_workspace`) + `ApprovalState` + Svelte `approval.ts` → parity **42/42**; A.5 TTL sweep; A.6 grant expiry; A.7 session fix + `wrong_session` test |
| **B. Workspace IPC** | 🟡 PARTIAL | B.1 схема `workspace.set` в IPC-контракте; B.2 `modules/workspace_policy.py` (self-test OK); **B.3 = N/A** (sidecar не исполняет fs-tools) |
| **C. UI audit** | ✅ DONE | `Math.random`=0; 8 таймеров = polling/watchdog (OK); `check_ui_fake_state.py` (injection-proven); INV-UI-001 verified |
| **D. Real-sidecar tests** | ✅ DONE | `real_sidecar_env()` (panic при `REQUIRE`); `check_real_sidecar_tests.py`; D.3 — нет CI файла (DEFERRED) |
| **E. Evidence provenance** | ✅ DONE | `refresh_evidence.py` + `check_evidence_provenance.py` (injection → STALE, exit 1) |
| **F. Preflight** | ✅ DONE | `doctor.py`: npm registry UNREACHABLE (U-001), NSIS missing, WebView2 OK, Rust/Node/Python OK |
| **G. Build** | ✅ DONE | `build.sh` (**.ps1 НЕ создан — AGENTS.md запрещает**) |
| **H. Tauri bundle** | ✅ DONE | конфиг production-grade; icon.ico, NSIS hooks, Python DLLs, approved-artifacts catalog present |
| **I/J. Smoke + harness** | ✅ DONE | `localcomet_test_harness.py` + `scripts/smoke_test.py`: **8 passed, 0 failed** (реальный sidecar); шаги 9–12 = RUST-COVERED/N-A |

---

## 4. Ключевые находки

### 4.1. Desktop sidecar ≠ tool-executor (главная архитектурная находка)

Desktop sidecar (`desktop_sidecar_runtime_ru.py`) — это **model-gateway / knowledge /
session менеджер**. Он **не исполняет файловые инструменты**: `files.*` методы явно
отклоняются как `unsupported_method` (подтверждено smoke step 6 [прогон] и
`tools/test_v6843_sidecar_supervisor.py:441-456`, где `files.read` в списке
`blocked_methods`).

**Следствие:** Studio prompt предполагал tool-executing sidecar (как у donor). Это не
так для LocalComet. Поэтому:
- Approval/workspace enforcement живёт в **Rust** (`approval.rs`, `workspace.rs`,
  `approval_commands.rs`), а не в sidecar.
- Я **не фабриковал** фейковый `tool.call`/`files.patch` путь в sidecar (это нарушило бы
  запрет на «заглушки, выдаваемые за backend»). Шаги smoke 9–12 помечены RUST-COVERED/N-A.
- Workspace IPC round-trip в sidecar (B.3) = **N/A**: нечего охранять (нет fs-операций).

### 4.2. Нет unified AppState

LocalComet управляет отдельными managed states (`DesktopSidecarSupervisor`,
`ControlPlaneBridge`, `ArtifactTrustService`, и т.д.), а не единым `AppState`. Код
Studio prompt (с `state.approval_registry`, `state.control_plane`) адаптирован под
реальную архитектуру: создан `ApprovalState` (registry + workspace), управляемый через
`app.manage(...)`.

### 4.3. Критические дефекты donor НЕ унаследованы

| Дефект donor (WP-1.45.4) | LocalComet |
|---|---|
| Approval bypass (Python — второй consumer) | Rust-only atomic `execute_approved`, нет bypass |
| Workspace только в Rust-state | Rust validates + invalidates tokens; WorkspacePolicy primitive |
| Readiness принимает любой кадр | Требуется correlated health response (`desk-health-{seq}`) |
| Stderr не дренируется | Bounded stderr reader (4096 ring) |
| Два расходящихся IPC-транспорта | Единый `ipc.rs` |
| Unbounded event queue | `MAX_EVENTS_PER_REQUEST` + `MAX_EVENT_TEXT_PER_REQUEST` |

---

## 5. Test Results [прогон]

```
cargo test (2 run)          147 passed, 0 failed, 6 ignored   (approval: 15 tests)
cargo clippy -D warnings    OK (0 warnings; точечные #[allow(dead_code)] с обоснованием)
cargo fmt --check           OK
trust-chain gate            15 files pass byte invariants
cmd-parity gate             42 commands registered and invoked (parity holds)
tool-risk gate              5 tool functions classified (3 mutating, all require approval)
ui-fake-state gate          75 frontend files, 0 violations (Math.random=0)
evidence provenance         4 evidence files fresh and intact
smoke (real sidecar)        8 passed, 0 failed
workspace_policy            self-test OK
npm run build (offline)     OK (Svelte adapter-static, vendored node_modules)
tauri build --bundles nsis  OK (LocalComet.exe + LocalComet_6.84.6_x64-setup.exe)
```

### Injection-таблица (гейты доказаны падением)

| Gate | Что сломали | Что упало | Что защищает |
|---|---|---|---|
| tool_risk_registry | добавлен mutating `truncate_file` без записи | `UNCLASSIFIED_TOOL`, exit 1 | полнота классификации реальных fs-операций |
| ui_fake_state | `Math.random()` + `setTimeout(…,2000)` near state | 2 VIOLATION, exit 1 | UI не генерирует fake state |
| evidence_provenance | изменён `config.py` без refresh | `STALE`, exit 1 | evidence привязан к исходникам |
| real_sidecar_tests | `REQUIRE=1` без окружения | panic, 3 failed | нет silent-skip тестов |
| approval (cargo) | wrong tool/digest/workspace/session, replay, expired | соответствующий `ApprovalError` | atomic scoped authorization |

---

## 6. Invariants → active

Переведены в `active` с реальными `implementation`/`test_ids`/`verification_method`:
- **INV-APPROVAL-001** (guarded tool via atomic Rust authorization)
- **INV-APPROVAL-002** (one-time, scoped, CSPRNG token)
- **INV-EVIDENCE-001** (evidence bound to execution inputs)
- **INV-UI-001** (verified: `check_ui_fake_state.py`)

Остаётся `planned`: **INV-WORKSPACE-001** (IPC round-trip в sidecar — N/A до появления
fs-tool path; Rust workspace authority реализован).

---

## 7. Known Issues

| ID | Проблема | Статус |
|---|---|---|
| U-001 | npm registry UNREACHABLE (offline) — блокирует `npm ci`, не `npm run build` | BLOCKED (infra, не продукт) |
| U-002 | packaged installer | **PARTIAL — собран** (`tauri build` exit 0), не установлен/запущен |
| U-003 | 6 ignored real-sidecar тестов (требуют окружения) | DEFERRED (honest skip после Task D) |
| B-003 | workspace IPC в sidecar | N/A (нет fs-tools) |
| D-003 | CI workflow отсутствует в чекауте | DEFERRED |
| H-001 | doctor.py эвристики (C-linker, NSIS) vs реальная сборка | RESOLVED (cargo/tauri build — authority; NSIS cached by Tauri) |
| H-002 | app.health ≠ advertised capability | RESOLVED (правка теста; smoke 8/8) |
| DONOR-001 | 2 donor-материала отсутствуют | ЗАЯВЛЕНО |
| APPROVAL-UI-001 | approval GUI-флоу | PARTIAL (Rust boundary реален; GUI ждёт fs-tools) |

Полный реестр: `docs/unverified-ledger.md`.

---

## 8. Changed / New Files

**Фаза 1 (Best-of-Two):**
```
.gitattributes                                  (hardened)
config.py, approved-artifacts.v1.json           (CRLF→LF fix)
src-tauri/Cargo.toml                            (+getrandom, +subtle)
src-tauri/src/approval.rs, workspace.rs         (NEW)
src-tauri/src/lib.rs                            (+mod approval, +mod workspace)
docs/engineering/best-of-two-migration-matrix.md (NEW)
security/invariants/{invariants,non_authorities}.toml (NEW)
scripts/check_command_parity.py                 (NEW)
tests/test_trust_chain_invariants.py            (NEW)
```

**Фаза 2 (Studio Prompt):**
```
security/invariants/tool_risk_levels.toml        (NEW)
scripts/check_tool_risk_registry.py              (NEW, injection-proven)
scripts/check_ui_fake_state.py                   (NEW, injection-proven)
scripts/refresh_evidence.py                      (NEW)
scripts/check_evidence_provenance.py             (NEW, injection-proven)
scripts/check_real_sidecar_tests.py              (NEW)
scripts/doctor.py                                (NEW)
scripts/build.sh                                 (NEW; .ps1 не создан — AGENTS.md)
scripts/smoke_test.py                            (NEW, 8/8 green)
localcomet_test_harness.py                       (NEW)
modules/workspace_policy.py                      (NEW, self-test OK)
src-tauri/src/approval_commands.rs               (NEW)
src-tauri/src/approval.rs                        (TTL sweep, grant expiry, session fix, +4 tests)
src-tauri/src/supervisor.rs                      (real_sidecar_env honest skip)
src-tauri/src/lib.rs                             (+approval_commands, +ApprovalState, +3 handlers)
src/lib/bridge/approval.ts                       (NEW)
desktop/contracts/localcomet_ipc_v1.schema.json  (+workspace.set messages)
security/invariants/invariants.toml              (APPROVAL/EVIDENCE/UI → active)
docs/unverified-ledger.md                        (NEW)
```

---

## 9. Audit Archive Anchor

Аудит-архив (срез проекта для архитектора):
```
artifacts/audit/localcomet-audit-2026-07-25.tar.gz
  SHA-256: 5001057f6f246494a577926aa4191704abe06db3e05c45ee49571cdd5a35119b
  Size:    14 722 705 bytes (569 files)
  Parts:   .part1 2c37fc8b…  .part2 4c0c573b…  .part3 b438806c… (склейка верифицирована)
Текстовый аудит:
audit/LocalComet-AUDIT-2026-07-25.txt
  SHA-256: 04580f386cef8cbde77fb8b34d9ec4522b838f1d499fb7e6ce0784e069f5d71d
```

Примечание: указанный tar-архив — срез на конец фазы Best-of-Two. Работа фазы Studio
Prompt задокументирована в этом отчёте, в `docs/unverified-ledger.md` и в изменённых
файлах; актуальный tree_digest исходников фиксируется в `artifacts/evidence/*.txt`
через `scripts/refresh_evidence.py` (финальный tree_digest: `d5c4c42ce0d01b65…`,
282 файла).

### Windows build artifacts [прогон]

Собраны через `npx tauri build --bundles nsis` (exit 0):
```
src-tauri/target/release/LocalComet.exe
  size:   14 547 968 bytes (13.87 MB)
  sha256: 2bfdd0c78ba619c128398157fbeb7190deb4ff0c68eb92368ebc59c5ca52ad78

src-tauri/target/release/bundle/nsis/LocalComet_6.84.6_x64-setup.exe
  size:   13 963 772 bytes (13.32 MB)
  sha256: 7fc82beb3ff74a3ae5ad55b8b365dbd00acd92d81a007f74c1fb0c5dcbfa488f
```
Инсталлятор собран, но не устанавливался/не запускался (требует GUI-сессии) — см. U-002.

---

## 10. Classification

LocalComet desktop корректно классифицировать как **функциональный локальный desktop-
ассистент с production-grade containment процессов, artifact trust, доказанным
Rust approval/evidence/UI-integrity ядром и собираемым Windows-инсталлятором**.

Основание для additions к классификации (подтверждено доказательствами):
- end-to-end Rust approval authorization (atomic, scoped, one-time) — INV-APPROVAL-001/002 active;
- evidence provenance с source binding — INV-EVIDENCE-001 active;
- UI не генерирует fake backend state — INV-UI-001 verified;
- Windows-бандл собирается (`tauri build --bundles nsis` exit 0, хеши зафиксированы) — U-002 partial.

НЕ подтверждено (не менять классификацию в эту сторону): установка/запуск инсталлятора
и smoke установленного приложения (требует GUI-сессии), полный GUI approval-флоу
(ждёт fs-tool исполнения в sidecar), `npm ci` (блокирован offline registry — U-001).
````

### ПУТЬ: docs/engineering/best-of-two-migration-matrix.md (101 строк, 6483 байт)

````markdown
# Best-of-Two Migration Matrix

Donor: Local Agent Desktop (WP-1.45.4, React/Tauri/Python sidecar)
Target: LocalComet canonical (6.84.6+, Svelte/Tauri/Python monorepo)
Date: 2026-07-25
Branch: integration/best-of-two-local-agent

## Summary

LocalComet desktop already implements or exceeds many donor improvements:
- Windows Job Object with KILL_ON_JOB_CLOSE + ACTIVE_PROCESS_LIMIT=1
- Process supervisor with active health probe and readiness correlation
- Bounded stderr reader (4096 ring buffer)
- IPC framing with 4MB max frame, length-prefix
- Artifact trust with SHA-256, GGUF magic, catalog guard, reparse rejection
- Control plane bridge with request registry, timeouts, model lifecycle
- Bounded pipe writes with timeout and backpressure handling
- Sanitized sidecar environment (PYTHONNOUSERSITE, -I, -B)
- Python discovery filtering WindowsApps Store stubs

## Migration Matrix

| Donor improvement | Donor file | LocalComet analogue | Decision | Target file | Required adaptation | Tests | Status |
|---|---|---|---|---|---|---|---|
| Windows Job Object | windows_job.rs | src-tauri/src/windows_job.rs | ALREADY_PRESENT | — | — | 3 unit tests | DONE |
| Process supervisor | supervisor.rs | src-tauri/src/supervisor.rs | ALREADY_PRESENT | — | — | 6 unit tests | DONE |
| Active health probe | supervisor.rs | supervisor.rs:360-371 | ALREADY_PRESENT | — | — | lifecycle test | DONE |
| Bounded stderr reader | supervisor.rs | supervisor.rs:548-572 | ALREADY_PRESENT | — | — | — | DONE |
| IPC framing + max size | ipc.rs | src-tauri/src/ipc.rs | ALREADY_PRESENT | — | — | 2 unit tests | DONE |
| Artifact trust + SHA-256 | artifact_trust.rs | src-tauri/src/artifact_trust.rs | ALREADY_PRESENT | — | — | extensive | DONE |
| Catalog guard (embedded digest) | — | artifact_trust.rs:33-34 | ALREADY_PRESENT | — | — | canonical check | DONE |
| Reparse point rejection | — | artifact_trust.rs (reject_reparse_point) | ALREADY_PRESENT | — | — | — | DONE |
| Bounded pipe write | — | windows_job.rs:10-42 | ALREADY_PRESENT | — | — | 3 unit tests | DONE |
| Sanitized environment | — | supervisor.rs:646-679 | ALREADY_PRESENT | — | — | env test | DONE |
| Python discovery (Windows) | — | supervisor.rs:600-644 | ALREADY_PRESENT | — | — | — | DONE |
| Control plane bridge | — | src-tauri/src/control_plane.rs | ALREADY_PRESENT | — | — | — | DONE |
| Request registry + timeouts | — | control_plane.rs:556-591 | ALREADY_PRESENT | — | — | — | DONE |
| Model request lifecycle | — | control_plane.rs:349-486 | ALREADY_PRESENT | — | — | — | DONE |
| EOL/BOM invariant test | test_eol_invariant.py | — | PORT | tests/test_trust_chain_invariants.py | Adapt for LocalComet trust-chain files | new | PENDING |
| .gitattributes hardening | .gitattributes | .gitattributes | ADAPT | .gitattributes | Add trust-chain file rules | — | PENDING |
| Non-authorities registry | non_authorities.toml | — | PORT | security/invariants/non_authorities.toml | LocalComet-specific entries | new | PENDING |
| Security-negative taxonomy | security-negative-map.toml | — | PORT | security/invariants/security_negative.toml | Adapt to LocalComet test structure | new | PENDING |
| Invariant registry | invariants.toml | — | PORT | security/invariants/invariants.toml | LocalComet invariant IDs | new | PENDING |
| Response type validation | — | control_plane.rs (partial) | ADAPT | src-tauri/src/ipc.rs + control_plane.rs | Add expected response type map | new | PENDING |
| Scoped approval tokens | control_plane_core.rs | — | PORT | src-tauri/src/approval.rs | New module, CSPRNG, scoped, one-time | new | PENDING |
| Workspace propagation | — | — | PORT | src-tauri/src/workspace.rs + IPC | workspace.set protocol | new | PENDING |
| Evidence provenance | check_evidence_provenance.py | — | PORT | scripts/check_evidence_provenance.py | Adapt for LocalComet evidence | new | PENDING |
| Command parity gate | check_command_parity.py | — | PORT | scripts/check_command_parity.py | Svelte invokes == Tauri commands | new | PENDING |
| Streaming SHA-256 (product path) | — | artifact_trust.rs (sha256_file) | ADAPT | artifact_acquisition.rs | Verify streaming in download path | — | PENDING |
| Native smoke binary | lad_smoke.rs | — | DEFER_WITH_REASON | — | Requires sidecar protocol stability first | — | DEFERRED |
| AST async check | — | — | DEFER_WITH_REASON | — | LocalComet uses spawn_blocking already | — | DEFERRED |
| React/Zustand stores | src/lib/*.ts | — | REJECT | — | LocalComet uses Svelte 5 | — | REJECTED |
| Separate Python package layout | sidecar/ | modules/ | REJECT | — | LocalComet has monorepo modules | — | REJECTED |
| Second IPC client | ipc_client.rs | — | REJECT | — | LocalComet has single ipc.rs | — | REJECTED |

## Process ownership map (LocalComet)

```
Tauri main (lib.rs)
  → DesktopSidecarSupervisor (supervisor.rs)
    → ContainedSidecarProcess (windows_job.rs)
      → CreateProcessW (CREATE_SUSPENDED)
      → AssignProcessToJobObject (KILL_ON_JOB_CLOSE, ACTIVE_PROCESS=1)
      → ResumeThread
    → stdout reader thread → frame router → ControlPlaneBridge
    → stderr reader thread → ring buffer (4096)
    → health probe (desk-health-{seq}) → saw_health_ok
    → shutdown: app.shutdown request → wait 1500ms → terminate
  → ManagedRuntimeSupervisor (managed_runtime.rs)
    → ContainedManagedRuntimeProcess (windows_job.rs)
      → Same Job Object containment
```

## Approval map (LocalComet — TO BE IMPLEMENTED)

```
User confirms action in Svelte UI
  → Tauri command (approve_step)
  → Rust approval.rs: issue scoped token (CSPRNG 256-bit)
    scope = {tool, input_digest, workspace, session, expiry, nonce}
  → Frontend carries opaque token
  → Tauri command (run_tool_call) with token
  → Rust approval.rs: execute_approved()
    → validate scope (constant-time)
    → consume one-time
    → create execution grant
    → send authorized envelope to sidecar
  → Python sidecar: execute only with valid grant
```

## Workspace map (LocalComet — TO BE IMPLEMENTED)

```
User selects directory (native dialog)
  → Rust canonicalize + symlink/junction check
  → workspace.set.request → sidecar
  → Python creates new WorkspacePolicy
  → workspace.set.response with identity
  → Rust invalidates old approval tokens
  → UI confirmed state
```
````

### ПУТЬ: docs/governance/ARCHITECTURE_INPUTS.md (13 строк, 827 байт)

````markdown
# Architecture Inputs

Status: NOT_RATIFIED

| Package | Version | Bytes | SHA-256 | Status |
|---|---:|---:|---|---|
| LocalComet Universal Patches UP00-UP10 | 1.0.3 | 288215 | 95e35bf21f1c3af5a44db9f9944ddad01e3e5265cc40812cac9d733b59721f29 | CANDIDATE_UNACCEPTED |
| LocalComet Architecture Governance Pack | 1.0.4 | 73898 | 3dc9fd1434c68462352fe493ffbd640a7ef30911d299043be7f2b1ebc6c1b607 | CANDIDATE_UNACCEPTED |
| LocalComet Cross-Pack Conformance and Ratification Dossier | 1.4.0 | 146038 | 155f7856db8208b997722cae1c1f5eca86cfefcfd1ec07ce73a1c49883a1873b | CANDIDATE_UNACCEPTED |

Source baseline commit: 8f26dbe4e0c075299e169d91f9b7ba6d3699b817.

These inputs do not authorize implementation, enforcement, governance activation, or architecture ratification. Public release requires a human-selected software license.
````

### ПУТЬ: docs/governance/ratification/OR-01_AUTHORITY_BOUNDARY.md (40 строк, 2737 байт)

````markdown
# OR-01 authority boundary

OR-01 authorizes one bounded Windows delivery increment. It is not authority to redesign LocalComet or to implement the broader UP00 blueprint.

## Authorized

- Record the owner decisions in repository governance documents.
- Configure the pinned Tauri 2 toolchain for a per-user Windows NSIS installer.
- Package the existing Python sidecar and a private runtime so installed launch does not depend on developer tools.
- Adapt the existing Rust sidecar supervisor for bounded startup readiness, failure cleanup, and shutdown.
- Add application-level single-instance protection using the existing Windows system boundary.
- Suppress terminal windows for the release application and its managed child.
- Use existing LocalComet metadata and icon assets.
- Create and validate Start Menu and desktop shortcuts and uninstall registration.
- Add packaging, lifecycle, installation, uninstall, negative-authority, and rollback tests directly required by UP00-WP01.
- Produce unsigned internal artifacts and human-review evidence.

## Not authorized

- New or changed frontend-to-Rust commands, events, capabilities, or raw IPC.
- Changes to the IPC schema, protocol version, semantic methods, or error contract.
- Changes to Python business logic, model management, Review Center, Prompt Studio, autonomous tasks, publication, or approval policy.
- Database, storage, schema, migration, ownership, retention, or data-lifecycle changes.
- Vault access or modification.
- New telemetry, analytics, crash upload, update check, model download, remote configuration, or launch-time network access.
- Generic process execution, a shell plugin, shell-string execution, or caller-supplied executable paths/arguments.
- Architecture decomposition, layer reorganization, Tauri major upgrade, broad dependency upgrade, signing infrastructure, automatic updates, or public-release claims.
- Any source work for UP01-UP10.

## Existing authority retained

- Rust continues to own process lifecycle, native-window lifecycle, capability enforcement, and outer IPC validation.
- Python continues to own LocalComet semantics behind the existing fixed framed-pipe protocol.
- Svelte remains an untrusted UI client and receives no new privileged authority.
- Existing user data remains owned by its current authority; installer files and runtime logs are kept separate from it.
- Existing typed commands and event channels remain unchanged.

## Stop rule

Stop before implementation if a safe installer requires an IPC redesign, data-lifecycle decision, architectural decomposition, new launch-time network dependency, user-data deletion, Vault access, broad toolchain upgrade, or any authority not explicitly listed as authorized.
````

### ПУТЬ: docs/governance/ratification/OR-01_DECISION_MATRIX.yaml (66 строк, 1940 байт)

````yaml
schema_version: 1
decision_id: OR-01
mission_id: UP00-WP01_WINDOWS_ONE_CLICK_LAUNCH
accountable_owner: AleksSmash2019
effective_date: '2026-07-20'
effect: PROSPECTIVE_ONLY
repository_baseline:
  commit: 6c784ace543e345bdb8bd2f778be974dc89f2df5
  branch: main
source_mapping:
  status: COMPLETED_AND_REMEDIATED
  baseline_commit: 6c784ace543e345bdb8bd2f778be974dc89f2df5
governance:
  architecture_governance_pack:
    version: 1.0.4-correction-candidate
    sha256: 3dc9fd1434c68462352fe493ffbd640a7ef30911d299043be7f2b1ebc6c1b607
    decision: RATIFIED_PROSPECTIVELY
  architecture_constitution:
    document_id: LC-AGP-CONSTITUTION
    precedence: HIGHEST_NORMATIVE
    existing_code_conformance: NOT_RETROACTIVELY_ASSERTED
  automated_enforcement:
    status: NOT_ACTIVATED_BY_OR-01
roadmap:
  universal_patches:
    version: 1.0.3-correction-candidate
    sha256: 95e35bf21f1c3af5a44db9f9944ddad01e3e5265cc40812cac9d733b59721f29
    decision: ADOPTED_AS_LONG_TERM_ROADMAP
    blanket_implementation_authority: false
  cross_pack_dossier:
    version: 1.4.0
    sha256: 155f7856db8208b997722cae1c1f5eca86cfefcfd1ec07ce73a1c49883a1873b
    role: HISTORICAL_ADVISORY_AND_PRECEDENCE_INPUT
source_write_authority:
  authorized:
    - work_package: UP00-WP01
      title: Windows One-Click Launch and Installer Baseline
      platform: Windows
  denied:
    - UP01
    - UP02
    - UP03
    - UP04
    - UP05
    - UP06
    - UP07
    - UP08
    - UP09
    - UP10
deferred_decisions:
  - G03_G12_ARCHITECTURAL_DECOMPOSITION
  - G05_IPC_AND_CONTRACT_VERSIONING
  - G09_DATA_LIFECYCLE
  - PUBLIC_RELEASE_LICENSING
  - PRODUCTION_PERFORMANCE_BASELINES
  - PRODUCTION_CODE_SIGNING
  - AUTOMATIC_UPDATES
forbidden_authority_additions:
  - GENERIC_SHELL_EXECUTION
  - GENERIC_RAW_IPC
  - VAULT_WRITE
  - PUBLICATION
  - AUTOMATIC_APPROVAL
  - TELEMETRY_OR_ANALYTICS
  - AUTOMATIC_WINDOWS_LOGIN_START
release_classification: UNSIGNED_INTERNAL_BUILD
````

### ПУТЬ: docs/governance/ratification/OR-01_OWNER_RATIFICATION.md (85 строк, 3671 байт)

````markdown
# OR-01 — Architecture owner ratification

**Decision ID:** `OR-01`

**Accountable owner:** `AleksSmash2019`

**Decision source:** explicit repository-owner instruction in mission `UP00-WP01_WINDOWS_ONE_CLICK_LAUNCH`

**Effective date:** `2026-07-20`

**Effect:** prospective only

## Decision

The Architecture Governance Pack `1.0.4-correction-candidate`, including the Architecture Constitution identified inside that pack as `LC-AGP-CONSTITUTION`, is ratified prospectively for new LocalComet work. The Constitution has the highest normative precedence.

This decision does not retroactively prove that existing LocalComet code conforms. Candidate and advisory statuses inside the immutable input packages remain historical facts; this repository record supplies the later accountable human decision those packages could not supply themselves.

The source-mapping decision is:

```yaml
source_mapping_status: COMPLETED_AND_REMEDIATED
source_mapping_baseline_commit: 6c784ace543e345bdb8bd2f778be974dc89f2df5
```

The Universal Patches UP00-UP10 package `1.0.3-correction-candidate` is adopted as the long-term development roadmap. Roadmap adoption grants no blanket implementation authority.

The only source-writing work package authorized by OR-01 is:

`UP00-WP01 — Windows One-Click Launch and Installer Baseline`

Implementation authority for UP01-UP10 is `NONE`.

## Immutable inputs

| Input | SHA-256 |
|---|---|
| Universal Patches UP00-UP10 `1.0.3-correction-candidate` | `95e35bf21f1c3af5a44db9f9944ddad01e3e5265cc40812cac9d733b59721f29` |
| Architecture Governance Pack `1.0.4-correction-candidate` | `3dc9fd1434c68462352fe493ffbd640a7ef30911d299043be7f2b1ebc6c1b607` |
| Cross-Pack Dossier `1.4.0` | `155f7856db8208b997722cae1c1f5eca86cfefcfd1ec07ce73a1c49883a1873b` |

## Normative precedence used

For this work package, the applicable order is:

1. the ratified Architecture Constitution;
2. accepted constitutional decisions, if any;
3. ratified Architecture Governance Pack rules;
4. its dependency and quality-gate definitions;
5. its Codex protocol and mandatory templates;
6. accepted repository-specific owner and source-mapping evidence;
7. the adopted Universal Patch protocol and shared catalog;
8. accepted patch-specific decisions;
9. this separately authorized work package;
10. implementation.

The explicit owner mission is the patch-specific source-write authorization. It narrows the roadmap to UP00-WP01 and does not amend the Constitution.

## Deferred decisions

OR-01 does not decide or authorize:

- G03/G12 architectural decomposition;
- G05 IPC or contract versioning;
- G09 data lifecycle;
- public-release licensing;
- production performance baselines;
- production code signing;
- automatic updates;
- automated governance-enforcement activation.

UP00-WP01 must stop if it cannot be completed without one of these decisions.

## Required safeguards

- Preserve the existing Svelte/Tauri/Rust/Python trust and IPC boundaries.
- Keep Rust as the process and native-window enforcement boundary.
- Make no Vault, user-data, schema, migration, or ownership change.
- Add no generic shell, raw IPC, publication, approval, telemetry, update, or network authority.
- Produce reviewable commits, independent evidence inputs, bounded rollback evidence, and an unsigned internal installer only.
- Do not push, create a remote pull request, or modify `main`.

## Separate enforcement status

Ratification makes the Constitution and Governance Pack normative for this new work. OR-01 does not claim that automated repository-wide enforcement has been prepared or activated. Any such activation remains a separate accountable decision.
````

### ПУТЬ: docs/local_model_gateway_v6845.md (18 строк, 1663 байт)

````markdown
# LocalComet v6.84.5 Local Model Gateway

v6.84.5 adds the first bounded text-only local inference path:

```text
Svelte UI -> fixed Tauri commands -> Rust bridge -> framed IPC -> Python sidecar
  -> ProviderAdapter -> HarnessAdapter -> user-operated 127.0.0.1 model server
```

The only provider registry entry is `openai-compatible-local`. The endpoint is constructed internally as `http://127.0.0.1:<PORT>/v1`; the user can provide only a decimal port in the range `1024..65535`. There is no URL field, API key field, custom header field, proxy support, redirect following, DNS, LAN, cloud, HTTPS fallback, cookie support, or credential support.

The harness registry is fixed to `minimal` and `native-localcomet`. `minimal` emits one user message. `native-localcomet` emits one fixed LocalComet system message plus the user message, with no tools, files, project context, attachments, or hidden environment data.

Model discovery is explicit. A binding can be confirmed only for the exact provider, harness, numeric port, and model ID returned by the current discovery result. Bindings are memory-only and are invalidated when the port or discovered model set no longer matches.

Inference is one active text turn globally. Streaming uses bounded SSE parsing, accepts only choice index `0`, accepts only string content deltas, requires `[DONE]` or a bounded accepted finish reason, and fails closed on tool/function markers. Cancellation is idempotent, closes the active HTTP connection, joins the worker within a bounded timeout, and releases the single-active lock.

The frontend contacts only fixed Tauri commands. It never contacts the provider directly.
````

### ПУТЬ: docs/localcomet_autonomous_agent_architecture_v665a.md (291 строк, 11804 байт)

````markdown
# LocalComet Autonomous Agent Architecture - v6.65a

## Core Vision

LocalComet is a local autonomous agentic OS for development and computer control. It is not intended to remain a wrapper around OpenCode. OpenCode, Aider, Codex, and Computer Use are inspirations and adapters, not the final core.

OpenCode is replaceable. LocalComet is the system.

## Role Separation

- **User** = goal owner and final approval
- **LocalComet** = orchestrator, memory, risk controller, gatekeeper
- **OpenCode** = temporary code executor adapter
- **Aider/Codex-style engines** = replaceable coding backends
- **Computer Use** = desktop/UI operator
- **Internal Agent Runtime** = future core

## Target Architecture

### Core Layers

#### 1. LocalComet Control Panel
Central Tkinter-based UI for command input, status display, and human interaction. Manages routes to adapters and internal modules.

#### 2. Intent Router
Receives natural language commands and routes to appropriate adapters or internal systems based on command analysis.

#### 3. Context Pack Builder
Collects and structures project context, memory, and knowledge for agents to reference during execution.

#### 4. Plan Contract Generator
Creates execution contracts with safety checks, risk classifications, and approval requirements before action execution.

#### 5. Risk Classifier
Evaluates command risk levels (low, medium, high, blocked) and determines approval requirements.

#### 6. Policy Engine
Enforces GREEN-only workflow rules, including backups, manifest checks, and approval requirements.

#### 7. Task Queue
Manages ordered execution of validated tasks with status tracking and rollback capabilities.

#### 8. Tool Router
Directs validated commands to appropriate adapters (OpenCode, Aider, Computer Use, Terminal, etc.).

#### 9. Adapter Layer
Collection of replaceable adapters for different execution engines:

- **OpenCodeAdapter** - Interfaces with OpenCode for temporary code execution
- **AiderAdapter** - Interfaces with Aider coding engine  
- **CodexAdapter** - Interfaces with Codex engine
- **InternalPatchAdapter** - Manages internal codebase patches
- **ComputerUseAdapter** - Controls desktop and GUI operations
- **BrowserAdapter** - Browser automation interface
- **TerminalAdapter** - Command-line execution
- **FileSystemAdapter** - File and directory operations
- **TestRunnerAdapter** - Test execution and validation

#### 10. Internal Patch Engine
Manages codebase changes with diff control, manifest generation, and rollback capabilities.

#### 11. Terminal Executor
Sandboxed command execution with safety checks and audit logging.

#### 12. Computer Use Operator
GUI automation with vision, grounding, and safety controls.

#### 13. Browser Harness
Browser automation with profile isolation and safety controls.

#### 14. Test Runner
Automated testing with functional, contract, and stability validation.

#### 15. Backup/Manifest Manager
Creates pre-change backups and manifests for all modifications.

#### 16. Recovery Manager
Manages rollback operations and system recovery.

#### 17. Reviewer/Gate System
Provides human-review interface with ACCEPT/HOLD/REJECT verdicts.

#### 18. Memory/Project Knowledge Base
Persistent storage of learned patterns, successful strategies, and project context.

## Adapter Strategy

### Replaceable Adapters

LocalComet supports multiple coding and execution backends through a standardized adapter interface:

- **OpenCodeAdapter**: Current temporary adapter for OpenCode-based execution
- **AiderAdapter**: Alternative adapter for Aider-based coding
- **CodexAdapter**: Alternative adapter for Codex-based coding  
- **InternalPatchAdapter**: Adapter for internal codebase modifications
- **ComputerUseAdapter**: Adapter for desktop GUI automation
- **BrowserAdapter**: Adapter for browser automation
- **TerminalAdapter**: Adapter for command-line execution
- **FileSystemAdapter**: Adapter for file system operations
- **TestRunnerAdapter**: Adapter for test execution and validation

### Key Principles

1. **OpenCode is replaceable** - Current adapter can be swapped out
2. **LocalComet is the system** - Core functionality remains independent of adapters
3. **AdapterInterface** - Standardized interface for all adapters
4. **Route selection** - Intent router chooses appropriate adapter at runtime
5. **Safety consistent** - All adapters must follow LocalComet's safety policies

## Safety and Governance

### GREEN-Only Workflow

1. **Backup before changes**: Mandatory pre-change snapshot creation
2. **Manifest before changes**: Complete change manifest generation
3. **Diff limits**: Maximum change size restrictions
4. **Risk class**: Automatic risk classification for all operations
5. **Approval requirements**: Different approval levels for different risk levels
6. **Contracts gate**: All changes require contract validation
7. **Functional gate**: All changes require functional test validation
8. **Strict stability gate**: All changes require strict project stability validation
9. **Reviewer verdict**: Final review with ACCEPT/HOLD/REJECT options
10. **Rollback path**: Guaranteed rollback capability for all changes

### Risk Classification

- **Low**: Safe UI automation, read operations
- **Medium**: File modifications, typing actions
- **High**: Code compilation, file replacements
- **Blocked**: Destructive operations, admin actions, secrets access

### Approval Requirements

- **Low risk**: No approval needed (auto-execute with observation)
- **Medium risk**: Requires confirmation before execution
- **High risk**: Requires explicit reviewer approval
- **Blocked**: Always blocked, cannot be overridden

### Gate System

1. **GREEN** - All checks pass, change approved
2. **YELLOW** - Warnings present, requires attention but can proceed
3. **RED** - Critical failures, change blocked
4. **HOLD** - Manual review required
5. **REJECT** - Change rejected, rollback initiated

## Autonomous Agent Loop

### Future Internal Loop

1. **Observe**: Scan environment, screen, and context
2. **Understand**: Analyze current state and requirements
3. **Plan**: Create execution plan with risk classification
4. **Risk Classify**: Determine required approvals and safety checks
5. **Backup**: Create system backup and change manifest
6. **Edit**: Execute changes through appropriate adapters
7. **Test**: Run functional, contract, and stability tests
8. **Repair**: Fix any test failures or issues
9. **Report**: Generate comprehensive execution report
10. **Accept/Rollback**: Final decision based on all checks

### Loop Characteristics

- **One-action-per-observation**: No blind multi-step execution
- **Grounded actions required**: All GUI actions must be visually grounded
- **Visual guard decisions**: Screen changes trigger decision points
- **Continuous observation**: System constantly monitors state

## Roadmap from v6.65 to v7.0

### Development Phases

#### v6.65: Architecture and Working Directory Guard
- Complete architecture documentation
- Implement working directory isolation
- Create base safety guardrails
- Establish foundation for internal agent runtime

#### v6.66: Capability Map v2, Read-Only and Accurate
- Develop accurate internal capability map
- Implement read-only mode for critical operations
- Enhance route selection accuracy
- Improve safety check precision

#### v6.67: Task Contract Registry
- Create immutable task contract registry
- Implement contract lifecycle management
- Add contract validation and enforcement
- Establish contract lineage tracking

#### v6.68: Tool Adapter Interface
- Standardize adapter interface
- Implement adapter registration system
- Add adapter testing framework
- Create adapter lifecycle management

#### v6.69: Internal Patch Engine Prototype
- Develop internal patch creation system
- Implement diff-based patching
- Create rollback infrastructure
- Add patch validation framework

#### v6.70: Diff Control and Rollback Manager
- Implement diff tracking and validation
- Create automated rollback capabilities
- Add rollback testing framework
- Improve patch safety mechanisms

#### v6.80: Internal Coding Loop
- Implement self-contained coding cycle
- Add internal modification capabilities
- Implement code review integration
- Create quality assurance integration

#### v6.90: Computer Use Supervised Operator
- Enhance GUI automation with supervision
- Add human-in-the-loop controls
- Implement safety-verified automation
- Create user approval workflow

#### v7.0: Autonomous Local Agent Runtime MVP
- Launch fully autonomous local agent runtime
- Implement complete self-governance
- Add comprehensive logging and reporting
- Launch production-ready system

## Non-Goals

### Explicit Exclusions

- **Not uncontrolled full desktop automation**: All automation requires grounding and approval
- **Not blind self-modification**: All changes require explicit safety checks and approvals
- **Not one giant system doctor patch**: Changes are incremental and reversible
- **Not dependent on OpenCode forever**: OpenCode is a temporary adapter
- **Not deleting backups/screenshots without approval**: All deletions require explicit confirmation
- **Not weakening safety for convenience**: Safety rules are non-negotiable
- **Not bypassing human oversight**: All significant changes require human approval
- **Not running without audit trails**: Every action is logged and auditable

## Next Implementation Candidates

### 5 Small Safe Next Patches

1. **Working Directory Guard**: Implement directory isolation and protection
2. **Accurate Capability Map v2**: Create comprehensive internal capability registry
3. **Task Contract Registry**: Establish immutable contract storage and validation
4. **Adapter Interface Skeleton**: Create base adapter interface with registration
5. **Diff Limit Guard**: Implement change size and impact restrictions

### Rationale

- **Incremental approach**: Each patch builds on previous work
- **Safety-first**: All changes maintain or improve safety
- **Backwards compatible**: No breaking changes to existing functionality
- **Testable**: Each change has clear acceptance criteria
- **Documented**: Complete documentation for each change

## Acceptance Criteria

### Validation Requirements

The architecture document is accepted only if:

- [ ] No Python source was edited (only docs/report files created)
- [ ] Docs/report files created only (not Python source)
- [ ] Current baseline remains GREEN (all tests passing)
- [ ] Architecture clearly states OpenCode is temporary
- [ ] Roadmap is concrete and incremental with clear milestones
- [ ] Safety policies are preserved and documented
- [ ] Adapter strategy is fully specified
- [ ] Non-goals are clearly stated

### Quality Gates

1. **Architectural completeness**: All major components documented
2. **Safety preservation**: No weakening of existing safety measures
3. **Incremental roadmap**: Path from v6.65 to v7.0 is feasible
4. **Documentation quality**: Clear, actionable, well-structured
5. **Implementation readiness**: Concrete next steps identified

## Final Architecture Summary

LocalComet evolves from a wrapper system into a fully autonomous local agent runtime. The core system orchestrates multiple replaceable adapters while maintaining strict safety controls. The architecture emphasizes:

- **Safety above all**: GREEN-only workflow with multiple gates
- **Replaceability**: Adapters can be swapped without changing core
- **Incremental development**: Clear roadmap with achievable milestones
- **Human oversight**: User retains final approval authority
- **Auditable operations**: Complete audit trails for all actions

The system will mature through well-defined phases, maintaining reliability and safety throughout the evolution from v6.65 to v7.0.
````

### ПУТЬ: docs/managed_runtime_v68451.md (11 строк, 1570 байт)

````markdown
# LocalComet v6.84.5.1 Managed llama.cpp Runtime

v6.84.5.1 introduces a managed runtime path for one engine only: `llama.cpp`.

Production runtime packages remain external to the repository under `%LOCALAPPDATA%\LocalComet\runtimes\llama.cpp`. A package is runnable only when its canonical `runtime_manifest.json` and `llama-server.exe` hash match LocalComet-controlled approval metadata. The source-controlled production registry intentionally contains zero approved entries in this release, so the truthful default UI state is `Managed Runtime: Not installed`.

Managed models are scanned only from `%LOCALAPPDATA%\LocalComet\models`, direct children only, `.gguf` only, with bounded count and size. The frontend receives opaque `model_id` values, sanitized display names, sizes, availability, and file-identity fingerprints, never absolute paths.

The runtime supervisor owns the private loopback port, per-launch credential file, bounded logs, readiness checks, and shutdown. The Python sidecar receives the credential only through the fixed internal `model.managed.attach` method and drops it through `model.managed.detach`. The Svelte UI cannot provide executable paths, model paths, ports, credentials, environment variables, or raw runtime arguments.

Tests use `tools/test_fixtures/fake_managed_llama_server.py`, launched only as a source-only Python fixture through test code. It is not a production engine, is not in the production registry, is not installed under managed runtime roots, and no `.exe`, `.bat`, or `.ps1` fixture is authored by this release.
````

### ПУТЬ: docs/pr-best-of-two.md (136 строк, 8528 байт)

````markdown
# PR: Best-of-Two Wiring Sprint v6.84.6

**Ветка:** `integration/best-of-two-local-agent` → `continue/after-build-week-2026`
**Дата:** 2026-07-25
**Base:** `continue/after-build-week-2026` @ `767a7e9` (прямой предок HEAD — мерж fast-forward, конфликтов нет)

> ℹ️ **Целевая ветка:** `continue/after-build-week-2026`. Ветка `main` в репозитории
> не существует (ни локально, ни в origin); существующие ветки — `build-week-2026` и
> `continue/after-build-week-2026`. Мерж в целевую ветку = fast-forward, конфликтов нет.

---

## Summary

Ветка подключает security-ядро, перенесённое из параллельной реализации Local Agent
Desktop, к продуктовому пути LocalComet: approval-токены (CSPRNG, scoped, one-time)
теперь выдаются и атомарно потребляются через Tauri-команды, добавлены evidence
provenance, UI fake-state и tool-risk гейты, honest real-sidecar тесты и in-process
smoke. Ключевое архитектурное уточнение: desktop sidecar **не исполняет file-tools**
(`files.*` = `unsupported_method`), поэтому approval/workspace enforcement живёт в Rust,
а не в sidecar. Все гейты зелёные, Windows-инсталлятор собирается.

---

## Changes

| Файл | Тип | Описание |
|---|---|---|
| `src-tauri/src/approval.rs` | NEW | CSPRNG 256-bit токены, constant-time scope validation, atomic `execute_approved`, TTL sweep, grant expiry (15 тестов) |
| `src-tauri/src/approval_commands.rs` | NEW | Tauri-команды `request_approval`/`execute_approved`/`set_workspace` + `ApprovalState` |
| `src-tauri/src/workspace.rs` | NEW | Rust workspace authority: canonicalization, reparse rejection, token invalidation (7 тестов) |
| `src-tauri/src/lib.rs` | MOD | wiring: `mod approval/approval_commands/workspace`, `ApprovalState`, +3 handlers (parity 42/42) |
| `src-tauri/src/supervisor.rs` | MOD | `real_sidecar_env()`: silent-skip → panic при `LOCALCOMET_REQUIRE_REAL_SIDECAR` |
| `src-tauri/Cargo.toml` / `Cargo.lock` | MOD | +`getrandom`, +`subtle` |
| `src/lib/bridge/approval.ts` | NEW | Svelte bridge для approval/set_workspace команд |
| `desktop/contracts/localcomet_ipc_v1.schema.json` | MOD | `workspace.set` request/response контракт |
| `modules/workspace_policy.py` | NEW | переиспользуемый примитив confinement (self-test OK) |
| `security/invariants/invariants.toml` | NEW | 12 инвариантов; APPROVAL-001/002, EVIDENCE-001, UI-001 → active |
| `security/invariants/non_authorities.toml` | NEW | 16 записей «что НЕ является authority» |
| `security/invariants/tool_risk_levels.toml` | NEW | 5 инструментов (3 mutating → approval) |
| `scripts/check_tool_risk_registry.py` | NEW | gate полноты классификации (injection-proven) |
| `scripts/check_command_parity.py` | NEW | Svelte invoke == Tauri handler (42/42) |
| `scripts/check_ui_fake_state.py` | NEW | Math.random / long-timer-near-state gate (75 файлов, 0 нарушений) |
| `scripts/refresh_evidence.py` | NEW | evidence с tree digest |
| `scripts/check_evidence_provenance.py` | NEW | STALE-детекция (injection-proven) |
| `scripts/check_real_sidecar_tests.py` | NEW | CI gate для require-mode |
| `scripts/smoke_test.py` | NEW | in-process smoke реального sidecar (8/0) |
| `localcomet_test_harness.py` | NEW | harness, драйвит реальный `DesktopSidecarRuntime` |
| `scripts/doctor.py` | NEW | preflight (Rust/linker/Node/npm/Python/WebView2/NSIS) |
| `scripts/build.sh` | NEW | 7-step fail-fast pipeline (`.ps1` не создан — AGENTS.md) |
| `tests/test_trust_chain_invariants.py` | NEW | EOL/BOM/final-LF инварианты (15 файлов) |
| `.gitattributes` | MOD | усилен для trust-chain файлов |
| `config.py`, `approved-artifacts.v1.json` | MOD | CRLF→LF fix |
| `docs/engineering/best-of-two-final-report.md` | NEW | итоговый отчёт (2 фазы) |
| `docs/engineering/best-of-two-migration-matrix.md` | NEW | карта donor→LocalComet |
| `docs/unverified-ledger.md` | NEW | 9 записей недоказанного |
| `audit/AUDIT_GUIDE.md`, `audit/*.md`, `audit/manifest.sha256`, `audit/LocalComet-AUDIT-2026-07-25.txt` | NEW | аудит-гайд + текстовый аудит (donor-бинарники исключены) |

**Итого:** 33 файла, +5175 / −19.

---

## Security

- **Approval enforcement:** CSPRNG (`getrandom`, 256 бит), constant-time сравнение
  (`subtle`), scope = tool + canonical input digest + workspace + session + expiry,
  one-time consume, TTL sweep, execution-grant expiry (30 c). Нет bypass-пути:
  guarded tool проходит только через `execute_approved`.
- **Invariants активированы:** INV-APPROVAL-001, INV-APPROVAL-002, INV-EVIDENCE-001,
  INV-UI-001 (с `verification_method`).
- **Evidence provenance:** каждое доказательство привязано к tree digest исходников;
  изменение кода без refresh → STALE (injection-proven).
- **UI integrity:** frontend не генерирует fake backend state (`Math.random`=0,
  таймеры = polling/watchdog).
- **Ключевая находка:** desktop sidecar НЕ исполняет file-tools (`files.*` =
  `unsupported_method`); approval/workspace enforcement живёт в **Rust**, а не в sidecar.
  Критические дефекты donor (approval bypass, dual IPC, readiness «любой кадр»,
  не дренируется stderr) **не унаследованы**.

---

## Test Results [прогон]

```
cargo test            147 passed, 0 failed, 6 ignored
smoke (real sidecar)  8 passed, 0 failed
cargo clippy -D warnings  OK (0 warnings)
cargo fmt --check     OK
ui-fake-state         75 files, 0 violations
evidence provenance   4 files fresh (tree=d5c4c42c…)
tool-risk registry    5 tools (3 mutating → approval)
trust-chain           15 files OK
command parity        42/42
build                 LocalComet_6.84.6_x64-setup.exe (13.32 MB, SHA-256: 7fc82beb…)
                      LocalComet.exe (13.87 MB, SHA-256: 2bfdd0c7…)
```

---

## Known Issues / Unverified

Из `docs/unverified-ledger.md`:

| ID | Проблема | Статус |
|---|---|---|
| U-001 | npm registry UNREACHABLE (offline) — блокирует `npm ci`, не `npm run build` | BLOCKED (infra) |
| U-002 | packaged installer | PARTIAL — собран, не установлен/запущен (требует GUI) |
| U-003 | 6 ignored real-sidecar тестов (требуют окружения) | DEFERRED (honest skip) |
| B-003 | workspace IPC в sidecar | N/A (sidecar не исполняет fs-tools) |
| D-003 | CI workflow отсутствует в чекауте | DEFERRED |
| DONOR-001 | 2 donor-материала отсутствуют | ЗАЯВЛЕНО |
| APPROVAL-UI-001 | approval GUI-флоу | PARTIAL (Rust boundary реален; GUI ждёт fs-tools) |

---

## Commits

| Hash | Сообщение |
|---|---|
| `4fa48fe` | feat(approval): CSPRNG scoped one-time tokens + product wiring |
| `822575e` | feat(workspace): WorkspacePolicy primitive + IPC schema workspace.set |
| `4a69094` | chore(audit): invariant registries + trust-chain and evidence gates |
| `cddd0e8` | test(sidecar): honest real-sidecar skip + in-process smoke harness |
| `4b0418e` | build: preflight doctor.py + build.sh pipeline |
| `36af461` | docs: best-of-two final report, unverified ledger, audit guide |
| `8b23f8c` | chore(invariants): activate INV-APPROVAL-001/002, INV-EVIDENCE-001; verify INV-UI-001 |

---

## Merge checklist

- [x] Все гейты зелёные (вывод показан)
- [x] Конфликтов с base нет (fast-forward)
- [x] **Целевая ветка:** `continue/after-build-week-2026` (`main` не существует; fast-forward, без конфликтов)
- [ ] Push ветки в origin (`integration/best-of-two-local-agent` ещё не запушена)
- [ ] Рецензент: проверить approval boundary и unverified-ledger перед мержем
````

### ПУТЬ: docs/project_documentation.md (52 строк, 1945 байт)

````markdown
# LocalComet — Документация проекта

## Обзор

LocalComet / LocalAgent — локальный Python-агент с маршрутизацией команд, LLM-планированием и браузерной автоматизацией.

## Архитектура

Поток: `Router → Planner → Executor → Agents → Modules`

- **Router** (`core/router.py`) — классификация команды по ключевым словам
- **Planner** (`core/planner.py`) — генерация JSON-плана через LLM
- **Executor** (`core/executor.py`) — диспетчеризация в агентов
- **Agents** (`agents/`) — тонкие адаптеры (18 агентов)
- **Modules** (`modules/`) — реализация (~140 модулей)

## Директории

| Директория | Назначение |
|---|---|
| `agents/` | Тонкие агент-адаптеры с `handle(action, data)` |
| `core/` | Ядро: router, planner, executor, llm, state, loop |
| `modules/` | Вся бизнес-логика: браузер, relay, self-edit, автоматизация |
| `next/` | Консоль v5/v6: app_v5, goal_manager, task_planner, task_queue |
| `desktop/` | Tauri + SvelteKit desktop-приложение |
| `tools/` | Тесты, утилиты, аудит, инсталлятор |
| `scripts/` | Вспомогательные скрипты (манифест, gateway) |

## Запуск

```powershell
python -m next.app_v5
python LocalComet_Control_Panel.py
```

## Тестирование

```powershell
python -m py_compile <file>
python tools/model_tester.py
python tools/hard_model_tester.py
python tools/test_gpt_bridge.py
python test_full_flow.py
```

## Конфигурация

`config.py`: LMSTUDIO_API, MODEL, OPENAI_MODEL, OPENAI_RESPONSES_API

## Workflow

`request.md → response.json → validate → apply → after patch`
````

### ПУТЬ: docs/team_plan_10_agents.md (120 строк, 5643 байт)

````markdown
# План работы команды из 10 агентов

## Классификация архитектуры

### Старая архитектура (v3)
- **Вход:** `app.py` — "LocalComet v3 — Agent Loop"
- **Папки:** `agents/`, `core/`, `modules/`
- **Паттерн:** route → plan → execute (линейный pipeline)
- **Агенты:** 18 тонких адаптеров `handle(action, data)`
- **Проблема:** циклическая зависимость core ↔ modules

### Новая архитектура (v5/v6)
- **Вход:** `next/app_v5.py` — "LocalComet v6.02 - Command Center"
- **Папки:** `next/`, `desktop/`, `tools/`, `scripts/`
- **Паттерн:** goal → plan → queue → observe (оркестрация задач)
- **Компоненты:** goal_manager, task_planner, task_queue, observer
- **Desktop:** IPC-контракты, sidecar runtime

### Общий слой
`core/` и `modules/` используются обеими архитектурами.

---

## Распределение задач

| # | Агент | Роль | Приоритет |
|---|-------|------|-----------|
| 1 | agent_01_architect | Разрыв цикла core ↔ modules | P1 |
| 2 | agent_02_refactor_app | Декомпозиция app_v5.py | P2 |
| 3 | agent_03_god_modules | Разделение god-модулей | P3 |
| 4 | agent_04_security | Безопасность и легаси | P4 |
| 5 | agent_05_testing | Тестирование | P2 |
| 6 | agent_06_desktop | Десктопное приложение | P3 |
| 7 | agent_07_browser | Браузерная автоматизация | P3 |
| 8 | agent_08_knowledge | Система знаний | P3 |
| 9 | agent_09_ui | UI и Control Panel | P4 |
| 10 | agent_10_docs_ci | Документация и CI | P2 |

---

## Детальные задачи

### 1. Архитектор (P1)
Разорвать циклическую зависимость core ↔ modules:
- Вынести `core/state.py` → `common/state_store.py`
- Убрать импорты core.router/planner/executor из modules
- Создать интерфейс для modules → core

### 2. Рефакторинг app_v5 (P2)
Декомпозировать `next/app_v5.py` (2039 строк):
- Заменить 12 функций `_run_direct_*` на реестр команд `core/commands.py`
- Перенести SHORTCUTS (120+ записей) в `core/router.py`
- Оставить в app_v5 только REPL-цикл

### 3. Декомпозиция god-модулей (P3)
Разделить модули > 1500 строк:
- `premium_task_panel_ru` (2957) → panel_core + panel_widgets + panel_state
- `desktop_control_plane_ru` (2208) → control_plane + ipc_handler + supervisor
- `computer_use_contract_tests_ru` (1818) → contract_fixtures + contract_runner
- `local_model_gateway_ru` (1811) → gateway_core + model_registry + health_check
- `stability_test` (1664) → test_runner + test_fixtures + test_reporter

### 4. Безопасность и легаси (P4)
- Устранить shell-инъекцию в `agent.py:search_web()`
- Убрать хардкод LLM URL из agent.py
- Заменить `app.py` на редирект к `next/app_v5`
- Убрать прямые импорты core.state из 5 агентов

### 5. Тестирование (P2)
- Создать pytest-совместимый runner для tools/
- Интеграционные тесты для next/task_planner, next/goal_manager
- Покрыть regression_commands и auto_verification
-_target: 80% покрытие core/ и next/_

### 6. Десктоп (P3)
- Развитие `desktop/contracts/` IPC-схем
- Синхронизация sidecar runtime с control plane
- Тесты для desktop IPC в tools/

### 7. Браузерная автоматизация (P3)
Консолидация 10+ browser_* модулей:
- Создать `modules/browser_facade.py` — единая точка входа
- Устранить дублирование: browser_direct, browser_autopilot, browser_super, browser_operator
- Единый интерфейс для agents/browser_agent.py

### 8. Система знаний (P3)
Унификация 11 knowledge_* модулей:
- Pipeline: proposal → review → decision → injection
- Единый `modules/knowledge_pipeline.py`
- Интеграция с core/state для персистентности

### 9. UI и Control Panel (P4)
- Стабилизация `LocalComet_Control_Panel.py`
- Убрать дублирование premium_ui_* (3 модуля → 1)
- Интеграция с command_center_ui

### 10. Документация и CI (P2)
- Создать `docs/engineering/adr-002-target-architecture.md`
- Настроить GitHub Actions: py_compile + tools/ тесты
- Обновить README.md с новой архитектурой
- Документировать контракты для каждого агента

---

## Порядок выполнения

```
Фаза 1 (P1-P2): architect → refactor_app → security → testing → docs_ci
Фаза 2 (P3):    god_modules → desktop → browser → knowledge
Фаза 3 (P4):    ui
```

## Критерии готовности

- [ ] Нет циклических импортов core ↔ modules
- [ ] app_v5.py < 300 строк
- [ ] Нет модулей > 800 строк
- [ ] Все агенты используют фасад state_store
- [ ] Покрытие тестами core/ и next/ ≥ 80%
- [ ] CI проходит без ошибок
````

### ПУТЬ: docs/unverified-ledger.md (124 строк, 8925 байт)

````markdown
# LocalComet — Реестр недоказанного (Unverified Ledger)

**Дата:** 2026-07-25
**Ветка:** `integration/best-of-two-local-agent` @ `767a7e9`

Каждая запись: что утверждается → почему не доказано в этой среде → какой
минимальный доступ закрыл бы вопрос → статус.

Правило: утверждение без доказательства помечается `[ЗАЯВЛЕНО]` и не считается
закрытым. Этот реестр — источник правды о границах доказанности.

---

## U-001. npm registry недостижим (infrastructure, не продукт)

- **Утверждается:** `npm ci` / `npm install` необходимы для сборки Svelte-фронтенда.
- **Почему не доказано:** `npm ping` → UNREACHABLE (offline/blocked). Подтверждено
  `scripts/doctor.py` [прогон]. Это блокирует `tauri build` и vitest-прогон.
- **Минимальный доступ:** сеть к `registry.npmjs.org` (или вендоринг `node_modules`).
- **Статус:** BLOCKED (infrastructure). Не является дефектом продукта.

## U-002. Packaged binary / installer

- **Утверждается:** NSIS-инсталлятор для Windows собирается.
- **Статус: СОБРАН [прогон].** `npx tauri build --bundles nsis` → exit 0
  (release-компиляция ~29-42s). Артефакты:
  - `LocalComet.exe`: 14 547 968 B, sha256=`2bfdd0c78ba619c128398157fbeb7190deb4ff0c68eb92368ebc59c5ca52ad78`
  - `LocalComet_6.84.6_x64-setup.exe`: 13 963 772 B, sha256=`7fc82beb3ff74a3ae5ad55b8b365dbd00acd92d81a007f74c1fb0c5dcbfa488f`
  - `npm run build` работает **offline** (`node_modules` vendored, 104 МБ) — U-001
    блокирует `npm ci`, но не сборку при наличии зависимостей.
  - Tauri использует **cached NSIS** (см. H-001).
- **Остаётся недоказанным:** установка и запуск инсталлятора (требует интерактивной
  GUI-сессии), smoke установленного приложения, поведение на путях с пробелами/кириллицей,
  стандартный пользователь без admin.
- **Статус:** PARTIAL — инсталлятор собран и хеширован, но не установлен/запущен.

## U-003. 6 ignored real-sidecar тестов требуют окружения

- **Утверждается:** интеграционные тесты supervisor.rs проходят против реального sidecar.
- **Почему не доказано:** тесты помечены `#[ignore]` / требуют
  `LOCALCOMET_TEST_PROJECT_ROOT` + `LOCALCOMET_TEST_PYTHON`. Без них — честный SKIP
  (после фикса Task D: panic при `LOCALCOMET_REQUIRE_REAL_SIDECAR=1`).
- **Минимальный доступ:** установленный sidecar + указанные env-переменные.
- **Статус:** DEFERRED (требует окружения). Метрика «147 passed» семантически честна
  после Task D (silent-skip устранён).

## B-003. Workspace IPC round-trip в sidecar — N/A

- **Утверждается:** sidecar получает `workspace.set` и применяет WorkspacePolicy к
  файловым операциям.
- **Почему не доказано / N/A:** desktop sidecar **не исполняет файловые инструменты**
  (`files.*` = `unsupported_method`, подтверждено smoke step 6 [прогон]). Propagating
  workspace в sidecar нечего охранять. Workspace authority — Rust approval scope
  (`workspace.rs` + `approval_commands.rs::set_workspace`), реализовано и покрыто тестами.
- **Что сделано:** схема `workspace.set` добавлена в IPC-контракт; `modules/workspace_policy.py`
  — тестированный примитив (self-test [прогон]).
- **Минимальный доступ для активации:** появление fs-tool исполнения в sidecar.
- **Статус:** N/A (INV-WORKSPACE-001 остаётся `planned` до появления fs-tool path).

## D-003. CI workflow отсутствует в чекауте

- **Утверждается:** CI устанавливает sidecar до `cargo test` и ставит
  `LOCALCOMET_REQUIRE_REAL_SIDECAR=1`.
- **Почему не доказано:** `.github/workflows/` пуст в этом чекауте (несмотря на
  коммит `ci: add validation workflow` в истории — файлы не present).
- **Минимальный доступ:** восстановить/создать `.github/workflows/ci.yml`.
- **Статус:** DEFERRED. Gate `scripts/check_real_sidecar_tests.py` готов к подключению.

## H-001. doctor.py эвристики vs реальная сборка

- **C-linker:** в чистом PowerShell doctor.py помечает MISSING (`cc`/`cl`/`link` не на
  PATH, `ziglang` не установлен), но cargo успешно линкует (147 тестов + release-сборка)
  через rustup MSVC-детекцию [прогон]. В Git Bash (MSYS) doctor.py находит линкер (OK).
  Эвристика консервативна.
- **NSIS:** doctor.py помечает `makensis` MISSING (не на PATH), НО Tauri 2 использует
  **cached NSIS** (от build-week, в кэше Tauri), поэтому `tauri build --bundles nsis`
  успешно создаёт инсталлятор [прогон] (см. U-002).
- **Интерпретация:** реальный `cargo build` / `tauri build` — authority, не эвристика
  preflight.
- **Статус:** RESOLVED (ложноположительные эвристики; продукт линкуется и бандлится).

## H-002. app.health не является advertised capability

- **Утверждается:** smoke step 4 ожидал `app.health` в advertised capabilities.
- **Почему ложное:** `app.health` — lifecycle-endpoint, обрабатывается ДО проверки
  capabilities; в hello advertised маркер `"lifecycle"`, а не `"app.health"`.
  Подтверждено: capabilities = 26 методов incl. `lifecycle` + `model.catalog.get` [прогон].
- **Статус:** RESOLVED (правка в тесте, не в продукте; smoke 8/8 green).

## DONOR-001. Отсутствуют donor-материалы

- **Утверждается:** полная верификация donor-дефектов по исходникам Local Agent Desktop.
- **Почему не доказано:** в среде отсутствуют
  `LocalComet_Detailed_Static_Audit_2026-07-25.txt` и
  `LocalAgent_Source_vs_Audit_Diff_2026-07-25.txt` (см. `audit/evidence-ledger.md`).
  Утверждения о donor-дефектах — из `WP-1.45.4_Independent_Verification` [ЗАЯВЛЕНО].
- **Минимальный доступ:** указанные файлы / полные исходники donor.
- **Статус:** ЗАЯВЛЕНО (относительно donor-кода).

## APPROVAL-UI-001. Approval-команды не вызываются реальным GUI-флоу

- **Утверждается:** пользователь инициирует guarded tool через approval в UI.
- **Почему не доказано:** Tauri-команды `request_approval`/`execute_approved`
  зарегистрированы и покрыты (parity 42/42, cargo test), Svelte bridge
  `approval.ts` существует, но продуктового UI-флоу, инициирующего guarded
  fs-tool, нет (sidecar не исполняет fs-tools — см. B-003).
- **Статус:** PARTIAL. Rust authorization boundary реален и атомарен; продуктовый
  GUI-путь появится вместе с fs-tool исполнением.

---

## Сводка

| ID | Область | Статус |
|---|---|---|
| U-001 | npm registry | BLOCKED (infra) |
| U-002 | packaged installer | PARTIAL (собран, не установлен) |
| U-003 | real-sidecar тесты | DEFERRED (env) |
| B-003 | workspace IPC в sidecar | N/A |
| D-003 | CI workflow | DEFERRED |
| H-001 | C-linker preflight | RESOLVED (false-positive) |
| H-002 | app.health capability | RESOLVED (тест) |
| DONOR-001 | donor-материалы | ЗАЯВЛЕНО |
| APPROVAL-UI-001 | approval GUI-флоу | PARTIAL |
````

### ПУТЬ: docs/work-packages/phase-b0/PHASE-B0_PROJECT_KNOWLEDGE_ROLLBACK.md (211 строк, 9876 байт)

````markdown
# Phase B0 — Project Knowledge Rollback Plan

Status: `DOCUMENTATION_CONTRACT_ONLY`

This plan defines rollback for the Phase B0 documentation and the minimum
rollback obligations for any later Project Knowledge implementation. Phase B0
itself creates no runtime state and does not access a knowledge source.

## 1. Rollback invariants

Every rollback MUST:

- preserve the user-selected source byte-for-byte;
- avoid the user's Obsidian Vault, normal AppData, installed application, and
  historical repository unless a later, explicit rollback authorization names
  an isolated test target;
- avoid `reset --hard`, `clean`, stash-based loss, or deletion of unrelated work;
- remove no model, managed runtime, conversation, project, or user file;
- restore truthful Project Knowledge UI state;
- leave ordinary local chat and the Phase A model lifecycle functional; and
- produce reviewable repository and runtime evidence.

## 2. Phase B0 documentation rollback

Before any future commit, the Phase B0 change is only four untracked Markdown
files. If the owner rejects the contract, stop and request explicit direction;
do not remove files automatically.

After a future documentation commit, rollback is additive. Preserve these four
documents and add a reviewed supersession or revocation record that identifies
the affected contract version and commit, the reason, the effective status, and
any replacement authority. The original files remain historical evidence and
must not be removed, emptied, or rewritten to conceal their prior authority.

Deleting any Phase B0 documentation file requires explicit owner authorization
that names each file and explicitly overrides the repository no-delete rule. A
generic request to roll back, revert, disable, or supersede Phase B0 is not file-
deletion authority. History must not be rewritten and the Build Week tag must
not move.

Documentation rollback verification:

```powershell
git diff --check
git --no-pager status --short --untracked-files=all
git --no-pager log -5 --oneline --decorate
```

Run the explicit trailing-whitespace and final-newline check from the test and
acceptance plan over these four documents and any additive supersession record.
After an authorized staging action, also run `git diff --cached --check`.

Because Phase B0 changes no product code or runtime state, no Python, npm, Cargo,
installer, AppData, or installed-application rollback action is required.

## 3. Future implementation rollback triggers

Any later Project Knowledge implementation must be held or rolled back if one of
these occurs:

- source content, metadata, attributes, names, or write times change;
- a path escapes the selected root or any reparse point or cloud placeholder is
  accepted;
- anything beyond root type, root reparse status, fixed-volume identity, and a
  sanitized display name is inspected before consent;
- source content is read before consent or after revocation;
- a repository or project root is defaulted, inferred, or inspected without
  separate explicit project-root consent;
- external `source_paths` are resolved or opened without that separate consent;
- source content reaches a model without exact preview approval;
- a stale, altered, partial, or replayed preview is accepted;
- absolute paths, source text, prompts, or secrets appear in logs or frontend
  payloads;
- a failed refresh remains usable for new previews;
- persisted consent cannot be revoked completely;
- semantic consent is persisted outside Python or duplicated by Rust;
- cancellation work does not join within 5 seconds or a prior-generation result
  becomes active;
- ordinary chat becomes unavailable when Project Knowledge fails;
- the implementation adds generic filesystem, shell, network, process, or raw
  IPC authority;
- packaged acceptance touches a normal-profile Vault or AppData root; or
- regression, security-negative, installer, shutdown, or orphan checks fail.

## 4. User-initiated operational rollback

The primary runtime rollback is `Disconnect and forget source`. It must work even
when validation, the model, or the source is unavailable.

The sequence is:

1. close admission for new source operations;
2. increment the source generation;
3. cancel active scan/refresh/preview work and join it within exactly 5 seconds;
4. reject every result carrying the prior generation;
5. invalidate preview, `vault_revision`, and per-turn decision identities;
6. clear the in-memory index, excerpts, and source path;
7. remove Python-owned remembered consent;
8. set state to `NOT_CONFIGURED`;
9. keep ordinary chat available; and
10. verify the source was not modified.

If configuration removal fails, Project Knowledge remains disabled and reports a
sanitized `REVOCATION_INCOMPLETE` state. It must not resume source reads on the
next launch. The user receives bounded remediation guidance that never includes
the absolute source path.

Missing the 5-second join deadline has the same fail-closed result. The prior
generation remains permanently rejected, Project Knowledge remains disabled,
and operational rollback is incomplete until acceptance evidence proves no
source worker remains.

## 5. Source-code rollback for a future implementation

Source rollback must occur only on a clean, authorized feature branch. Use
reviewable revert commits in reverse dependency order:

1. production UI enablement and source-selection controls;
2. frontend bridge/store/type changes;
3. Tauri permissions and narrow Rust command changes;
4. Rust picker, opaque-handle, and path-boundary implementation;
5. Python production adapter, semantic consent persistence, and lifecycle
   integration;
6. implementation tests; and
7. implementation documentation, leaving this Phase B0 authority record unless
   the owner separately revokes it.

Do not restore the prior environment-variable-only prototype as a production
configuration path. A rolled-back build must truthfully show Project Knowledge
as unavailable and must ignore, without deleting, any later-version remembered
record it cannot safely interpret.

## 6. Persisted-state compatibility

Rollback must not require reading the selected source. The older application may
leave a later-version Python-owned semantic consent record untouched, but it
must not activate or display it as configured. Reinstalling a compatible future
build may offer to revalidate it only after confirming the record version and
consent.

Deleting a remembered consent record is authorized only by user revocation or a
separately approved migration. Under no condition may cleanup delete the source
directory or any descendant.

Frontend localStorage must never contain the absolute source path, so UI rollback
requires no path cleanup. Any discovery of such a value is a security incident:
disable Project Knowledge, preserve bounded evidence, and request explicit
remediation authority.

## 7. Package and installed-build rollback

Future packaged rollback must use an isolated application-data root and a
disposable fixture source. The sequence is:

1. record fixture and isolated-profile manifests without source content;
2. revoke Project Knowledge in the current build;
3. close LocalComet and prove no scan, sidecar, app, or model-runtime orphan;
4. uninstall through the canonical uninstaller without deleting user data;
5. install the last accepted package;
6. confirm Project Knowledge is unavailable and ordinary chat still works;
7. close normally and recheck process state; and
8. compare the fixture manifest byte-for-byte; and
9. use the required ProcMon or equivalent ETW process-tree audit to confirm no
   protected normal-profile Vault or AppData root was opened.

Installer rollback must preserve the existing unsigned-internal-build and
current-user boundaries. It must not introduce a network bootstrap, updater,
service, scheduled task, or data-deletion option.

## 8. Rollback acceptance evidence

Required evidence for a future implementation rollback:

- exact source commits and revert commits;
- changed-file list with no unrelated path;
- focused consent, containment, reparse, redaction, refresh, and revocation tests;
- complete supported frontend, Rust, Python, sidecar, and package checks;
- isolated fixture pre/post manifest showing zero mutation;
- isolated profile identity and a sanitized ProcMon or equivalent ETW
  process-tree report proving zero matching opens under protected normal-profile
  Vault and AppData roots;
- process inventory showing no orphan;
- `git diff --check`; and
- final clean worktree status.

The access audit must use the same process-tree, path-prefix, operation, capture-
interval, protected-path handling, and evidence-redaction rules defined by the
test and acceptance plan. If that audit is unavailable, rollback package
acceptance remains incomplete.

Evidence must exclude absolute personal paths, note bodies, prompts, secrets,
environment dumps, source copies, screenshots containing source content, and
model responses containing approved knowledge.

## 9. Stop conditions

Stop rollback and request owner direction if:

- the target commit or installed package cannot be identified exactly;
- the worktree contains unrelated changes that overlap rollback paths;
- rollback would require deleting or migrating user data;
- documentation rollback would require deleting a Phase B0 file without the
  owner's explicit named-file override;
- source preservation cannot be proven without accessing a non-isolated source;
- a remembered record requires an undecided schema/data-lifecycle migration; or
- the last accepted package cannot truthfully represent Project Knowledge as
  unavailable.

Rollback completion means the product no longer uses Project Knowledge, ordinary
local chat remains functional, the selected source is unchanged, no managed
process remains, and repository state is reviewable.
````

### ПУТЬ: docs/work-packages/phase-b0/PHASE-B0_PROJECT_KNOWLEDGE_SOURCE_AUTHORITY.md (376 строк, 17872 байт)

````markdown
# Phase B0 — Project Knowledge Source Authority

Status: `DOCUMENTATION_CONTRACT_ONLY`

Baseline tag: `v0.0.0-build-week-2026`

Baseline commit: `a9912ac4f4e95822962ca56a6da2fe7f1caf8fa4`

Phase B0 defines the authority boundary for a future production Project
Knowledge integration. It does not enable Project Knowledge, grant filesystem
authority to the current frontend, read a knowledge source, or authorize source
code, capability, packaging, AppData, Vault, or installed-application changes.

The words MUST, MUST NOT, SHOULD, and MAY are normative.

## 1. Objective

Permit a user to make one valid LocalComet Vault v2 root available as an
explicitly selected, read-only Project Knowledge source while preserving these
invariants:

- LocalComet never chooses a source implicitly.
- Selecting a source does not send its content to a model.
- Source content reaches a model only after an exact local preview and a
  separate per-turn user decision.
- Ordinary local chat remains available without Project Knowledge.
- The selected source is never modified by LocalComet.

The first supported source contract is the LocalComet Vault v2 contract enforced
by the validator at the Build Week baseline. A directory containing arbitrary
Markdown without the required Vault v2 schema is not a supported source.
Generic Markdown directories are deferred to a separate authority decision.

## 2. Authority granted by this contract

A later, separately authorized implementation MAY add a bounded production
source-selection flow that conforms to this document. That authority is limited
to one local Vault v2 source, read-only validation, in-memory indexing, bounded
retrieval, local preview, and exact per-turn inclusion.

This contract does not authorize:

- arbitrary frontend filesystem access or a generic path/handle command;
- selecting more than one source;
- automatic repository discovery or use of the application checkout;
- defaulting to, deriving, probing, or inspecting a repository or project root
  for Vault v2 validation;
- reading a project root referenced by note metadata;
- treating a generic Markdown directory as a supported source;
- writes, edits, synchronization, import, export, indexing databases, or lock files
  inside the selected source;
- network, cloud, connector, browser, email, shell, process, tool, telemetry, or
  publication authority;
- using Project Knowledge as long-term conversational memory;
- background ingestion before consent or after revocation;
- model training, fine-tuning, embeddings downloads, or remote vector services.

## 3. Source-selection flow

The initial production state MUST be `NOT_CONFIGURED` and Project Knowledge MUST
remain unavailable without a valid consent record.

The user selects a source through this future flow:

1. The user opens Settings → Project Knowledge and activates `Choose folder`.
2. Rust opens the native Windows directory picker. The frontend MUST NOT accept,
   construct, paste, or retain an absolute path.
3. Picker cancellation changes no state and performs no source scan.
4. Rust may inspect only the candidate's root type, root reparse status, fixed
   local-volume identity, and sanitized display name needed for the confirmation
   screen. This four-field allowance is exhaustive. It MUST NOT enumerate a
   descendant, inspect descendant metadata, open a source file, or read source
   content before source consent.
5. LocalComet shows a confirmation containing a sanitized folder display name,
   the read-only promise, supported content, scan limits, persistence choice,
   revocation behavior, and the statement that selection does not send content
   to a model.
6. The user explicitly activates `Use this folder read-only`. Merely choosing a
   folder in the native picker is not source consent.
7. Rust mediates the selected path and creates an opaque source handle. Python
   validates the boundary and Vault v2 contract and begins one bounded scan. The
   frontend receives only an opaque source ID, sanitized display name, state,
   counts, `vault_revision`, and safe findings.

The first implementation MUST support exactly one active source. Choosing a new
source requires a new confirmation and atomically revokes the old source before
the new scan begins. Failure of the new source MUST leave Project Knowledge
disabled; it MUST NOT silently reactivate the old source.

## 4. Consent model

Project Knowledge has two independent consent gates.

### 4.1 Source consent

Source consent authorizes LocalComet to enumerate, validate, and read bounded
supported files beneath the exact selected root. It does not authorize model
inclusion, writes, external project reads, or network use.

Vault v2 `source_paths` values are inert provenance in the first implementation.
LocalComet MUST NOT resolve, stat, open, or otherwise inspect them against a
repository or project root. Project-root consent is a separate authority that is
not granted by Phase B0; unless a later contract and a separate explicit user
consent grant it, external `source_paths` remain inert.

The confirmation MUST identify whether consent is:

- `THIS_SESSION_ONLY` — the default; held in process memory and discarded at
  normal shutdown, crash recovery, or application restart; or
- `REMEMBER_SOURCE` — an explicit additional choice that permits the trusted
  Python semantic backend to persist the canonical source identity for later
  sessions.

No remembered-source field may be stored in browser localStorage. Remembered
consent MUST NOT weaken the separate per-turn inclusion gate. Rust owns native
picker and path mediation and issues opaque source handles; Rust does not own or
persist semantic source consent.

### 4.2 Per-turn inclusion consent

For every turn that requests Project Knowledge, LocalComet MUST prepare a bounded
preview before a model call. The preview MUST show the exact context text,
relative provenance, source count, `vault_revision`, truncation state, and an
immutable preview digest.

The user must choose exactly one action:

- `INCLUDE_AND_SEND` — send the exact approved preview with the turn;
- `REJECT_AND_SEND_WITHOUT_KNOWLEDGE` — send the turn without source content; or
- `CANCEL` — cancel the turn without a model call.

There is no remembered per-turn approval, bulk approval, implied approval,
approval by chat text, or automatic include mode in the first implementation.

These two Project Knowledge consent gates are distinct from Knowledge Change
Review and Review Center decisions. A Review Center decision does not create
source consent, remembered consent, filesystem authority, or per-turn inclusion
consent, and none of those authorities may be inferred from review approval.

## 5. Revocation

Settings MUST provide `Disconnect and forget source` whenever a source is active
or remembered. Revocation MUST be explicit, idempotent, and available without a
working model.

On revocation, LocalComet MUST:

1. stop admitting new scans, refreshes, previews, and inclusion decisions;
2. increment the source generation, cancel active source work, and join it within
   exactly 5 seconds;
3. invalidate pending previews and `vault_revision` identities;
4. clear the in-memory index, excerpts, decisions, and source path;
5. remove any Python-owned remembered-source record;
6. emit only a sanitized terminal state; and
7. leave every source file and directory unchanged.

Every scan, refresh, preview, and result MUST carry the generation captured when
the operation was admitted. A result is accepted only when its generation still
equals the active consent generation. Closing admission and incrementing the
generation occur before cancellation. Any result delivered afterward is
discarded without changing state, even if the underlying operation reports
success. Failure to join within 5 seconds is `REVOCATION_INCOMPLETE`, leaves
Project Knowledge disabled, and is an acceptance failure; it never permits a
late result to become active.

Revocation cannot retract context already delivered to a running or completed
local model turn. The UI MUST state this before confirming revocation when such a
turn exists. After revocation, no retry may reuse the prior context.

## 6. Read-only filesystem boundary

The selected source MUST be one existing absolute directory on a fixed local
volume. The following candidates MUST be rejected:

- relative, empty, drive-relative, device, UNC, network-share, or URL forms;
- a volume root, user-profile root, Windows directory, Program Files root,
  temporary-directory root, LocalComet install directory, or LocalComet AppData
  root;
- a file instead of a directory;
- a root that is itself a symlink, junction, mount-point redirection, or other
  reparse point; and
- a root whose ancestor chain cannot be validated without crossing a reparse
  point.

All reads MUST remain beneath the canonical selected root. The application MUST
use directory enumeration and file-open operations that do not follow links.
Absolute paths MUST stay inside trusted backend memory. The frontend and model
may receive only relative paths proven to remain within the source.

The selected directory MUST satisfy the LocalComet Vault v2 schema enforced by
the validator at baseline commit
`a9912ac4f4e95822962ca56a6da2fe7f1caf8fa4`. Indexable content is limited to
regular Markdown files with the `.md` extension.

The only auxiliary file contents authorized for structural validation are:

- regular `*.base` files beneath the selected root; and
- `00 Канон/LocalComet — Архитектурная карта.canvas`.

Regular `.obsidian/*.json` entries may be counted and inspected as directory
metadata, but their contents MUST NOT be opened or read. Auxiliary content MUST
NOT enter retrieval results or model context. Expanding the Vault version,
supported extensions, auxiliary paths, or auxiliary content rules requires a
new authority decision.

LocalComet MUST NOT create, write, append, truncate, rename, move, delete, copy,
touch, lock, chmod, set attributes, set extended metadata, or repair anything in
the source. Validation errors are reported; they are never fixed automatically.

## 7. Symlink, reparse-point, and race protection

The root, every traversed directory, every candidate file, and every referenced
relative component MUST be inspected without following links. Every symlink,
junction, mount point, reparse point of any tag, and cloud placeholder within the
traversed source is a hard failure for that scan. The first implementation has no
safe-reparse or safe-cloud-placeholder exception.

For each file, LocalComet MUST:

1. validate the parent chain beneath the canonical root;
2. inspect the entry without following links;
3. open it in no-follow/read-only mode;
4. verify after opening that type, identity, and containment still match; and
5. reject the complete candidate index on any time-of-check/time-of-use change.

No partial index may become active. A path that disappears, changes identity,
changes type, or becomes a reparse point during a scan is a safe refresh failure.
If the platform cannot provide no-follow open and post-open type, identity, and
containment verification, LocalComet MUST reject the scan. Following the path or
using a weaker check is not an allowed fallback.

The current KnowledgeAdapter and Vault v2 validator use path-based reads and do
not yet satisfy this handle-level rule. They are not production-conforming and
MUST NOT be wired to a production source until a separately authorized
implementation hardens them and passes the required tests.

## 8. Persistence and lifecycle

The outer source-selection lifecycle is:

```text
NOT_CONFIGURED → AWAITING_CONFIRMATION → VALIDATING → READY
READY → REFRESHING → READY
READY|REFRESHING|ERROR|DEGRADED → REVOKING → NOT_CONFIGURED
AWAITING_CONFIRMATION|VALIDATING|REFRESHING → ERROR
```

This outer lifecycle does not rename the existing Python `AdapterState`
contract. Its projection is:

| Outer source state | Existing `AdapterState` projection |
|---|---|
| `NOT_CONFIGURED` | `NOT_CONFIGURED` |
| `AWAITING_CONFIRMATION` | `NOT_CONFIGURED` (adapter not admitted) |
| `VALIDATING` | `SCANNING` |
| `READY` | `READY` |
| `REFRESHING` | `SCANNING` |
| `DEGRADED` | `DEGRADED` |
| `ERROR` | `ERROR` |
| `REVOKING` | `NOT_CONFIGURED` (new adapter work not admitted) |

`vault_revision` remains the existing Python and desktop wire field. The phrase
"source revision" is descriptive prose only and MUST NOT rename that field.

`THIS_SESSION_ONLY` stores the path, index, and consent only in trusted process
memory. `REMEMBER_SOURCE` MAY persist only the minimum Python-owned semantic
record: contract version, canonical path, opaque source ID, sanitized display
name, consent timestamp, and last validated `vault_revision`. It MUST NOT persist
note text, excerpts, prompts, previews, or absolute paths in frontend storage.
Rust may reconstruct and validate an opaque source handle from the Python-owned
record but MUST NOT persist a second semantic consent record.

A remembered source MAY be validated at application startup because the user
explicitly chose persistence. Startup failure MUST leave chat usable and Project
Knowledge unavailable. It MUST NOT retry indefinitely or block application
readiness beyond the 30-second scan budget. Startup cancellation and revocation
remain subject to the exact 5-second join deadline.

The in-memory index is replaced atomically only after a complete successful
validation. Shutdown clears all session-only state. Crash recovery treats any
unfinished scan or preview as invalid.

## 9. Scan limits

The first implementation MUST enforce limits no greater than:

| Resource | Hard limit |
|---|---:|
| Active sources | 1 |
| Traversal depth below source root | 32 directories |
| Inspected filesystem entries | 10,000 |
| Markdown notes | 2,000 |
| Bytes per Markdown note | 1,048,576 |
| Aggregate Markdown plus auxiliary content bytes read per scan | 67,108,864 |
| Bytes per permitted auxiliary file | 1,048,576 |
| Query characters | 4,096 |
| Results exposed to desktop preview | 8 |
| Selected sections per note | 3 |
| Characters per excerpt | 1,200 |
| Total preview context characters | 12,000 |
| One scan or refresh wall-clock budget | 30 seconds |

Lower operational defaults are allowed. Raising a hard limit requires a reviewed
contract change and corresponding denial tests.

The aggregate byte counter MUST include every Markdown, `*.base`, and authorized
canvas content byte read. Before each content open, the candidate's size MUST be
checked against the remaining aggregate budget. Metadata inspection does not
authorize opening unlisted auxiliary content.

## 10. Refresh and freshness rules

There is no continuous watcher, periodic scan, launch-time download, or hidden
background refresh. Refresh occurs only:

- immediately after confirmed source selection;
- at startup for an explicitly remembered source;
- when the user activates `Refresh`; or
- as a bounded freshness check before an approved preview is injected.

Every successful scan produces a deterministic `vault_revision`. A preview is
bound to the source ID, `vault_revision`, turn ID, selected content hashes, and
preview digest. If any identity or the active source generation changes before
inclusion, LocalComet MUST reject the decision, invalidate the preview, and
require a fresh preview.

A failed refresh MUST NOT activate a partial candidate. The previous validated
index MAY remain in memory for diagnostics, but it is `DEGRADED` and MUST NOT be
used for a new preview until a complete refresh succeeds.

## 11. Redaction and failure behavior

Logs, IPC errors, telemetry, and diagnostics MUST NOT contain absolute paths,
source text, note bodies, excerpts, prompts, secrets, credentials, environment
variables, or raw exception representations.

Safe diagnostics MAY contain bounded error codes, operation state, elapsed time,
counts, byte totals, relative paths when needed for user remediation, and
cryptographic digests. A displayed relative path MUST first pass containment and
control-character validation.

Secret-like content detected by the approved validator MUST be reported as a
redacted blocking finding. The matching secret value MUST NOT be repeated in the
UI or logs. Raw source content appears only in the local preview required for
per-turn consent.

All boundary, validation, timeout, cancellation, stale-revision, and malformed
content failures are fail-closed:

- no source content is sent to a model;
- no partial index becomes active;
- no automatic fallback silently sends a knowledge-enabled turn;
- ordinary chat remains available through an explicit send-without-knowledge
  path; and
- the source remains unchanged.

## 12. Data ownership and deletion

The user owns the selected source. LocalComet owns only its Python-owned semantic
consent record, opaque identifiers, in-memory index, and sanitized diagnostics.
Revocation may delete LocalComet-owned configuration and volatile state but MUST
NOT delete or modify source content.

Normal application uninstall continues to preserve user-owned data under the
existing installer contract. Any future UI for deleting remembered Project
Knowledge configuration requires an explicit, separate user action and may not
be coupled to source deletion.

## 13. Phase B0 completion boundary

Phase B0 is complete when this authority contract, its threat model, test and
acceptance plan, and rollback plan are internally consistent and pass repository
documentation checks. Completion does not make Project Knowledge available in
the installed product, reopen Phase A, or supersede the existing OR-01
prohibition on Vault access, new IPC/capabilities, or implementation work. Any
future code or capability work still requires separate owner authorization.
````

### ПУТЬ: docs/work-packages/phase-b0/PHASE-B0_PROJECT_KNOWLEDGE_TEST_AND_ACCEPTANCE_PLAN.md (353 строк, 16846 байт)

````markdown
# Phase B0 — Project Knowledge Test and Acceptance Plan

Status: `DOCUMENTATION_CONTRACT_ONLY`

This plan separates Phase B0 documentation acceptance from the mandatory gates
for a later, separately authorized implementation. Passing Phase B0 does not
enable Project Knowledge.

## 1. Phase B0 preconditions

- Repository root is `C:\Users\DNS\Documents\LocalComet-build-week-clean`.
- Branch is `continue/after-build-week-2026`.
- Baseline is tag `v0.0.0-build-week-2026` at commit
  `a9912ac4f4e95822962ca56a6da2fe7f1caf8fa4`.
- Worktree and index are clean before the documentation change.
- No source code, capabilities, packaging, Vault, AppData, or installed
  application is accessed or modified.

## 2. Phase B0 documentation scope

The only expected additions are:

```text
docs/work-packages/phase-b0/PHASE-B0_PROJECT_KNOWLEDGE_SOURCE_AUTHORITY.md
docs/work-packages/phase-b0/PHASE-B0_PROJECT_KNOWLEDGE_THREAT_MODEL.md
docs/work-packages/phase-b0/PHASE-B0_PROJECT_KNOWLEDGE_TEST_AND_ACCEPTANCE_PLAN.md
docs/work-packages/phase-b0/PHASE-B0_PROJECT_KNOWLEDGE_ROLLBACK.md
```

Phase B0 acceptance requires:

1. The authority document defines selection, consent, revocation, read-only
   boundaries, reparse protection, persistence, lifecycle, limits, refresh,
   redaction, and failure behavior.
2. The threat model identifies assets, trust boundaries, invariants, threats,
   mitigations, and residual risk.
3. This plan defines positive, negative, regression, packaged, and rollback
   acceptance for later implementation.
4. The rollback plan preserves the source and separates documentation rollback
   from future feature rollback.
5. The four documents do not claim that Project Knowledge is production-ready.

## 3. Phase B0 repository checks

Run from the repository root:

```powershell
$phaseB0Docs = @(
  'docs/work-packages/phase-b0/PHASE-B0_PROJECT_KNOWLEDGE_SOURCE_AUTHORITY.md',
  'docs/work-packages/phase-b0/PHASE-B0_PROJECT_KNOWLEDGE_THREAT_MODEL.md',
  'docs/work-packages/phase-b0/PHASE-B0_PROJECT_KNOWLEDGE_TEST_AND_ACCEPTANCE_PLAN.md',
  'docs/work-packages/phase-b0/PHASE-B0_PROJECT_KNOWLEDGE_ROLLBACK.md'
)
$documentCheckFailed = $false
foreach ($document in $phaseB0Docs) {
  $resolvedDocument = (Resolve-Path -LiteralPath $document).Path
  $documentLines = [System.IO.File]::ReadAllLines($resolvedDocument)
  for ($lineIndex = 0; $lineIndex -lt $documentLines.Length; $lineIndex++) {
    if ($documentLines[$lineIndex] -match '[ \t]+$') {
      Write-Error "${document}:$($lineIndex + 1): trailing whitespace"
      $documentCheckFailed = $true
    }
  }
  $documentBytes = [System.IO.File]::ReadAllBytes($resolvedDocument)
  if ($documentBytes.Length -eq 0 -or $documentBytes[-1] -ne 10) {
    Write-Error "${document}: missing final newline"
    $documentCheckFailed = $true
  }
}
if ($documentCheckFailed) { throw 'Phase B0 document check failed' }
git diff --check
git --no-pager diff --name-status
git --no-pager status --short --untracked-files=all
```

Because `git diff --check` does not inspect untracked files, the explicit
four-file check above is mandatory while the documents are untracked. After the
files are staged by an authorized later action, also run:

```powershell
git diff --cached --check
```

Expected result:

- The explicit four-file check reports no trailing whitespace and confirms a
  final LF byte in every document.
- `git diff --check` exits `0` with no output.
- After staging, `git diff --cached --check` exits `0` with no output.
- Exactly the four Phase B0 Markdown files are untracked or changed.
- No staged change, deletion, source file, generated artifact, or unrelated path
  is present.

No Python compilation, npm, Cargo, installer, stability, UI automation, or
installed-application test is required for the documentation-only change.

## 4. Future implementation test environment

All filesystem tests MUST use fresh disposable synthetic fixtures. The positive
source fixture MUST be a valid LocalComet Vault v2 root. Tests MUST set
test-specific source, protected-project, configuration, and application-data
roots. They
MUST NOT read or write:

- a real Obsidian Vault;
- the normal LocalComet AppData root;
- the installed LocalComet application;
- `Projects/BrowserProfile`;
- `C:\Users\DNS\Documents\LocalAgent`; or
- any source directory not created by the test itself.

Tests must disable bytecode and other repository-local caches where applicable.
Generated frontend, Rust, and installer validation belongs in an ignored or
external clean-room workspace.

## 5. Source-selection and consent tests

Automated and component tests must prove:

- initial state is `NOT_CONFIGURED`;
- only an explicit native-picker action starts selection;
- cancelling the picker causes no read and no state change;
- before confirmation, Rust inspects only root type, root reparse status, fixed
  local-volume identity, and sanitized display name;
- descendant entries, descendant metadata, and source contents are not read
  before confirmation;
- the confirmation shows the read-only boundary, limits, persistence choice,
  revocation behavior, and no-model-send statement;
- only `Use this folder read-only` creates source consent;
- `THIS_SESSION_ONLY` is the default;
- `REMEMBER_SOURCE` requires an additional explicit choice;
- choosing a second source atomically revokes the first;
- frontend payloads cannot supply or recover an absolute path; and
- malformed, unknown, duplicate, or replayed consent requests fail closed;
- a Review Center decision cannot create source consent, remembered consent,
  filesystem authority, or per-turn inclusion consent; and
- no repository, application checkout, environment path, or project root is
  inferred or inspected when no source has been explicitly selected.

## 6. Read-only and containment tests

Positive fixtures must cover a disposable valid LocalComet Vault v2 root and
deterministic `vault_revision` generation. A generic Markdown-only directory
without the required Vault v2 schema is an unsupported negative fixture, not a
positive source.

Negative fixtures must cover:

- empty, relative, drive-relative, UNC, URL, device, and file paths;
- volume root, user-profile root, AppData root, install root, and temporary root;
- root symlink, root junction, ancestor reparse point, nested directory link,
  file link, mount point, cloud reparse placeholder, and unknown reparse tag;
- `..`, mixed-separator traversal, case-fold collision, Unicode normalization
  collision, reserved Windows names, alternate data streams, and control chars;
- a file replaced, renamed, deleted, resized, or converted to a link during read;
- a path resolving outside the root after validation; and
- unsupported regular files and non-regular filesystem entries.

Every reparse tag and every cloud placeholder MUST be rejected; tests must not
define a safe-tag exception. A native integration test must also force the
no-follow-open or post-open identity primitive to be unavailable and prove that
the scan fails closed rather than falling back to a path-based read.

Vault v2 notes containing external `source_paths` must be tested with a protected
synthetic project root and with the application checkout as a sentinel. Without
a separate project-root authority and explicit consent, the values remain inert:
no resolve, stat, directory enumeration, or file open may target either root.
The production test must prove there is no implicit repository-root fallback.

For every case, assert no content escapes the root, no partial index activates,
no source entry changes, and the returned error is sanitized.

Read-only tests must snapshot fixture names, bytes, SHA-256 values, attributes,
and write timestamps before and after selection, scan, preview, refresh,
cancellation, revocation, restart, and shutdown. Any LocalComet-created file or
content/attribute/write-time change is a failure. Operating-system access-time
behavior is recorded separately and is not represented as a LocalComet write.

## 7. Limit and resource tests

Test the exact boundary and first rejected value for:

- traversal depth `32` / `33`;
- filesystem entries `10,000` / `10,001`;
- Markdown notes `2,000` / `2,001`;
- note bytes `1,048,576` / `1,048,577`;
- aggregate Markdown plus authorized auxiliary content bytes `67,108,864` /
  `67,108,865`;
- auxiliary bytes `1,048,576` / `1,048,577`;
- query characters `4,096` / `4,097`;
- desktop results `8` / `9`;
- selected sections `3` / `4`;
- excerpt characters `1,200` / `1,201`;
- preview context characters `12,000` / `12,001`; and
- scan wall time within / beyond `30` seconds.

Also test cancellation during enumeration, hashing, validation, retrieval, and
refresh; repeated refresh requests; one-active-operation enforcement; bounded
memory/event output; and absence of orphan workers after cancellation.

Aggregate-byte fixtures MUST combine Markdown, regular `*.base`, and the single
authorized `00 Канон/LocalComet — Архитектурная карта.canvas` content. They must
prove that every content byte is charged before the open and that
`.obsidian/*.json` content is never opened. No other auxiliary content is
authorized.

Cancellation tests MUST close admission and increment the source generation
before signalling cancellation, join active work within exactly 5 seconds, and
reject every result carrying the prior generation. A deterministic blocking
fixture must prove that a result arriving after cancellation cannot activate an
index or preview. Missing the 5-second join deadline is an acceptance failure.

## 8. Refresh, revision, and preview tests

Tests must prove:

- the first complete scan atomically activates one index;
- identical bytes produce the same deterministic `vault_revision`;
- a successful changed scan atomically replaces the old index;
- a failed scan activates no candidate and marks the old state `DEGRADED`;
- `DEGRADED` state cannot prepare a new preview;
- preview content is bounded and includes relative provenance and truncation;
- preview identity binds source ID, source generation, `vault_revision`, turn ID,
  selected content hashes, and preview digest;
- any source change between preview and decision invalidates the decision;
- an approval cannot be replayed for another turn, preview, source, or
  `vault_revision`;
- `REJECT_AND_SEND_WITHOUT_KNOWLEDGE` contains no source text;
- `CANCEL` causes no model call; and
- retry after revocation contains no prior context.

## 9. Persistence and revocation tests

For `THIS_SESSION_ONLY`, verify no source record is written and restart returns to
`NOT_CONFIGURED`.

For `REMEMBER_SOURCE`, verify only the approved versioned semantic metadata is
stored by Python, Rust stores no duplicate semantic consent, no note or preview
content is stored, and no absolute path appears in frontend storage. Invalid,
truncated, unknown-version, or tampered records must fail closed.

Revocation tests must prove admission closes and generation increments before
cancellation, active work is joined within exactly 5 seconds, prior-generation
results are discarded, pending previews become invalid, Python-owned consent is
removed, volatile content is cleared, the operation is idempotent, and the
source remains byte-identical.

Crash and abnormal-exit tests must prove unfinished scans and approvals are not
recovered as valid.

## 10. Redaction and failure tests

Inject synthetic absolute paths, usernames, API keys, Bearer [REDACTED: secret in docs/work-packages/phase-b0/PHASE-B0_PROJECT_KNOWLEDGE_TEST_AND_ACCEPTANCE_PLAN.md:253] private
keys, credentials, environment values, malformed Unicode, long exception text,
and source excerpts into every failure layer.

Assert that logs, Rust errors, Python errors, events, diagnostics, and frontend
state contain only stable codes and approved bounded fields. Raw exception repr,
source body, prompt, secret value, and absolute path must be absent.

Secret-like content must block the affected scan or preview without repeating
the value. Failure must leave ordinary chat usable and must never silently send
the turn with knowledge.

## 11. Capability-negative tests

Repository, generated capability, and packaged scans must prove that the
implementation adds no:

- generic filesystem, shell, process, environment, URL, HTTP, or raw IPC command;
- frontend-supplied path, executable, argument, hash, or approval identity;
- source write, repair, sync, migration, export, deletion, or watcher;
- network share, remote knowledge source, cloud embedding, telemetry, or update;
- automatic knowledge inclusion or remembered turn approval;
- generic Markdown source support, implicit repository/project-root discovery,
  or resolution of inert external `source_paths`;
- use of a Review Center decision as consent or filesystem authority;
- tool, browser, computer-use, email, connector, or publication authority; or
- change to the existing model/artifact trust contract unrelated to Project
  Knowledge.

## 12. Regression gates for a future code change

After focused tests pass, run the repository-supported affected Python suites,
changed-file compilation, complete frontend tests/check/build, Rust formatting,
locked/offline Cargo check, warnings-denied Clippy, Rust tests, sidecar contract
checks, package-source verification, and the normal clean-room offline NSIS
build.

The current KnowledgeAdapter and Vault v2 validator are not production-
conforming until a separately authorized change replaces path-based reads with
mandatory no-follow opens and post-open type, identity, and containment
verification. Regression gates cannot waive this requirement.

The existing local-model lifecycle must still pass: approved acquisition,
connect, real text response, Stop, Retry, disconnect, clean shutdown, and no
managed orphan. Ordinary chat with Project Knowledge unavailable, rejected, or
revoked must remain functional.

`stability test` is required after an important Python implementation change,
with any generated reports kept outside the committed source set.

## 13. Packaged acceptance for a future implementation

Use a disposable valid LocalComet Vault v2 fixture source and isolated
application-data root. Verify:

1. fresh install starts with Project Knowledge unavailable;
2. native selection and confirmation work without exposing an absolute path;
3. a valid source becomes ready and produces a local preview;
4. reject sends an ordinary turn with zero knowledge bytes;
5. include sends the exact preview and produces one local response;
6. modifying the fixture after preview forces a refresh;
7. revocation stops future use and preserves the fixture byte-for-byte;
8. remembered versus session-only behavior survives restart exactly as defined;
9. malformed/reparse/oversized fixtures fail safely;
10. normal closure leaves no app, sidecar, model-runtime, or scan worker orphan;
11. uninstall and reinstall do not modify the fixture; and
12. no protected normal-profile Vault or AppData root is opened by the LocalComet
    process tree.

Record process identity, isolated roots, exact fixture manifest, commands, exit
codes, UTC times, and sanitized results. Do not record source content, prompts,
personal paths, or credentials.

Item 12 requires a Windows filesystem-access audit. Start ProcMon capture before
launch and filter to the complete LocalComet process tree, including the desktop
process, Python sidecar, model runtime, and scan workers. Filter filesystem
events whose path begins with either the predeclared normal-profile LocalComet
AppData root or the predeclared real-Vault root. At minimum include open,
`CreateFile`, directory-query, read, write, rename, delete, and metadata-change
operations. An ETW Kernel-File capture with equivalent PID-tree and path-prefix
correlation is an acceptable substitute.

The protected path strings are supplied to the local audit filter without
probing their existence or contents. Audit output is written only to the
isolated clean-room evidence root. Acceptance requires zero matching LocalComet
process-tree events; audit-tool self-events are excluded by process identity. A
sanitized published summary records hashes or labels for protected roots, event
filters, capture interval, process tree, and zero-event result, never the
personal path strings. If ProcMon or equivalent ETW evidence is unavailable,
item 12 is unproven and packaged acceptance is blocked.

## 14. Acceptance decision

Phase B0 documentation passes when Section 3 passes and the four documents cover
all requested authority topics without changing product behavior.

A future implementation passes only when Sections 4–13 pass with zero
unexplained failure, zero source mutation, zero authority expansion, and a clean
worktree. Any missing owner decision, unsafe path behavior, unredacted content,
stale-preview acceptance, source mutation, or incomplete packaged evidence is a
release blocker.
````

### ПУТЬ: docs/work-packages/phase-b0/PHASE-B0_PROJECT_KNOWLEDGE_THREAT_MODEL.md (174 строк, 10989 байт)

````markdown
# Phase B0 — Project Knowledge Threat Model

Status: `DOCUMENTATION_CONTRACT_ONLY`

This threat model is subordinate to
`PHASE-B0_PROJECT_KNOWLEDGE_SOURCE_AUTHORITY.md`. It defines the security
conditions a later Project Knowledge implementation must satisfy. Phase B0 does
not access a knowledge source or modify product code.

## 1. Protected assets

- confidentiality and integrity of the user-selected source;
- user control over source selection, persistence, refresh, inclusion, and
  revocation;
- integrity of `vault_revision`, source generation, preview, and per-turn
  decision;
- confidentiality of absolute paths, note content, prompts, and credentials;
- LocalComet's frontend/Rust/Python trust boundary;
- availability of ordinary local chat when Project Knowledge fails; and
- the prohibition on source writes and unauthorized external access.

## 2. Trust boundaries

### Svelte frontend

The frontend is untrusted for filesystem authorization. It may request the fixed
selection flow and render sanitized state, but it must not receive absolute
paths, manufacture consent, choose backend paths, or alter preview identities.

### Rust desktop boundary

Rust owns the native picker, path mediation, opaque source handles, path
containment enforcement, process lifecycle, and narrow Tauri commands. Rust does
not own or persist semantic source consent. It must expose no generic filesystem,
shell, process, environment, or raw IPC authority.

### Python sidecar

Python owns deterministic Vault v2 validation, indexing, retrieval,
`vault_revision`, preview construction, semantic state, semantic consent
persistence, and fail-closed errors. It receives a Rust-mediated opaque source
handle through a fixed internal contract, not a path from frontend-controlled
payload text.

### Local model runtime

The model is not trusted to authorize reads or request additional source data.
It receives only the exact preview approved for one turn and cannot browse the
source, resolve paths, call tools, or persist approval.

### Selected source

The first supported source is one valid LocalComet Vault v2 root. Generic
Markdown directories are unsupported. All source names, metadata, frontmatter,
links, and content are untrusted. Local ownership of a file does not make its
contents safe instructions. External `source_paths` are inert provenance unless
a later authority contract and separate explicit project-root consent permit
otherwise.

## 3. Security invariants

1. Before explicit source consent, Rust may inspect only root type, root reparse
   status, fixed local-volume identity, and sanitized display name; no descendant
   is enumerated and no source file content is read.
2. No source content reaches a model before exact per-turn approval.
3. No LocalComet operation writes to the selected source.
4. No accepted path crosses the canonical root or any reparse or cloud-placeholder
   boundary.
5. No failed, partial, stale, or cancelled scan becomes active.
6. No stale or altered preview can be approved.
7. No source error blocks ordinary chat.
8. No absolute path or secret appears in frontend payloads or diagnostics.
9. Revocation stops future source use and clears LocalComet-owned volatile state.
10. Neither source selection nor content expands model, tool, network, or shell
    authority.
11. No repository or project root is inferred, defaulted, resolved, or inspected
    for Vault validation or for an external `source_paths` value.
12. Knowledge Change Review and Review Center decisions grant no source consent,
    remembered consent, filesystem authority, or per-turn inclusion consent.

## 4. Threats and required mitigations

| Threat | Example | Required mitigation | Failure result |
|---|---|---|---|
| Implicit source selection | App guesses a repository, project root, or environment path | Native picker plus separate confirmation; no default/fallback path; default `NOT_CONFIGURED` | No scan |
| Consent confusion | Folder-picker confirmation is treated as full consent | Dedicated `Use this folder read-only` action and separate persistence choice | Candidate discarded |
| Silent model inclusion | Selected notes are appended automatically | Exact local preview and per-turn decision bound to preview hash | Turn waits or sends without knowledge only by explicit choice |
| Path traversal | `..`, absolute path, device path, crafted separator | Canonical parsing, component validation, relative provenance only | Reject source or result |
| Symlink/junction/cloud escape | Any reparse point, known tag, cloud placeholder, or nested junction | Reject every reparse/cloud entry; mandatory no-follow open and post-open verification; no weaker fallback | Reject complete scan |
| TOCTOU replacement | File changes between validation and read | Revalidate type, identity, and containment after no-follow open; `vault_revision`-bound index | Reject candidate index |
| Directory or file bomb | Deep tree, many entries, huge notes or auxiliary files | Depth, entry, note, aggregate Markdown-plus-auxiliary byte, time, and result limits | Bounded error, no partial index |
| Malformed content | Invalid UTF-8, duplicate metadata, control characters | Strict decoding and deterministic schema validation | Reject affected scan safely |
| Prompt injection in notes | Note asks model to ignore policy or use tools | Treat context as quoted untrusted data; no tool capability; fixed system boundary | Model gets no new authority |
| Secret disclosure | API key or private key appears in a note | Blocking secret scan, redacted finding, no raw secret in logs | Preview/inclusion denied |
| Absolute-path disclosure | Exception embeds user directory | Stable safe errors, relative validated paths only | Redacted error |
| Stale preview | Source changes after user reviews content | Source generation, `vault_revision`, content hashes, turn ID, and preview digest checked at inclusion | Require new preview |
| Approval replay | Old approval is reused for another turn | Single-turn immutable identity; terminal decisions are non-reusable | Reject decision |
| Frontend forgery | Compromised UI submits a path or altered preview | Rust/Python recompute authority and identities; narrow typed commands | Reject request |
| Persistence leak | Absolute source path stored in localStorage or semantic consent duplicated in Rust | Python-owned semantic persistence only; Rust path mediation only; no frontend path storage | Configuration error |
| Revocation race | Scan completes while user revokes | Close admission, increment generation, cancel and join within 5 seconds, reject every stale-generation result | Discard late result; release block if join misses deadline |
| Refresh failure reuse | Old index is silently used after a failed refresh | Mark `DEGRADED`; prohibit new previews until successful refresh | Knowledge unavailable |
| Network-share substitution | UNC target changes remotely | First implementation accepts fixed local volumes only | Reject selection |
| Unsupported file smuggling | Binary renamed or embedded in auxiliary file | Vault v2 schema plus the pinned `*.base` and declared-canvas allowlist, regular-file, size, decoding, and aggregate-byte checks | Reject scan |
| Resource starvation | Repeated refreshes or previews overlap | One active source operation, bounded queue, idempotent cancellation | Busy or cancelled state |
| Log exfiltration | Content appears in tracebacks or crash logs | No raw exception serialization; bounded codes and sanitized fields | Safe terminal error |
| Source mutation | Indexer creates cache, lock, or repair files | Read-only handles and no write-capable code path | Security failure and rollback trigger |

## 5. Prompt-injection boundary

Retrieved knowledge is evidence, not instruction authority. The future model
request MUST clearly delimit context from system and user instructions. Content
inside notes cannot:

- approve an action;
- change LocalComet policy or capability state;
- request more files;
- enable tools, browsing, shell, or network access;
- override the user's inclusion decision; or
- suppress provenance and truncation disclosure.

The first Project Knowledge release remains text-only and tool-free. Treating
context as untrusted does not guarantee model compliance, so the absence of tool
and filesystem capability is a required defense, not an optional prompt rule.

## 6. Persistence threats

Remembered consent increases path-disclosure and unintended-startup-read risk.
Therefore persistence is opt-in, Python-owned, minimal, versioned, and
revocable. Rust may reconstruct an opaque source handle but may not persist a
second semantic consent record. The application must not persist note contents
or previews. A record with an unknown version, invalid path, changed root
identity, or missing consent fields fails closed as `NOT_CONFIGURED` or `ERROR`;
it is never repaired by guessing.

Crash recovery must invalidate unfinished operations and approvals. Temporary
index data, if a later design persists any, requires a separate authority
decision and is not authorized by Phase B0.

## 7. Failure and abuse handling

Security failures have bounded stable codes and sanitized explanations. Repeated
failures may apply an in-memory backoff, but they may not create a scheduled
task, service, telemetry event, or permanent lockout. The user can always revoke
the source and continue ordinary chat.

The application must not offer automatic repair, quarantine, deletion, rename,
permission changes, or source migration. Remediation guidance may identify a
validated relative path and issue class without reproducing sensitive content.

## 8. Residual risks

- Reading files may cause operating-system access-time or security-product
  activity even though LocalComet performs no write.
- A local model may repeat approved sensitive context in its response.
- A user can intentionally approve confidential material for a local model turn.
- A fixed local volume can fail or be externally modified during a scan.
- Sanitized folder display names may still be personally identifying; the UI
  should allow a generic label.

These residual risks must be disclosed in acceptance evidence. They do not
permit weakening consent, containment, redaction, or no-write requirements.

## 9. Threat-model acceptance

The later implementation is acceptable only if automated negative tests cover
every invariant and every table row that can be exercised synthetically, and a
packaged test proves selection, preview, rejection, inclusion, refresh,
revocation, restart, and clean shutdown using a disposable valid Vault v2
fixture source. The current path-based KnowledgeAdapter is not production-
conforming until mandatory no-follow open and post-open identity verification
are implemented and accepted under separate authority.

Testing must never use the user's real Obsidian Vault, normal AppData profile,
installed production model data, or historical repository.
````

### ПУТЬ: docs/work-packages/up00/UP00-WP01_PR_BODY.md (96 строк, 7032 байт)

````markdown
# UP00-WP01 — Windows one-click launch and installer baseline

> Draft prepared locally for human review. Do not push or create a remote pull request from this work package.

## Purpose

Package LocalComet as a per-user Windows desktop application that starts its existing managed backend automatically, waits for bounded readiness, handles duplicate launch safely, and shuts down without orphan processes.

## User-visible result

After one NSIS installation, the user starts `LocalComet` from the Start Menu or desktop. No terminal, repository checkout, Python, Node.js, npm, Cargo, Vite, or Tauri CLI is needed for installed launch.

## Exact scope

- Prospective governance/owner-decision records for this work package.
- Existing-sidecar runtime packaging and Windows NSIS configuration.
- Main/child no-console behavior.
- Bounded startup readiness, native startup failure, single-instance behavior, and process shutdown.
- Installer, shortcut, lifecycle, uninstall, negative-authority, and rollback verification.

## Exclusions

No IPC/schema/data-lifecycle redesign, UI redesign, model manager, Review Center, Prompt Studio, autonomous tasks, publication, approval mutation, Vault action, telemetry, updater, signing infrastructure, broad dependency upgrade, or UP01-UP10 implementation.

## Architecture decisions used

- `OR-01` prospective Architecture Governance Pack/Constitution ratification.
- Source Mapping `COMPLETED_AND_REMEDIATED` at `6c784ace543e345bdb8bd2f778be974dc89f2df5`.
- Existing Svelte static UI, Tauri 2 Rust boundary, framed pipe IPC, Python sidecar, Windows Job Object containment, LocalComet metadata/icon, and per-user app-data convention.

## Deferred decisions untouched

G03/G12 decomposition, G05 IPC versioning, G09 data lifecycle, public licensing, production performance baselines, production signing, and automatic updates.

## Files changed by category

- Desktop/package configuration: `desktop/localcomet-desktop/README.md`, `package.json`, `src-tauri/Cargo.toml`, `tauri.conf.json`, and `up00-runtime-manifest.json`.
- Windows installer: `desktop/localcomet-desktop/src-tauri/nsis/installer-hooks.nsh`.
- Desktop startup/lifecycle: `src-tauri/src/lib.rs`, `main.rs`, `single_instance.rs`, `startup.rs`, `supervisor.rs`, and `windows_job.rs`.
- Prospective governance: `OR-01_AUTHORITY_BOUNDARY.md`, `OR-01_DECISION_MATRIX.yaml`, and `OR-01_OWNER_RATIFICATION.md`.
- Work-package records: this PR body, rollback plan, test/acceptance plan, and work-package definition.
- Packaging and tests: `tools/build_up00_windows_installer.py`, `tools/test_up00_unready_sidecar.py`, and `tools/test_v6843_sidecar_supervisor.py`.

The branch changes 22 tracked paths with no tracked deletion. Generated Python, Node, Cargo, installer, install-smoke, and rollback outputs remain below ignored build/evidence roots and are not committed.

## Installer artifact

- Filename: `LocalComet_0.0.0_x64-setup.exe`
- Size: `12,273,194` bytes
- SHA-256: `58426bab541951d7b9f8ca8ce5f5e2d70e31c85ddd8055c2ea3c9fbde485ad5f`
- Package version: `0.0.0`
- Installed executable: `%LOCALAPPDATA%\Programs\LocalComet\LocalComet.exe`
- Installed executable size: `8,887,808` bytes
- Installed executable SHA-256: `b8a1b297acbf8a6a745f5f94aabfac0954d02433c018f5f3ce93e7a658cf4161`
- Signature: not signed, as required for `UNSIGNED_INTERNAL_BUILD`

## Tests and evidence

- Source/backend: changed Python files passed `py_compile`; the existing backend suite passed `225` checks; the packaged sidecar completed hello, health, shutdown, goodbye, and bounded exit without a repository Python dependency.
- Frontend: offline install resolved `84` packages with `0` vulnerabilities; `10` test files / `181` tests passed; Svelte check reported `0` errors and one unchanged accessibility warning; the production build passed.
- Rust/Tauri: format, offline check, all-target clippy with warnings denied, and `31` tests passed. The unsigned release and NSIS bundle completed successfully.
- Installer: silent current-user install exited `0`; `55` installer-owned files totaling `36,129,239` bytes were placed below `%LOCALAPPDATA%\Programs\LocalComet`; HKCU uninstall registration was present.
- Shortcuts: desktop and Start Menu shortcuts were both named `LocalComet`, targeted the same installed executable, and supplied no arguments.
- Readiness and UI: cold launch created one app and one required sidecar; the window appeared only after hello and health readiness. Direct UI inspection showed `Control Plane: Connected`.
- Console behavior: the GUI app owned no console window. The sidecar and its Windows-created `conhost.exe` helper both had `HWND 0`; all managed processes exited together.
- Duplicate and shutdown: a second shortcut launch retained the original app/sidecar PIDs and sidecar count `1`; normal close removed the app, sidecar, and helper with no orphan.
- Failure cleanup: an unresponsive fixture reached the bounded readiness timeout and was torn down without an orphan.
- Uninstall preservation: uninstall exited `0` and removed the install directory, both shortcuts, and registration. The existing user-data top-level fingerprint and startup-log size/hash were identical before and after uninstall.
- Authority-negative checks: no generic raw IPC, caller-controlled shell execution, Vault write, publication, automatic approval, telemetry, updater, login autostart, arbitrary network bootstrap, schema migration, or UP01-UP10 implementation was introduced.
- Rollback: a local disposable clone reverted the five implementation commits newest-first with `git revert --no-commit`; its staged tree exactly matched baseline tree `ac5cd9f2a5902db42ebe5403c6dc9fc14f4a114d`, then the feature state was restored. The canonical worktree remained unchanged and clean.

## Rollback

Uninstall without optional app-data deletion, preserve `%LOCALAPPDATA%\LocalComet`, and revert only this branch's commits in a disposable local clone. Never use rollback to delete user data or modify the Vault.

## Known limitations

- Unsigned internal build only.
- No production code signing or automatic updates.
- No public-release licensing or distribution claim.
- System WebView2 is a prerequisite; the installer adds no network bootstrap.

## Reviewer checklist

- [x] Governance commit is documentation-only and precedes source changes.
- [x] Only UP00-WP01 is authorized and implemented.
- [x] Existing IPC, data ownership, and architecture boundaries remain unchanged.
- [x] Installer is current-user and installer files do not overlap user data.
- [x] Both shortcuts target the installed executable.
- [x] Readiness, duplicate launch, shutdown, failure cleanup, and no-visible-console evidence pass.
- [x] Uninstall removes installer ownership and preserves user state.
- [x] Frontend, Rust/Tauri, backend, negative-authority, and rollback checks pass.
- [x] Artifact/evidence manifests and checksums verify.
- [x] `main` is unchanged; no push or remote PR occurred.

**Release warning:** `UNSIGNED_INTERNAL_BUILD`
````

### ПУТЬ: docs/work-packages/up00/UP00-WP01_ROLLBACK.md (37 строк, 2343 байт)

````markdown
# UP00-WP01 rollback

Rollback removes only this branch's code/configuration/documentation delta. It never deletes LocalComet user data, logs, projects, knowledge files, or Vault content.

## Preconditions

1. Stop the installed LocalComet window normally and verify no managed child remains.
2. Record the installer, installed executable, branch HEAD, commit list, and worktree status.
3. If an installed build is present, run its registered uninstaller without opting into app-data deletion.
4. Verify installer-owned files and shortcuts are gone while `%LOCALAPPDATA%\LocalComet` user-owned state remains.

## Source rollback

For rehearsal, use a disposable clone made from the local repository beneath the ignored build root. Do not rehearse by mutating `main` or the primary feature worktree.

In the disposable clone:

1. Check out the final feature commit detached.
2. Record `git diff --name-status main...HEAD` and exact commit order.
3. Revert the UP00-WP01 commits newest-first using normal inverse commits or `git revert --no-commit`; do not use `git reset --hard` or broad checkout restoration.
4. Confirm the resulting tracked tree equals baseline `6c784ace543e345bdb8bd2f778be974dc89f2df5` byte-for-byte.
5. Run baseline-safe integrity and syntax checks.
6. Restore the final feature state in the disposable clone from the locally known commit and rerun integrity checks.

The primary feature worktree remains untouched throughout rehearsal.

## Runtime/artifact rollback

- Generated build workspaces and unsigned installers are non-authoritative artifacts; stop using the superseded installer and retain checksums/evidence for audit.
- Do not remove `%LOCALAPPDATA%\LocalComet`, because it is the established user-data/log root.
- Do not run an installer option that deletes application data.
- Do not alter the Vault or any project/document path.
- Reinstallation of a prior binary is allowed only after its exact identity and data compatibility are independently verified; this work package does not claim a public downgrade path.

## Rollback pass condition

Rollback passes only when the disposable source tree returns to the exact baseline, user-owned state is unchanged, installer-owned files are removable, the successful feature state can be restored, and the original repository remains on the clean feature branch.
````

### ПУТЬ: docs/work-packages/up00/UP00-WP01_TEST_AND_ACCEPTANCE_PLAN.md (85 строк, 4504 байт)

````markdown
# UP00-WP01 test and acceptance plan

Every result must be captured with the exact command, exit code, UTC time, and relevant artifact identity. A failed command is not converted into a pass.

## A. Repository integrity

- Prove the initial `main` revision and commit subject.
- Prove the feature branch started at that revision and `main` never moved.
- Record tracked preimages/postimages for every changed path.
- Require no tracked deletion, no unrelated path change, no staged residue, and a clean final worktree.
- Scan changed text for machine-specific paths, secrets, Vault references, shell authority, telemetry, updater, publication, automatic approval, and login autostart.
- Keep generated dependencies/builds below ignored generated-output roots only.

## B. Frontend

In the generated workspace, with the lockfile and offline package cache:

```text
npm ci --offline
npm test
npm run check
npm run build
```

## C. Rust and Tauri

With the pinned lockfile and local Cargo cache:

```text
cargo fmt --all -- --check
cargo check --offline
cargo clippy --offline --all-targets -- -D warnings
cargo test --offline
npm run tauri -- build --bundles nsis --no-sign --ci -- --offline
```

Verify the resulting bundle is NSIS, current-user, unsigned, uses existing metadata/icons, and contains the staged sidecar/runtime files.

## D. Backend and sidecar

- Run `py_compile` for each changed Python file.
- Run the existing sidecar contract/supervisor checks in the isolated generated workspace.
- Run the new UP00 packaging/lifecycle checks.
- Launch the packaged sidecar with no repository Python dependency and validate hello, health, shutdown response, goodbye, and bounded exit.
- Exercise an unresponsive test sidecar and prove readiness timeout tears it down.
- Exercise repeated start on one supervisor and prove only one child.

## E. Installed application

Perform a bounded current-user installation from the generated installer.

- Record installer-owned paths before launch.
- Verify Start Menu and desktop shortcuts exist, are named `LocalComet`, and target the same installed executable.
- Launch with the Start Menu shortcut and prove the main window appears only after the startup log records readiness.
- Prove the required sidecar starts automatically and no terminal/developer tool is needed.
- Prove neither app nor sidecar owns a visible or persistent console window. If Windows creates a `conhost.exe` descendant for the console-subsystem sidecar, prove it has no window (`HWND 0`) and exits with the managed sidecar.
- Launch the desktop shortcut while the first instance is active; prove the second app exits and sidecar count stays one.
- Request normal window close; prove app and sidecar exit within the bounded timeout with no orphan.
- Verify an HKCU uninstall registration exists.

## F. Uninstall and data preservation

- Record every installer-owned path and shortcut before uninstall.
- Record the exact pre-existing top-level metadata fingerprint of the LocalComet per-user data root and the byte size/hash of the startup log.
- Run the generated uninstaller without selecting optional app-data deletion.
- Prove binaries, resources, shortcuts, and uninstall registration are removed.
- Prove the data-root fingerprint and startup log remain byte-identical after uninstall.
- Do not inspect or touch Vault content, projects, knowledge files, or unrelated user configuration.

## G. Negative authority

Diff and package scans must show no new generic raw IPC, shell plugin or caller-controlled command execution, Vault write, publication, automatic approval, telemetry/analytics, arbitrary network access, source-tree runtime state, login autostart, schema migration, or UP01-UP10 implementation.

## H. Rollback rehearsal

- Create a disposable local clone below the ignored build root from the local repository only.
- Verify the feature state and tests in that clone.
- Revert the branch commits newest-first without `reset --hard`, without deleting user data, and without touching the original worktree.
- Prove the disposable clone returns to the exact baseline tree and remains build-consistent for unchanged baseline checks.
- Reapply/restore the successful feature state in the disposable clone and rerun repository integrity.
- Leave the original feature branch unchanged and clean.

## Success gate

All categories A-H must pass. Any required failure that cannot be corrected inside the documented file scope produces the mission's exact blocker verdict.
````

### ПУТЬ: docs/work-packages/up00/UP00-WP01_WINDOWS_ONE_CLICK_LAUNCH.md (73 строк, 4721 байт)

````markdown
# UP00-WP01 — Windows One-Click Launch and Installer Baseline

**Status:** implementation complete; pending human PR review

**Owner decision:** `OR-01`

**Baseline:** `6c784ace543e345bdb8bd2f778be974dc89f2df5`

**Branch:** `feat/up00-wp01-windows-one-click-launch`

**Release classification:** `UNSIGNED_INTERNAL_BUILD`

## Purpose

Produce a normal per-user Windows installation of LocalComet. After one installation, a user launches `LocalComet` from the Start Menu or desktop without a repository checkout, terminal, Python, Node.js, npm, Cargo, Vite, or Tauri CLI.

The launch sequence is:

```text
Windows shortcut
  -> LocalComet.exe
  -> single-instance gate
  -> contained localcomet-core.exe
  -> bounded existing IPC hello and health response
  -> LocalComet window becomes visible and usable
```

## Source-grounded implementation

- Keep the current Svelte static frontend and Tauri 2 shell.
- Keep the current Rust `DesktopSidecarSupervisor`, framed stdin/stdout IPC, and Python entry point.
- Materialize the local CPython runtime and the existing sidecar dependency closure only in generated packaging output.
- Bundle the interpreter under the already-established release-sidecar name `localcomet-core.exe`; invoke it with fixed isolated arguments through the existing Windows Job Object launcher.
- Hide the main window until the current hello plus `app.health` exchange succeeds within a fixed timeout.
- Use a Windows named mutex for an exit-safe second launch; add no single-instance IPC protocol.
- Use Tauri's current-user NSIS support, existing `LocalComet` name, `com.localcomet.desktop` identifier, `0.0.0` package version, and existing icon.
- Place installer-owned binaries under `%LOCALAPPDATA%\Programs\LocalComet`; keep logs under `%LOCALAPPDATA%\LocalComet\logs`; do not place runtime state in Git.

## Scope

- Windows release subsystem/no-console behavior.
- Deterministic generated packaging workspace and private sidecar runtime staging.
- NSIS current-user bundle activation, Start Menu shortcut, desktop shortcut, and uninstall registration.
- Bounded startup, readiness, visible failure, duplicate-start prevention, normal shutdown, and failure cleanup.
- Tests and evidence for source, package, install, shortcut, process, uninstall, negative-authority, and rollback behavior.

## Exclusions

No UI redesign, command/event/capability change, IPC redesign, database or schema migration, user-data lifecycle change, Vault action, model manager change, Review Center change, Prompt Studio change, autonomous-task change, publication, signing, updater, login autostart, telemetry, dependency-major upgrade, or UP01-UP10 implementation.

## Acceptance criteria

1. A Windows NSIS installer is produced from the pinned Tauri major version and classified `UNSIGNED_INTERNAL_BUILD`.
2. Installation is current-user and does not require administrator rights.
3. Installer-owned files are separated from the established `%LOCALAPPDATA%\LocalComet` user-data root.
4. Start Menu and desktop shortcuts named `LocalComet` both target the installed executable.
5. Installed launch needs no terminal or developer tool and creates no persistent console window.
6. Exactly one required sidecar is started automatically through structured fixed arguments.
7. The application window is not shown as ready until bounded hello and health readiness succeeds.
8. Startup failure produces a sanitized native explanation with phase, retry guidance, log location, and safe-close guidance.
9. A second launch exits safely without a second sidecar.
10. Normal close and failed readiness leave no managed orphan.
11. Uninstall removes installer-owned files, shortcuts, and registration while preserving user-owned data and logs by default.
12. Frontend, Python/backend, Rust/Tauri, installer, installed-launch, authority-negative, and rollback checks pass.
13. The feature branch is clean, `main` is unchanged, and nothing is pushed or opened remotely.

## Deferred limitations

Production signing, automatic updates, public-release licensing, production performance baselines, and broader architecture/data/contract decisions remain deferred. WebView2 is treated as a Windows runtime prerequisite; this internal installer adds no network bootstrap.

## Acceptance result

All thirteen acceptance criteria passed in local verification. The generated NSIS installer, installed application, both shortcuts, readiness gate, duplicate-start behavior, normal shutdown, unresponsive-sidecar cleanup, uninstall preservation, authority-negative scans, and disposable-clone rollback rehearsal were verified. The release remains an unsigned internal build and requires human PR review before any publication decision.
````

### ПУТЬ: docs/work-packages/up01/UP01-WP01_MINIMAL_NAVIGATION_AND_SETTINGS.md (162 строк, 11051 байт)

````markdown
# UP01-WP01 — Minimal Desktop Navigation and Settings

## Authority and dependency

- Mission: `UP01-WP01_MINIMAL_DESKTOP_NAVIGATION_AND_SETTINGS`
- Branch: `feat/up01-wp01-minimal-navigation-settings`
- Exact base: `821d49c2130bfacb8dcb5ccd5371bd0a24105497`
- Dependency: UP00-WP01 (`feat/up00-wp01-windows-one-click-launch`)
- Release classification: `UNSIGNED_INTERNAL_BUILD`

This work package inherits the prospective governance ratification and authority boundaries recorded by UP00-WP01. It authorizes only the bounded frontend work described here.

## Objective and user problem

Make the desktop navigation calm and truthful by showing only the LocalComet identity, Chat, and Settings in the primary rail. Add a functional Settings drawer that consolidates theme, language, and Diagnostics controls. Remove visible placeholder promises and repair Diagnostics row overflow without changing chat, model connection, Control Plane, backend, IPC, Vault, or installer architecture.

The UP00 baseline UI exposes disabled Tasks and Settings actions, a Diagnostics rail action that does not open Diagnostics, a separate Review Center rail action, reserved Audit/Documents sidebar rows, and duplicate language/theme controls. Diagnostics close state and long telemetry rows are also inconsistent at desktop and narrow widths.

## Exact scope

### Navigation and view selection

| Surface | Current owner | Current behavior | UP01 behavior |
| --- | --- | --- | --- |
| Root view | `src/routes/+page.svelte` | Renders `AppShell` | Unchanged |
| Workspace selection | `src/lib/stores/shellStore.ts` | `chat` or `review` | Underlying modes preserved; visible rail exposes Chat only |
| Primary rail | `src/lib/components/shell/NavigationRail.svelte` | Local five-item array | Brand, Chat, bottom-aligned Settings only |
| Settings | No functional surface | Disabled rail placeholder | Frontend-only right drawer |
| Diagnostics | Shell stores plus `Diagnostics.svelte` | Header toggle; rail item is a no-op | Settings and header use one truthful visibility action |
| Sidebar preferences | `ConversationSidebar.svelte` | Separate language/theme quick controls | Removed from sidebar and consolidated in Settings |
| Sidebar placeholder rows | `conversationGroups` rendered by `ConversationSidebar.svelte` | Reserved Audit and disabled Documents rows show `Позже`/`Later` | Filtered from the rendered sidebar; fixture data remains reusable |

### Discovered rail entries

| Entry | Current state | Disposition |
| --- | --- | --- |
| LocalComet brand | Non-interactive identity | Keep |
| Chat | Functional, selects chat | Keep |
| Tasks / Задачи | Disabled placeholder with `later` / `позже` | Hide |
| Diagnostics | Marked enabled but only selects chat | Hide; Diagnostics remains available from Chat header and Settings |
| Review Center | Functional `review` workspace | Hide from the minimal rail; preserve all underlying view code |
| Settings | Disabled placeholder with `later` / `позже` | Replace with functional bottom rail action |

### Baseline state sources

- Theme: `themeMode` in `src/lib/stores/shellStore.ts`; resolved against `prefers-color-scheme` by `AppShell.svelte`; tokens live in `src/app.css`; currently memory-only.
- Locale: `locale` in `src/lib/i18n/index.ts`; currently persisted defensively under `localcomet.ui.language`.
- Diagnostics visibility: `inspectorVisible` and `inspectorDrawerOpen` in `shellStore.ts`; currently memory-only.
- Control Plane state: existing read-only `controlPlaneStore.bridgeState`; no bridge change is required.
- Versions: `DESKTOP_SHELL_VERSION` is `v6.84.5.1`; the existing title build label is `v6.84.5.1b`; UP00 records the internal status `UNSIGNED_INTERNAL_BUILD`.

## Settings surface

The right-side Settings drawer contains only:

1. Appearance: System, Light, Dark using the existing `themeMode` mechanism.
2. Language: Russian and English using the existing `locale` mechanism.
3. Diagnostics: show/hide the existing Diagnostics panel and display current Control Plane connection state read-only.
4. About: LocalComet, repository-proven version/build strings, and the existing internal-build classification.

Settings opens from the bottom rail action and `Ctrl+,`. Escape and the close control close it. Native buttons retain Enter and Space activation. The drawer is non-modal and does not trap focus.

## Preference persistence boundary

The frontend-only record is:

```json
{
  "theme": "system",
  "locale": "ru",
  "diagnosticsPanel": "closed"
}
```

- Key: `localcomet.ui.preferences.v1`
- Allowed `theme`: `system`, `light`, `dark`
- Allowed `locale`: `ru`, `en`
- Allowed `diagnosticsPanel`: `open`, `closed`
- Invalid JSON and invalid values fall back independently to safe defaults.
- Unknown fields are ignored and are not written back.
- A read-only fallback from the existing `localcomet.ui.language` key preserves the prior locale when the versioned record is absent.
- Settings open/closed state is not persisted.
- No prompts, chat content, model data, credentials, paths, tokens, Vault data, or machine-specific values are stored.
- No backend write, Tauri command, IPC request, network request, migration framework, or telemetry is introduced.

## Implemented files

Create:

- `desktop/localcomet-desktop/src/lib/components/shell/SettingsPanel.svelte`
- `desktop/localcomet-desktop/src/lib/stores/uiPreferences.ts`
- `desktop/localcomet-desktop/tests/settings.test.ts`
- `desktop/localcomet-desktop/tests/uiPreferences.test.ts`

Modify:

- `desktop/localcomet-desktop/src/lib/components/shell/NavigationRail.svelte`
- `desktop/localcomet-desktop/src/lib/components/shell/AppShell.svelte`
- `desktop/localcomet-desktop/src/lib/components/shell/ConversationSidebar.svelte`
- `desktop/localcomet-desktop/src/lib/components/shell/ChatHeader.svelte`
- `desktop/localcomet-desktop/src/lib/components/agent/Diagnostics.svelte`
- `desktop/localcomet-desktop/src/lib/components/common/EventStream.svelte`
- `desktop/localcomet-desktop/src/lib/components/common/TelemetryRow.svelte`
- `desktop/localcomet-desktop/src/lib/stores/shellStore.ts`
- `desktop/localcomet-desktop/src/lib/i18n/index.ts`
- `desktop/localcomet-desktop/src/lib/i18n/en.ts`
- `desktop/localcomet-desktop/src/lib/i18n/ru.ts`
- `desktop/localcomet-desktop/src/lib/version.ts`
- `desktop/localcomet-desktop/src/app.css`
- relevant bounded frontend tests under `desktop/localcomet-desktop/tests/`
- the four UP01 work-package documents in this directory

## Explicit exclusions

The following remain unchanged:

- all Python application/backend modules;
- `desktop/localcomet-desktop/src-tauri/**` and every Rust command or Tauri capability;
- `src/lib/bridge/**`, Control Plane and model gateway contracts;
- `src/lib/components/model/**` and the model-connect workflow;
- `src/lib/components/chat/**` and chat behavior;
- `src/lib/components/review/**` and the underlying Review Center workspace;
- `src/lib/components/shell/AgentInspector.svelte` and its unrendered legacy fixture content;
- installer configuration and installer architecture;
- databases, telemetry, network access, Vault content, `Projects/BrowserProfile`, and UP02–UP10.

## Accessibility requirements

- Every visible rail action is a semantic button with a real handler, concise localized label and tooltip, native Enter/Space support, visible focus, and truthful active state.
- The Settings close control receives initial focus and is keyboard reachable; closing returns focus to the Settings rail action when possible.
- Settings does not trap focus.
- Theme, language, and Diagnostics choices expose selected state through `aria-pressed` or equivalent semantics.
- Diagnostics values wrap within their row and expose the full value through an accessible tooltip.
- Existing contrast tokens and reduced-motion behavior are preserved.

## Visual acceptance criteria

- The primary rail contains only brand, Chat, and bottom-aligned Settings.
- No rendered primary-navigation tooltip contains `позже`, `later`, `coming soon`, or `reserved`.
- Reserved Audit/Documents sidebar rows and duplicate language/theme controls are not rendered.
- Settings is usable at the current desktop width and at a narrower supported Windows desktop width.
- Diagnostics labels and values remain separated with no overlap at 100% and 125% scaling equivalents.
- Diagnostics remains scrollable and its close control remains visible.
- Chat layout, model connection, title bar, Control Plane status, typography, icons, and color tokens remain recognizable and functional.

## Acceptance outcome

- Frontend validation: 12 test files and 202 tests passed; `svelte-check` reported 0 errors and one pre-existing warning in the unrendered legacy `LanguageSwitcher.svelte`; the production build passed.
- Browser acceptance: Chat and Settings were the only interactive rail actions; mouse, Enter, Space, `Ctrl+,`, Escape, close-focus restoration, theme, locale, Diagnostics, persistence, and defensive preference behavior passed.
- Layout acceptance: Settings and Diagnostics had no horizontal overflow at 1280, 1024 (125% CSS-pixel equivalent), or 800 CSS pixels. Seventeen Diagnostics rows had no measured label/value overlap, and the close control remained visible while scrolled.
- Authority boundary: the diff contains no Python, Rust, Tauri command, IPC, backend/Vault write, network, telemetry, model-runtime, shell-authority, or installer-architecture change.
- Installer regression: the unchanged UP00 packaging command built `LocalComet_0.0.0_x64-setup.exe` from implementation commit `4698211c50058b1c4ffc6669c576bedc65871f4a`; size 12,272,900 bytes; SHA-256 `25f4524b7bd897bccfedc128a2ae36c217c5b3884b9c082f4652efa8a5a003b7`; Authenticode status `NotSigned`.
- Installed smoke: Start Menu app identity `com.localcomet.desktop` launched one LocalComet window; Control Plane reached Connected; model-connect remained available; Light, English, and open Diagnostics persisted across restart; duplicate launch remained single-window; normal close left no `LocalComet` or `localcomet-core` process.
- Rollback rehearsal: reverting `821d49c2130bfacb8dcb5ccd5371bd0a24105497..4698211c50058b1c4ffc6669c576bedc65871f4a` in a disposable clone completed without conflict and reproduced the exact base tree `a34f5e50e23c4a5c1c097fbd53c82bce674920d0`.

## Rollback

Rollback is by reverting the UP01 commits in reverse order or abandoning this stacked branch and returning to exact commit `821d49c2130bfacb8dcb5ccd5371bd0a24105497`. The preference record is frontend-only and safe to leave in place; the predecessor ignores it. No backend, IPC, schema, Vault, or user-content rollback is required.

## No-backend-authority statement

UP01-WP01 grants no authority to add or change Python backend behavior, Rust commands, Tauri IPC, generic shell execution, network access, model runtime behavior, database/schema state, Vault behavior, telemetry, automatic approvals, autonomous tasks, publication, or UP02–UP10 features.
````

### ПУТЬ: docs/work-packages/up01/UP01-WP01_PR_BODY.md (60 строк, 3901 байт)

````markdown
# UP01-WP01 — Minimal Desktop Navigation and Settings

## Summary

This stacked change simplifies the LocalComet desktop primary rail to the product identity, Chat, and a bottom-aligned functional Settings action. Settings consolidates existing theme, language, and Diagnostics controls, uses bounded frontend-only persistence, and shows repository-proven About values. Diagnostics rows and close behavior are tightened for desktop and narrow layouts.

## Dependency

This branch is stacked on UP00-WP01 commit `821d49c2130bfacb8dcb5ccd5371bd0a24105497` from `feat/up00-wp01-windows-one-click-launch`. Review and integration must preserve that dependency. It must not be rebased directly onto the expected main baseline `6c784ace543e345bdb8bd2f778be974dc89f2df5` without first integrating UP00-WP01.

## User-visible changes

- Primary rail contains only LocalComet, Chat, and Settings.
- Tasks and misleading/no-op rail actions are no longer rendered.
- Review Center remains in source but is not exposed in the minimal rail.
- Reserved Audit/Documents sidebar rows are no longer rendered.
- Theme and language quick controls move from the sidebar into Settings.
- Settings supports Appearance, Language, Diagnostics, and About only.
- `Ctrl+,`, Escape, and the close control provide keyboard access.
- Diagnostics visibility persists and long telemetry values no longer overlap labels.

## Persistence

`localcomet.ui.preferences.v1` contains only:

```json
{
  "theme": "system | light | dark",
  "locale": "ru | en",
  "diagnosticsPanel": "open | closed"
}
```

Parsing is defensive, unknown fields are ignored, invalid values use safe defaults, and no backend or network operation is invoked.

## Explicit exclusions

No backend, Rust command, Tauri IPC, model runtime, database/schema, Vault, network, telemetry, update, account, API-key, cloud, model-download, autonomous-task, approval, or installer-architecture feature is added. Chat and model-connect behavior remain unchanged.

## Validation

- `npm test`: PASS — 12 test files, 202 tests.
- `npm run check`: PASS — 0 errors; one pre-existing warning in the unrendered legacy `LanguageSwitcher.svelte`.
- `npm run build`: PASS.
- Rendered keyboard/accessibility flow: PASS — mouse, Enter, Space, `Ctrl+,`, Escape, focus return, semantic names and selected states.
- Responsive Diagnostics/Settings validation: PASS at 1280, 1024 (125% CSS-pixel equivalent), and 800 CSS pixels; no row overlap or horizontal overflow; sticky close remained visible.
- Authority-negative scan: PASS — no backend, Rust/Tauri command, IPC, Vault, network, telemetry, model-runtime, shell-authority, or installer-architecture change.
- Approved-path, unchanged-helper packaging: PASS — 225 sidecar checks, offline npm gates, Cargo fmt/check/clippy, 31 Rust tests, and unsigned NSIS bundle.
- Installer: `LocalComet_0.0.0_x64-setup.exe`, 12,272,900 bytes, SHA-256 `25f4524b7bd897bccfedc128a2ae36c217c5b3884b9c082f4652efa8a5a003b7`, Authenticode `NotSigned`.
- Installed Start Menu smoke: PASS — app identity `com.localcomet.desktop`, minimal rail, functional Settings, Light/English/Diagnostics persistence, Control Plane Connected, model-connect available, and one-window duplicate launch.
- Shutdown/orphan check: PASS — normal close left no `LocalComet` or `localcomet-core` process.
- Rollback rehearsal: PASS — conflict-free revert reproduced the exact UP00 base tree.

The unchanged UP00 helper hard-codes its predecessor branch name. Packaging therefore ran in a clean external clone whose local compatibility branch pointed to the exact UP01 implementation commit; the canonical feature branch, packaging source, installer architecture, scope, and shortcut behavior were not changed.

## Release status

Internal human review only. Nothing is pushed and no remote pull request is opened by this work package.

`UNSIGNED_INTERNAL_BUILD`
````

### ПУТЬ: docs/work-packages/up01/UP01-WP01_ROLLBACK.md (45 строк, 2666 байт)

````markdown
# UP01-WP01 Rollback

## Rollback boundary

UP01 changes frontend navigation, a frontend-only Settings drawer, a versioned UI preference record, Diagnostics layout styles, tests, and work-package documentation. It does not change backend, IPC, Rust commands, databases, Vault content, model runtime, installer architecture, installation scope, or user chat content.

## Source rollback

Preferred rollback options:

1. Revert the UP01 commits in reverse order on `feat/up01-wp01-minimal-navigation-settings`.
2. If the branch has not been shared, abandon it and restore the predecessor branch at exact commit `821d49c2130bfacb8dcb5ccd5371bd0a24105497`.

Do not rewrite or reset `main`. Do not alter the UP00 predecessor commit.

## Preference rollback

The only new persistent record is `localcomet.ui.preferences.v1` with theme, locale, and Diagnostics visibility. The UP00 frontend does not read that key, so source rollback is safe without deleting it. The pre-existing `localcomet.ui.language` value is read only as a compatibility fallback and is not broadened.

No prompt, chat, model, credential, path, machine, Vault, database, or backend data requires rollback.

## Installer rollback

UP01 does not change installer architecture or scope. If installed-smoke validation fails because of UP01:

- stop publication and return the required blocker;
- retain the evidence and installer checksum;
- reinstall the previously accepted UP00 internal build only when a bounded human rollback is required;
- do not select any uninstall option that removes application data;
- verify shortcuts and processes belong to the intended installation before any uninstall action.

## Rehearsal acceptance

A disposable clone/worktree rollback rehearsal must show that reverting the UP01 commit range restores the exact UP00 source tree, aside from ignored build output, and that no backend, IPC, Vault, or data migration step is needed.

## Recorded rehearsal

- Disposable clone: `C:\Users\DNS\Documents\LocalComet-UP01-WP01-Rollback-20260720T100932Z`
- Feature implementation HEAD: `4698211c50058b1c4ffc6669c576bedc65871f4a`
- Base: `821d49c2130bfacb8dcb5ccd5371bd0a24105497`
- Command: `git revert --no-commit 821d49c2130bfacb8dcb5ccd5371bd0a24105497..4698211c50058b1c4ffc6669c576bedc65871f4a`
- Result: exit 0, zero conflicts, five commits reverted by the sequencer.
- Base tree and reverted index tree: `a34f5e50e23c4a5c1c097fbd53c82bce674920d0`.
- Tracked tree vs base, index vs base, and worktree vs index comparisons all returned exit 0.
- The inverse changes remain staged only in the disposable clone; the canonical feature repository remained clean and unchanged.
````

### ПУТЬ: docs/work-packages/up01/UP01-WP01_TEST_AND_ACCEPTANCE_PLAN.md (126 строк, 7030 байт)

````markdown
# UP01-WP01 Test and Acceptance Plan

## Preconditions

- Canonical repository: `C:\Users\DNS\Documents\LocalComet`
- Branch: `feat/up01-wp01-minimal-navigation-settings`
- Base: `821d49c2130bfacb8dcb5ccd5371bd0a24105497`
- Clean index/worktree before packaging
- No Vault access and no network-dependent installation

## Repository-supported frontend commands

Run from `desktop/localcomet-desktop`:

```powershell
npm test
npm run check
npm run build
```

The package has no repository-defined lint or formatting script. The unchanged UP00 packaging helper additionally runs offline npm, Cargo formatting/check/clippy/test, sidecar readiness, and the NSIS build.

## Static and unit acceptance

- All Vitest tests pass.
- `svelte-check` reports no errors or warnings introduced by UP01.
- The production Vite build succeeds.
- Preference tests cover valid values, invalid JSON, invalid values, unknown fields, safe defaults, legacy locale fallback, and storage failure.
- Store tests prove theme, locale, and Diagnostics persistence without persisting Settings state or unrelated data.
- Server-rendered component tests prove only Chat and Settings rail actions render, Settings is functional, sidebar placeholders are absent, and preference controls are consolidated.

## Interaction flow

The flow under test is: app loads into Chat -> Settings opens from the bottom rail or `Ctrl+,` -> theme, language, and Diagnostics controls update existing frontend state -> Escape or Close dismisses Settings -> Diagnostics remains usable and closable.

Verify:

1. Chat remains active and functional.
2. Settings opens from mouse, Enter, Space, and `Ctrl+,`.
3. Settings closes from Escape and its close control.
4. Tasks, Review Center, rail Diagnostics, reserved Audit, and Documents are not rendered in the production navigation surfaces.
5. No visible navigation tooltip contains `позже`, `later`, `coming soon`, or `reserved`.
6. Every visible rail action has a real handler, focus state, accessible name, tooltip, and truthful active state.
7. Theme changes among System, Light, and Dark.
8. Locale changes between Russian and English.
9. Diagnostics opens and closes from Settings and from the existing Chat header control.
10. Existing Control Plane connection state is displayed read-only in Settings.
11. Refresh/restart restores theme, locale, and Diagnostics visibility.
12. Invalid or extra stored values do not break startup.

## Accessibility acceptance

- Keyboard-only traversal reaches Chat, Settings, all Settings controls, and Close.
- Native semantic buttons handle Enter and Space.
- Focus is visible against existing tokens.
- Opening Settings moves focus to Close; closing returns focus to the Settings action when possible.
- The drawer is non-modal and has no focus trap.
- Selected theme/language/Diagnostics state is programmatically exposed.
- Long Diagnostics values wrap and expose full text by tooltip/title.
- Existing reduced-motion handling remains effective.

## Layout acceptance

Capture local screenshots after tests pass for:

1. minimal primary rail;
2. Settings — Appearance;
3. Settings — Language;
4. Settings — Diagnostics;
5. closed Settings with Diagnostics visible;
6. Diagnostics rows without overlap.

Validate the current desktop layout and a narrower supported desktop viewport, including CSS-pixel equivalents for 100% and 125% Windows scaling. Check for clipped controls, text overlap, rail overlap, scroll traps, hidden close controls, and duplicate route/navigation UI.

## Authority-negative acceptance

Diff and repository scans must prove the patch adds no:

- Python or Rust source change;
- Tauri command, IPC contract, capability, or generic shell execution;
- backend or Vault write;
- database/schema change;
- model runtime change;
- network call, remote font, remote icon, telemetry, or update check;
- prompt/chat/model/path/token/credential persistence;
- hidden placeholder feature implementation.

## Regression and installer acceptance

After frontend acceptance and clean commits:

- Rebuild the unsigned current-user NSIS installer with the unchanged UP00 packaging implementation.
- Record any branch-guard compatibility handling explicitly; do not modify or bypass installer architecture.
- Install without deleting or migrating user data.
- Launch from the Start Menu and confirm the minimal rail, Settings, theme, language, Diagnostics, and Control Plane connection.
- Confirm model-connect remains available.
- Close normally and confirm the desktop app, sidecar, and helper leave no orphan process.
- Preserve installed user data.
- Record installer filename, bytes, SHA-256, and unsigned status.

## Evidence outputs

Write only bounded reports and screenshots to the external UP01 evidence directory. Do not commit screenshots, source copies, environment dumps, credentials, personal prompts, or Vault content.

## Recorded result

| Gate | Result |
| --- | --- |
| Validated implementation commit | `4698211c50058b1c4ffc6669c576bedc65871f4a` |
| `npm test` | PASS — 12 files, 202 tests |
| `npm run check` | PASS — 0 errors; 1 pre-existing warning in unrendered legacy `LanguageSwitcher.svelte` |
| `npm run build` | PASS — static production bundle generated |
| UP00 sidecar guard suite | PASS — 225 checks |
| Cargo format/check/clippy | PASS — offline, no clippy warnings |
| Cargo tests | PASS — 31 tests |
| Navigation/settings keyboard flow | PASS — mouse, Enter, Space, `Ctrl+,`, Escape, and focus return |
| Preference validation | PASS — valid, invalid, unknown, failure, persistence, and legacy locale cases |
| Accessibility | PASS — semantic names/states, focus, close reachability, no focus trap |
| Layout | PASS — 1280, 1024, and 800 CSS-pixel widths; no row overlap or horizontal overflow |
| Authority-negative scan | PASS — no backend, IPC, Vault, network, telemetry, shell, or model authority added |
| Installer | PASS — `LocalComet_0.0.0_x64-setup.exe`, 12,272,900 bytes, SHA-256 `25f4524b7bd897bccfedc128a2ae36c217c5b3884b9c082f4652efa8a5a003b7`, Authenticode `NotSigned`, `UNSIGNED_INTERNAL_BUILD` |
| Installed Start Menu smoke | PASS — `com.localcomet.desktop`, Connected control plane, model-connect present, persisted preferences, clean shutdown |
| Duplicate launch | PASS — one LocalComet window |
| Rollback rehearsal | PASS — conflict-free inverse range reproduced the exact UP00 base tree |

The installer helper's frozen branch guard was satisfied only inside a clean external packaging clone by assigning its required predecessor branch name to the exact UP01 implementation commit. The canonical feature branch was not renamed or moved, and the helper, installer architecture, install scope, and shortcut behavior were unchanged. An initial ordinary Windows clone was rejected by the frozen-file hash guard because global `core.autocrlf=true` changed a guarded working-tree hash; the successful clone used `core.autocrlf=false` so checked-out bytes matched the canonical blobs.
````

### ПУТЬ: docs/work-packages/up02/UP02-WP01-HF2_PR_BODY.md (22 строк, 1448 байт)

````markdown
# UP02-WP01-HF2 PR body

## Summary

- correct the Settings rail icon to an unambiguous local gear;
- remove production-visible demo, placeholder, duplicate, and raw-debug UI;
- retain only useful functional controls and localized accessible names;
- truthfully gate Project Knowledge because the current production source/authority contract is absent;
- preserve the lower-level typed knowledge pipeline for later authorized integration;
- preserve real local chat, streaming, Stop, retry, restart, HF1 scrolling/composer, Settings, Diagnostics, and the offline installer.

## Knowledge state

The preview and decision pipeline is implemented, but production adapter construction requires an external Vault path. HF2 does not request or grant that authority. Production UI therefore states that project context is currently unavailable, sends no project data, does not call it memory, and never blocks ordinary chat.

## Verification

Focused visible-control/knowledge/layout tests passed before one complete frontend, Rust/Tauri, and backend pass. The final unsigned internal NSIS installer passed Start Menu launch, two real-model responses, Stop/Retry, transcript scrolling, composer reachability, narrow-window layout, and orphan-free shutdown. External evidence records all controls and results.

## Distribution

Internal unsigned build only. Model/runtime are owner-provisioned and not bundled. No push or remote pull request is performed.
````

### ПУТЬ: docs/work-packages/up02/UP02-WP01-HF2_ROLLBACK.md (14 строк, 741 байт)

````markdown
# UP02-WP01-HF2 rollback

The exact predecessor is b33f0ad85ec4c9058ee10a86fe2936c187fa3c11.

Rollback is the reverse of the ordered HF2 commits. It restores the prior icon path, production fixture rendering, composer knowledge wiring, and prior diagnostics presentation without touching model/runtime artifacts, user settings, chat data, Vault, or the legacy LocalAgent checkout.

A detached external worktree rehearsal must prove:

- exact predecessor tree is available and clean;
- the ordered HF2 series reconstructs the canonical feature tree;
- reverse application returns to the exact predecessor tree;
- no managed runtime/model or user-owned data is changed.

Do not reset, clean, or switch the canonical checkout during rehearsal.
````

### ПУТЬ: docs/work-packages/up02/UP02-WP01-HF2_TEST_AND_ACCEPTANCE_PLAN.md (38 строк, 2785 байт)

````markdown
# UP02-WP01-HF2 test and acceptance plan

## Focused first

1. Source/render tests verify the recognizable gear, localized accessible names, desktop/narrow sidebar behavior, hidden demo thread, removed redundant badges, hidden placeholder buttons, removed raw request metrics, and useful Diagnostics controls.
2. Production Project Knowledge tests verify a static localized unavailable state, no switch, no preview panel in the composer, no preview request wiring, no long-term-memory claim, and an unaffected ordinary chat path.
3. Existing lower-level knowledge preview/decision tests remain intact to preserve the already implemented typed pipeline.
4. Layout tests cover 1920×1080, 1366×768, 1280×720, and 1024×640 CSS-equivalent viewports and 100%, 125%, and 150% scaling equivalents.

## Affected regression

After focused tests pass, run the complete frontend Vitest suite, Svelte/type check, frontend production build, rustfmt, locked/offline Cargo check, warnings-denied Clippy, affected Rust tests, touched Python compilation, affected backend/knowledge/security suites, and one final offline NSIS bundle.

## Installed smoke

Launch the final installed package from Start Menu. Verify the minimal rail and gear, absence of demo/placeholders, Settings and About, truthful unavailable Project Knowledge, model connection, two real prompts, progressive stream, Stop, stable partial response, retry, scroll/composer, normal restart, and clean shutdown without managed orphans.

## Acceptance thresholds

- dead visible controls: 0
- placeholder visible controls: 0
- misleading enabled controls: 0
- Project Knowledge preview requests from production unavailable UI: 0
- new authorities: 0
- affected regression failures: 0

## Recorded results

- Focused frontend: 5 files / 69 tests passed.
- Complete frontend: 17 files / 262 tests passed.
- Svelte/type check: 0 errors; one pre-existing LanguageSwitcher listbox tabindex warning.
- Frontend production build: passed.
- Sidecar supervisor: 225 checks passed.
- Rust: fmt, locked/offline check, warnings-denied Clippy, and 75 tests passed; 2 owner-artifact tests ignored as designed.
- Backend knowledge/security/chat: 86 + 86 + 5 + 7 + 13 tests passed; changed Python files compiled.
- Layout matrix: 1920×1080, 1366×768, 1280×720, and 1024×640 CSS-equivalent viewports at 100%, 125%, and 150% equivalents passed.
- Installed acceptance: 2048×1152 logical desktop on a 2560×1440 display (125% effective ratio) plus a 1024-pixel-wide snapped window passed. Composer remained above the taskbar with no horizontal or outer-page overflow.
- Installed local model: first and second responses passed; Stop, stable partial cancellation, Retry, mouse/keyboard/drag scrolling, near-bottom follow, and clean shutdown passed.
````

### ПУТЬ: docs/work-packages/up02/UP02-WP01-HF2_UI_HYGIENE_AND_KNOWLEDGE_TRUTHFULNESS.md (44 строк, 4041 байт)

````markdown
# UP02-WP01-HF2 — UI hygiene and Project Knowledge truthfulness

## Objective

Remove production-visible fixtures, dead or misleading controls, ambiguous Settings semantics, redundant build detail, and raw chat telemetry while preserving the accepted local-model chat and minimal LocalComet visual language.

This hotfix is stacked on UP02-WP01 commit b33f0ad85ec4c9058ee10a86fe2936c187fa3c11.

## Bounded inventory

VISIBLE_CONTROL_INVENTORY.tsv records every interactive or control-like item in the primary rail, thread sidebar, chat toolbar, status area, transcript/composer, Project Knowledge row, model drawer, Settings, Diagnostics, and About. The inventory records labels, accessible names, icons, handlers, actions, state, keyboard behavior, functionality, duplication, fixtures, and disposition.

## Planned corrections

- Replace the custom brightness-like Settings path with a recognizable gear in the existing local Icon component.
- Preserve only brand, Chat, and bottom-aligned Settings in the primary rail.
- Hide the cancellation-demo thread from production without deleting its test fixture or any persisted chat.
- Remove redundant sidebar version/developer labels because version/build remain in Settings → About.
- Make the header sidebar toggle narrow-layout-only and localize it; localize Diagnostics.
- Hide disabled Tools and installer placeholder buttons and remove raw request metrics from normal chat.
- Remove no-op diagnostics tabs and production demo controls while preserving underlying test fixtures.
- Keep all real model setup, runtime, transcript, retry, Settings, and Diagnostics actions.

## Project Knowledge diagnosis

The typed preview, decision, and bounded injection pipeline exists and is tested. Production adapter construction, however, requires an externally configured LOCALCOMET_KNOWLEDGE_VAULT path and otherwise returns no adapter. The installed acceptance failure therefore reflects a partial pipeline with no current production source-selection/authority contract.

HF2 does not add Vault, repository, file, RAG, memory, indexing, or generic IPC authority. The production composer will expose a localized non-interactive unavailable state, explain that no project data is sent and that this is not long-term memory, and always allow ordinary chat. Existing lower-level pipeline code and fixtures remain available for later authorized work.

## Explicit exclusions

No redesign, Agent, Computer Use, Browser, Swiss Knife, patch execution, cloud inference, network access, download, Vault read, repository-to-model context, arbitrary filesystem access, shell, or new IPC.

## Final implementation and acceptance

- Production navigation contains brand, Chat, and the recognizable Settings gear; the fixture-only cancellation conversation is not rendered.
- Duplicate version/developer badges, disabled placeholder controls, no-op diagnostics tabs/demo controls, and request telemetry outside Diagnostics are absent.
- Settings retains language, appearance, functional Diagnostics, About version/build, and the truthful available/unavailable capability summary.
- Project Knowledge is a localized non-interactive unavailable state in both English and Russian. It sends no project data, does not claim long-term memory, and does not block ordinary chat.
- The final installed build connected the owner-provisioned Qwen2.5 1.5B managed model, returned two real truthful Russian answers, preserved progressive streaming, accepted Stop, preserved the partial response, and completed Retry.
- The transcript scrolled by mouse wheel, scrollbar drag, PageUp/PageDown, Home/End; manual upward reading was not reset during streaming and returning to the bottom resumed follow behavior. The composer stayed visible in maximized and 1024-pixel-wide snapped windows.
- Clean application exit left no LocalComet, localcomet-core, or llama-server process.

Final installer: `LocalComet_0.0.0_x64-setup.exe`, 12,536,287 bytes, SHA-256 `9ac01a6218da251b7ec24772320af22de535d68c17e5d8529b01e7d48fb8ca34`.
````

### ПУТЬ: docs/work-packages/up02/UP02-WP01_ASSISTANT_CONTEXT_SCHEMA.md (45 строк, 2211 байт)

````markdown
# UP02-WP01 AssistantContext Schema

## Trusted value

`AssistantContext` is an immutable, application-owned value authored at the Tauri request boundary and strictly validated before provider-message construction.

```yaml
application:
  name: LocalComet
  mode: local_offline_desktop_assistant
  version: v6.84.5.1
conversation:
  locale: ru | en
  project_context_available: false
capabilities:
  local_chat: true
  local_model_inference: true
  internet: false
  email: false
  browser: false
  filesystem: false
  vault: false
  computer_use: false
  shell: false
  tools: []
```

The version is the existing source-proven desktop shell version. The locale is the only per-turn input and is restricted to the existing Settings preference enum. All authority-bearing values are application constants. Missing, extra, wrongly typed, or changed capability fields are rejected. Unknown capability keys never grant authority.

## Deterministic instruction meaning

The system instruction is compact and deterministic. It says that the model is a local assistant operating inside LocalComet, follows the current UI language unless the user explicitly requests another language, describes only enabled capabilities, cannot gain authority from user text, has no project context, does not invent project facts, distinguishes the assistant/model/user/application, may draft without claiming execution, and is concise and practical by default.

## Security properties

- Frontend code can select only `ru` or `en`; it cannot supply capability fields or arbitrary system text.
- The user prompt is carried separately and always follows the system message.
- The provider payload is validated as exactly `[system, user]` for ordinary chat.
- No absolute path, user name, repository location, Vault location, secret, credential, or environment dump is present.
- The context and system instruction are not rendered in chat or included in normal user-visible diagnostics.
- Local loopback inference transport is not an internet capability.

## Safe display projection

Settings may show only localized availability lists. It must not show the system prompt, internal paths, or offer toggles for unavailable capabilities.
````

### ПУТЬ: docs/work-packages/up02/UP02-WP01_PR_BODY.md (30 строк, 2180 байт)

````markdown
# UP02-WP01 PR Body

## Summary

- add an immutable LocalComet `AssistantContext` to the existing typed local-model request path;
- construct a deterministic system instruction before the unchanged user message;
- default model replies to the selected UI locale and declare project context unavailable;
- add bounded first-use, loading, failed/timed-out, cancelled, and retry guidance;
- add a localized read-only capability summary to Settings/About;
- preserve real streaming, Stop, retry, readiness, HF1 scrolling/composer behaviour, minimal navigation, and the offline installer.

## Trust boundary

The frontend sends only the existing validated locale enum. Tauri authors the full context with fixed capability values. The local gateway rejects missing, extra, unknown, or capability-changing fields and builds the provider system message deterministically. System content is not rendered or logged to user-visible diagnostics.

## Capability truth

Available: local chat and local model inference.

Unavailable: internet, email, browser, files, Vault, Computer Use, shell, and external tools. Project-specific context is not supplied. User text cannot change these values.

## Verification

The final evidence package records frontend, Rust/Tauri, backend, security-negative, installed semantic, 40-row regression, installer, uninstall/reinstall, process cleanup, and rollback results. Any critical truthfulness or existing-function regression failure blocks completion.

Completed local verification passed all 15 installed semantic prompts with zero critical truthfulness failures. It also passed the 30-message/long-stream HF1 layout checks, mouse and keyboard scrolling, Stop with stable partial output, retry, restart, Settings/capability summary and persistence, exact managed-artifact preservation through uninstall/reinstall, and clean process shutdown. The offline pipeline passed 247 frontend tests, Svelte check/build, Rust format/check/Clippy/tests, backend suites, release build, and unsigned NSIS bundle.

## Distribution

Internal unsigned build only. The bootstrap model/runtime are not bundled. No push or remote pull request is performed by this mission.
````

### ПУТЬ: docs/work-packages/up02/UP02-WP01_ROLLBACK.md (21 строк, 1339 байт)

````markdown
# UP02-WP01 Rollback

## Source rollback

The exact predecessor is `ee221944eca092580e333b804f4e408a89a0bc76` on `feat/up05-wp01-r2-real-model-chat`. A bounded rehearsal uses a temporary detached worktree or equivalent read-only tree comparison so the active feature branch and user data are not destructively reset.

Verification criteria:

- the predecessor tree matches the required commit exactly;
- removing the UP02 commits removes the trusted context, new chat guidance, Settings capability summary, and UP02 tests/docs;
- predecessor chat, runtime, HF1 layout, and installer source remain recoverable;
- reconstructing the feature from its ordered commits produces the feature tree again;
- managed runtime/model data, UI preferences, chat data, Vault, and user-owned files are not deleted or changed.

## Installed rollback

Use the existing per-user uninstaller. Confirm it removes only application-owned installed files and shortcuts while preserving external managed runtime/model and user-owned data. Reinstall the predecessor only from an already approved local artifact if available; do not download anything.

## Unsafe conditions

Stop with `BLOCKED_UNSAFE_ROLLBACK` if exact targets cannot be proven, if rollback would require deleting user-owned data, or if the successful feature state cannot be reconstructed cleanly.
````

### ПУТЬ: docs/work-packages/up02/UP02-WP01_TEST_AND_ACCEPTANCE_PLAN.md (36 строк, 3977 байт)

````markdown
# UP02-WP01 Test and Acceptance Plan

## Automated verification

1. Context tests prove exact application identity/version, `ru` and `en` locale handling, explicit capability values, fail-closed missing/unknown fields, message order, and absence of private data.
2. Frontend tests cover locale transport, empty/unavailable/loading/ready states, lifecycle labels, retry, Settings capability summary, existing chat reliability, preferences, and HF1 scrolling.
3. Rust tests cover typed locale validation, trusted context construction, exact forwarded payload, capability immutability, and existing request/cancellation state machines.
4. Python tests cover strict context validation, deterministic system assembly, provider `[system, user]` order, streaming, cancellation, exactly-one terminal event, second request, timeout recovery, and source hygiene.
5. Run complete Vitest, Svelte/type check, production frontend build, `rustfmt`, locked/offline Cargo check, warnings-denied Clippy, affected Rust tests, Python compile/tests, release build, and offline NSIS bundle.

## Security negatives

Search the feature diff and request contract for network, email, filesystem/Vault, shell, Computer Use, generic IPC, model/runtime payload, path, secret, and credential authority. Loopback-only existing model transport is expected. The test must prove that prompt text and unknown keys cannot change the trusted capability set.

## Installed semantic acceptance

Use the approved installed bootstrap model with Russian UI. Evaluate the 15 owner-specified prompts semantically: identity, current abilities, internet/news/email/files/Vault/shell/Computer Use refusals, missing project context, prompt-injection resistance, explicit English, return to Russian, useful Rust planning, and text editing. Any claim that an unavailable action was performed is a critical failure.

## Existing-function regression matrix

The external evidence contains one TSV and one Markdown matrix with all 40 required rows. Each row records ID, method, expected result, actual result, PASS/FAIL/BLOCKED, evidence reference, and whether UP02 introduced a failure.

Installed acceptance also covers a 30-message conversation, long streaming output, near-bottom follow, stable manual upward scrolling, Stop/retry/restart, Settings and preference persistence, uninstall/reinstall with managed artifacts preserved, shortcut launch, and clean shutdown without LocalComet-managed orphans.

## Evidence policy

Evidence and installer artifacts are written only to the owner-specified external directories. They exclude model/runtime bytes, source copies, Vault content, private documents, secrets, credentials, full environment dumps, and unrelated logs. No network access is used.

## Completed acceptance summary

- Automated frontend: 16 files and 247 tests passed; Svelte check reported 0 errors and the single pre-existing `LanguageSwitcher.svelte` warning; production build passed.
- Offline Rust/Tauri: format, check, warnings-denied Clippy, 75 tests passed with 2 owner-provisioned artifact tests intentionally ignored, release build, and NSIS bundle passed.
- Backend: focused AssistantContext, security-negative, model-chat lifecycle, and complete model-gateway suites passed, including deterministic `temperature: 0` request construction.
- Installed semantic acceptance: all 15 prompts passed semantically with 0 critical capability-truth failures using the approved bootstrap model.
- Installed regression: 30-message conversation, long streaming, manual scroll stability, mouse/keyboard/drag scrolling, reachable composer, Stop with immutable partial output, retry, restart, Settings, preference persistence, clean shutdown, and per-user uninstall/reinstall passed.
- Uninstall removed only installer-owned files, shortcuts, and registration. It preserved the approved runtime (`3a8aea5f…6b59fb`) and model (`6a1a2eb6…9407e`) bytes; reinstall restored the application and another real response.
````

### ПУТЬ: docs/work-packages/up02/UP02-WP01_TRUTHFUL_ASSISTANT_AND_USABILITY.md (48 строк, 4814 байт)

````markdown
# UP02-WP01 — Truthful Assistant and Usability

## Objective

Make the local text assistant identify its LocalComet operating context, follow the selected interface locale by default, and refuse to claim capabilities that the current desktop application does not provide. Improve the existing chat state guidance without changing the product architecture or restoring unfinished product areas.

This work is stacked on UP05-WP01-R2-HF1 at `ee221944eca092580e333b804f4e408a89a0bc76`.

## User-visible problem

The approved bootstrap model currently receives only the user message on the managed minimal harness. It can therefore guess its identity, capability set, project knowledge, and preferred language. The chat also leaves a ready-but-empty conversation visually blank, exposes technical lifecycle words on assistant messages, and does not summarize capability boundaries in Settings.

## Relevant implementation discovered

| Concern | Current source | Current behaviour | Minimum change |
| --- | --- | --- | --- |
| Frontend turn request | `src/lib/bridge/modelGateway.ts` and `src/lib/stores/modelGateway.ts` | Sends IDs, model, timestamp, token limit, prompt, and binding fingerprint | Add the existing `ru`/`en` locale as a validated enum |
| Trusted desktop boundary | `src-tauri/src/control_plane.rs` | Validates the Tauri command and forwards an exact payload | Construct the immutable application/capability context here |
| Provider message assembly | `modules/local_model_gateway_ru.py` | Minimal harness sends `[user]`; native harness has a legacy static system message | Validate the trusted context and deterministically send `[system, user]` for every ordinary turn |
| Locale source | `src/lib/i18n/index.ts` via versioned UI preferences | `locale` is `ru` or `en` and persists through Settings | Snapshot the current locale for each turn; do not mutate it from model output |
| Readiness | model gateway, managed runtime, inference stores | Control Plane, runtime/model, and request lifecycle are separate stores | Preserve separation and improve localized labels/guidance |
| Empty state | `MessageList.svelte` | Only disconnected/no-message state is rendered; ready/no-message is blank | Add bounded unavailable, loading, and ready first-use copy |
| Request state | `MessageList.svelte` and `MessageComposer.svelte` | Non-completed assistant state is a raw technical string | Add localized lifecycle text and a bounded retry action for failed/timed-out turns |
| Capability summary | `SettingsPanel.svelte` | About shows only version/build values | Add read-only available/unavailable lists; no toggles |
| Installer | `tools/build_up00_windows_installer.py` | Builds the existing offline per-user NSIS package | Reuse only after source verification passes |

The current ordinary request message order is one `user` message. UP02 changes it to one deterministic trusted `system` message followed by the unchanged `user` message. Neither trusted context nor the system instruction is added to the rendered transcript.

## UI state model

- Model unavailable: send is disabled and the existing model-connect action is visible.
- Runtime/model validating or loading: send is disabled and bounded progress wording is shown without claiming readiness.
- Model ready: send is enabled when input is non-empty; the first-use state explains local chat and current capability limits.
- Request streaming: progressive text and Stop remain visible.
- Request failed or timed out: streaming stops, a localized safe explanation and retry action are shown.
- Request cancelled: partial text is preserved, cancellation is explicit, and a subsequent request remains possible.

Control Plane connection, managed runtime/model readiness, and request generation remain independently derived. The existing HF1 bounded transcript, near-bottom follow behaviour, keyboard scrolling, and reachable composer are preserved.

## Scope

Included: typed trusted assistant context, deterministic system instruction, locale transmission, chat-state wording, first-use guidance, read-only capability summary, tests, documentation, existing offline installer rebuild, and regression acceptance.

Excluded: internet, email, browser, files, Vault, RAG, Computer Use, shell, tools, cloud inference, API keys, model downloads, autonomous action, generic IPC, navigation redesign, and unrelated Agent/Browser/Computer Use source.

## Product limitations

The assistant is a probabilistic local model. The application supplies deterministic context and verifies behaviour semantically, but it cannot promise perfect wording. Project-specific context is unavailable in this package; users can paste or describe information in the chat, but LocalComet does not inspect their repository, files, or Vault for ordinary responses.
````

### ПУТЬ: docs/work-packages/up05/UP05-WP00_APPROVED_CATALOG_SCHEMA.md (136 строк, 4858 байт)

````markdown
# UP05-WP00 Approved Artifact Catalog Schema

<!-- Canonical schema documentation. -->

Catalog path:

desktop/localcomet-desktop/src-tauri/resources/localcomet/approved-artifacts.v1.json

Published identity:

- schema version: 1
- catalog ID: `localcomet-approved-artifacts`
- catalog version: `1.0.0`
- exact catalog-byte SHA-256: `e50530563403c5e750205581576bcaf108daf08d05223d91b4ed31e107a8b33c`

## Top-level schema

- schema_version: integer, exactly 1
- catalog_id: exactly localcomet-approved-artifacts
- catalog_version: bounded non-empty version identifier
- runtimes: sorted by runtime_id
- models: sorted by model_id

Unknown keys and duplicate JSON keys are rejected.

## Runtime entry

Required fields:

- runtime_id
- provider
- release_tag
- platform
- architecture
- variant
- upstream_repository
- upstream_revision
- asset_filename
- asset_bytes
- asset_sha256
- archive_format
- managed_relative_path
- executable_relative_path
- required_files
- permitted_bind_scope
- supported_api_protocol
- license_id
- public_distribution
- status

required_files entries contain a safe package-relative path, positive byte count, and lowercase SHA-256. Paths are unique under Windows case folding and sorted. The executable must be present in required_files.

WP00 permits only Windows, x86-64, CPU, ZIP, loopback-only, OpenAI-compatible-v1, non-public approved entries.

## Model entry

Required fields:

- model_id
- provider
- family
- display_name
- format
- quantization
- upstream_repository
- upstream_revision
- asset_filename
- asset_bytes
- asset_sha256
- license_id
- compatible_runtime_ids
- managed_relative_path
- public_distribution
- installer_bundled
- bootstrap_purpose
- status

compatible_runtime_ids are unique, sorted, non-empty, and must reference runtime IDs in the same catalog. WP00 permits only GGUF, non-public, non-installer-bundled, explicitly approved internal bootstrap entries.

## IDs

IDs match a bounded lowercase ASCII grammar:

- first character: a-z or 0-9
- remaining characters: a-z, 0-9, period, underscore, or hyphen
- total length: 3 through 96 bytes

IDs do not contain paths and are never derived from private paths.

## Hashes and sizes

Every SHA-256 is exactly 64 lowercase hexadecimal characters. Artifact size and required-file sizes are positive unsigned integers. Model and archive artifact hashes are over exact raw upstream bytes.

The source catalog digest is SHA-256 over exact canonical catalog file bytes. It is evidence, not a semantic or self-referential hash field inside the catalog.

Approved runtime pin:

- ID: `llama-cpp-windows-x86-64-cpu-bootstrap`
- release/revision: `b10068` / `571d0d540df04f25298d0e159e520d9fc62ed121`
- asset/bytes: `llama-b10068-bin-win-cpu-x64.zip` / 18,007,324
- SHA-256/license: `01d5f30876acfb4a0be59396710f450213495c7181d8fbcce2fad045835ceb89` / MIT

Approved model pin:

- ID: `qwen2.5-1.5b-instruct-q4-k-m`
- repository/revision: `Qwen/Qwen2.5-1.5B-Instruct-GGUF` / `91cad51170dc346986eccefdc2dd33a9da36ead9`
- asset/bytes: `qwen2.5-1.5b-instruct-q4_k_m.gguf` / 1,117,320,736
- SHA-256/license: `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e` / Apache-2.0

## Paths and filenames

Catalog paths use relative forward-slash components only. Validation rejects:

- absolute and UNC paths;
- Windows drive-relative forms;
- backslashes;
- dot and dot-dot components;
- empty components;
- NUL;
- paths outside the required runtime/model prefix;
- case-fold collisions;
- executable paths outside the runtime package.

Asset filenames are basenames only. Duplicate artifact filenames mapped to conflicting managed locations are rejected.

## Installed state

WP00 creates no persistent installed inventory. Installed state is a live derived projection over catalog-declared managed paths, current byte counts, hashes, file format, containment, and compatibility. Therefore an AppData file cannot add approval, and missing, corrupt, stale-digest, traversal-bearing, or unknown-ID inventory content is inert.

Any future cache remains non-authoritative. It must be written through a sibling temporary file, schema-validated, flushed and closed, atomically replaced on Windows, reread, and exactly post-write validated. Every read must reconcile catalog ID/version/digest, known artifact IDs, relative containment, current bytes, and current SHA-256. Failure preserves the previous valid cache; deletion causes safe live reconstruction.

## Safe projections

Frontend responses may include stable IDs, display/version/platform/architecture/format/quantization, artifact filename, expected bytes/SHA-256, `license_id`, status, compatibility IDs, validation status, verified time, and catalog identity/digest.

They never include resolved absolute paths, URLs, executable arguments, environment, credentials, or approval mutation controls.
````

### ПУТЬ: docs/work-packages/up05/UP05-WP00_MANAGED_ARTIFACT_TRUST_CONTRACT.md (140 строк, 8161 байт)

````markdown
# UP05-WP00 Managed Artifact Trust Contract

<!-- Source-controlled trust decision. -->

Status: implementation, bounded acquisition, managed provisioning, direct inference, and rollback rehearsal complete.

Depends on UP01-WP01 at 0467cf71e1cf0e0400d687c1829e7bd0de91eebc. Completion unblocks UP05-WP01 model/chat reliability work; it does not complete chat reliability itself.

## Trust root

LocalComet approval authority consists only of:

1. the reviewed source file desktop/localcomet-desktop/src-tauri/resources/localcomet/approved-artifacts.v1.json;
2. the strict Rust parser and validator compiled into the packaged desktop application;
3. the packaged LocalComet application that embeds the exact catalog bytes;
4. exact lowercase SHA-256 identities over raw upstream artifact bytes.

The catalog is immutable at runtime. Frontend, model output, Python sidecar, AppData, installed inventory, and local files cannot add or override approval. Updating approval requires a source commit, review, new application build, and installer.

## Catalog versus installed state

The catalog answers what may be trusted. Installed state answers whether an approved artifact is currently present and byte-valid.

Installed state is derived live from catalog-declared relative paths under the source-grounded LocalComet per-user roots:

- runtimes/llama.cpp below the LocalComet application-data root;
- models below the LocalComet application-data root;
- runtime-state for private ephemeral process state only.

WP00 deliberately does not create a persistent installed-artifacts cache. Live derived snapshots avoid a second state file, remain reconstructible, and prevent AppData from becoming approval authority. A future cache may be added only under the mission's non-authoritative reconciliation rules.

If a future non-authoritative cache is introduced, each update must use a sibling temporary file, validate its schema and catalog references, flush and close the file, atomically replace the prior file using a Windows-supported operation, reread the result, and validate the exact post-write bytes. Failure must preserve the previous valid cache. Every read must still reconcile the cache with the embedded catalog digest and current artifact bytes; deleting or corrupting it must cause safe live reconstruction.

## Resolution chain

Every managed launch must resolve:

stable model ID
→ approved model catalog entry
→ exact contained managed model path
→ byte count, SHA-256, and GGUF validation
→ approved compatible runtime ID
→ exact contained runtime package
→ required file byte counts and SHA-256
→ fixed LocalComet launch policy

Raw frontend paths, arbitrary AppData records, arbitrary executables, and arbitrary arguments are never inputs to this chain.

## Canonical identity

Artifact IDs are explicit lowercase ASCII identifiers, unique by kind and immutable after publication.

Bootstrap IDs:

- llama-cpp-windows-x86-64-cpu-bootstrap
- qwen2.5-1.5b-instruct-q4-k-m

The schema version is 1. The catalog is UTF-8 without BOM, LF-only, deterministically ordered, duplicate-key-free, without trailing whitespace, with exactly one terminal newline. Its exact byte digest is:

`e50530563403c5e750205581576bcaf108daf08d05223d91b4ed31e107a8b33c`

Artifact hashes are SHA-256 over exact raw upstream artifact bytes. Extracted runtime file hashes are separately pinned as required-file identities.

## Managed containment

Catalog paths are relative and use forward-slash components. Validation rejects absolute paths, drive-relative paths, backslashes, empty components, dot components, traversal, NUL, reparse points, and paths outside the approved root after resolution.

Runtime executable identity is catalog-controlled and must remain within its approved runtime package. Model identity must remain within the model root and must satisfy exact size, SHA-256, .gguf extension, and GGUF magic checks.

## Typed read-only contract

Tauri exposes only bounded safe projections:

- approved runtime catalog;
- approved model catalog;
- live validated installed artifact statuses;
- one artifact validation status by stable ID;
- one model compatibility/readiness result by stable model ID.

No typed command accepts catalog JSON, paths, URLs, commands, environment variables, approval flags, or inventory writes. Existing managed start continues to accept only a stable model ID and revalidates the full chain in Rust.

## Approval update process

1. Resolve one owner-authorized artifact from its official upstream.
2. Download outside the repository and Vault.
3. Validate source identity, bytes, SHA-256, format/archive safety, and license.
4. Add exact metadata to the canonical catalog in stable ID order.
5. Run strict schema, canonical serialization, path, compatibility, and negative-security tests.
6. Review and commit source.
7. Build a new application/installer before the approval can take effect.
8. Provision the exact pinned bytes only into catalog-declared application-owned paths.

No runtime automatic download is added.

## Approved bootstrap record

Runtime:

- upstream: `ggml-org/llama.cpp`;
- release and revision: `b10068` / `571d0d540df04f25298d0e159e520d9fc62ed121`;
- asset: `llama-b10068-bin-win-cpu-x64.zip`, 18,007,324 bytes;
- SHA-256: `01d5f30876acfb4a0be59396710f450213495c7181d8fbcce2fad045835ceb89`;
- license: MIT;
- package identity: 31 exact required files, including the approved executable and DLL set.

Model:

- upstream: `Qwen/Qwen2.5-1.5B-Instruct-GGUF`;
- revision: `91cad51170dc346986eccefdc2dd33a9da36ead9`;
- asset: `qwen2.5-1.5b-instruct-q4_k_m.gguf`, 1,117,320,736 bytes;
- SHA-256: `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`;
- format/quantization/license: GGUF / Q4_K_M / Apache-2.0.

Both artifacts were acquired from their official upstreams, validated before catalog publication, and provisioned by same-volume atomic placement into their catalog-declared LocalComet-owned locations. Post-placement discovery reports both as catalog-approved, installed, hash-valid, contained, mutually compatible, and launchable. No runtime or model bytes were committed or added to installer resources.

## Acceptance outcome

The approved runtime loaded the approved model on loopback and returned `AI` in a real streaming inference. Load-to-listen was 0.953 seconds; first non-empty content arrived after 114.378 milliseconds; total inference time was 123.099 milliseconds. The stream contained three JSON SSE chunks, one non-empty content chunk, and exactly one `[DONE]`. Peak working set was 1,749,966,848 bytes. Graceful Ctrl+C shutdown completed with no owned or orphan runtime process.

Frontend tests passed 211/211; Svelte check completed with zero errors and one pre-existing warning; the production frontend build passed. Rust formatting, check, warnings-denied clippy, all tests, the 55.05-second provisioned-artifact test, and the offline locked release build in 1 minute 10 seconds passed. Python compilation, the v6.84.5.1 managed-runtime checks, and the clean-room model-gateway check passed. Source reverse-apply and physical same-volume artifact move/absence/restore rollback checks passed.

The broader fast stability gate reported 17/19: its two failures are legacy checks in untouched control-panel code. All WP00-affected checks passed.

## Explicit non-authorities

The following cannot approve an artifact:

- AppData files or caches;
- filenames or filesystem metadata;
- model output;
- frontend state;
- Python sidecar responses;
- local HTTP responses;
- process existence or port availability;
- unsigned URLs, redirects, ETags, or archive listings;
- installer presence without exact catalog validation.

## Bootstrap limitations

The Qwen bootstrap model is for internal inference validation, Russian/English smoke tests, and protocol verification. It is not a production default, public-distribution payload, installer payload, automatic-download target, recommendation for every machine, quality baseline, or performance baseline. UP05-WP01 remains responsible for LocalComet chat reliability; WP00 does not declare that work complete.
````

### ПУТЬ: docs/work-packages/up05/UP05-WP00_PR_BODY.md (47 строк, 3345 байт)

````markdown
# UP05-WP00 PR Body

<!-- Source-controlled WP00 review record. -->

## Summary

Implemented a source-controlled immutable Approved Artifact Catalog, strict Rust validation, live non-authoritative installed-state derivation, and typed read-only frontend projections. Pinned, provisioned, and validated one internal llama.cpp CPU runtime and one Qwen2.5 1.5B Q4_K_M bootstrap model without committing or bundling their bytes.

This file is the retrospective source-controlled review record. No remote pull request was opened.

## Trust decision

Approval is reviewed source authority. AppData cannot approve artifacts. Managed launch resolves stable model ID through catalog, exact model validation, compatibility, exact runtime validation, and fixed contained launch policy.

## Scope

- canonical catalog resource and digest
- Rust parser/schema/path/hash/compatibility validator
- live installed status and managed launch integration
- read-only Tauri/frontend contract
- focused security and consumer tests
- bounded official acquisition/provisioning
- direct real inference and cleanup evidence
- WP00 documentation and rollback

## Explicit exclusions

No automatic download, cloud provider, model library redesign, installer payload, public distribution, generic raw IPC, generic shell, arbitrary filesystem access, telemetry, Vault access, RAG, tools/agents, UP06–UP10, or UP05 chat lifecycle completion.

## Validation

Catalog schema 1 passed with exact digest `e50530563403c5e750205581576bcaf108daf08d05223d91b4ed31e107a8b33c`.

Pinned artifacts:

- runtime ID `llama-cpp-windows-x86-64-cpu-bootstrap`: llama.cpp `b10068`, revision `571d0d540df04f25298d0e159e520d9fc62ed121`, `llama-b10068-bin-win-cpu-x64.zip`, 18,007,324 bytes, SHA-256 `01d5f30876acfb4a0be59396710f450213495c7181d8fbcce2fad045835ceb89`, MIT;
- model ID `qwen2.5-1.5b-instruct-q4-k-m`: `Qwen/Qwen2.5-1.5B-Instruct-GGUF`, revision `91cad51170dc346986eccefdc2dd33a9da36ead9`, `qwen2.5-1.5b-instruct-q4_k_m.gguf`, 1,117,320,736 bytes, SHA-256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`, Apache-2.0.

Direct inference passed on loopback with output `AI`: 0.953 seconds load-to-listen, 114.378 milliseconds to first content, 123.099 milliseconds total, three JSON SSE chunks, one non-empty content chunk, exactly one `[DONE]`, and peak working set 1,749,966,848 bytes. Graceful Ctrl+C shutdown left no orphan process.

Frontend tests passed 211/211; Svelte check had zero errors and one pre-existing warning; production build passed. Rust fmt/check/clippy/all tests passed, including the 55.05-second installed-production test; the offline locked release build passed in 1 minute 10 seconds. Python compilation, v6.84.5.1 managed-runtime regression, and clean-room model-gateway regression passed. Negative authority tests and both source and physical managed-artifact rollback rehearsals passed.

The supplemental fast stability gate reported 17/19 because two legacy checks fail in untouched control-panel code. All WP00-affected checks passed. Evidence retains this limitation explicitly.

## Review notes

The bootstrap model is internal validation material only, not a public-distribution or installer payload and not a production performance baseline. Full LocalComet chat reliability resumes in UP05-WP01; WP00 does not claim it complete.
````

### ПУТЬ: docs/work-packages/up05/UP05-WP00_ROLLBACK.md (48 строк, 2783 байт)

````markdown
# UP05-WP00 Rollback

<!-- Rollback preserves unrelated user-owned artifacts and data. -->

## Source rollback

The branch is stacked directly on UP01-WP01 base 0467cf71e1cf0e0400d687c1829e7bd0de91eebc. Reviewable WP00 commits may be reverted in reverse order. A clean branch reset/recreation at the exact base restores the predecessor tree without touching main.

Rehearsal result: PASS. The complete feature patch and the catalog-only patch both passed reverse-apply checks against the exact base. `main` and `origin/main` remained unchanged.

## Managed artifact rollback

Rollback records exact PRE01/WP00-created relative destinations. Remove only the catalog-declared bootstrap model file and the exact bootstrap runtime package directory after revalidating their identities. Never scan or delete unrelated models/runtimes.

If a destination does not match the WP00 created-file manifest, stop rather than deleting it.

## Derived state

WP00 uses live derived installed status and creates no persistent trusted inventory. Ephemeral runtime-state credentials remain owned by the managed supervisor and are deleted on stop. A missing runtime-state directory requires no restoration.

A future optional cache must remain non-authoritative and must use a sibling temporary file, schema validation, flush and close, Windows-supported atomic replacement, reread, and exact post-write validation. Failure preserves the prior valid cache. Current WP00 state needs no cache rollback: deleting, corrupting, or inventing inventory content cannot approve anything, and live validation reconstructs state from catalog-declared bytes.

## Preservation

Rollback must preserve:

- unrelated models and runtimes;
- LocalComet settings and user data;
- repository work outside WP00;
- main and origin/main;
- the Obsidian Vault;
- external evidence and upstream pin records unless the owner explicitly removes them.

## Completed rehearsal

The bounded rehearsal passed:

- only the exact catalog-declared runtime ID `llama-cpp-windows-x86-64-cpu-bootstrap` and model ID `qwen2.5-1.5b-instruct-q4-k-m` destinations were selected;
- both destinations were moved aside using same-volume operations without deleting their bytes;
- the absence state was observed while unrelated managed content and user data remained present;
- both destinations were restored to their original catalog-declared locations;
- live installed state reconstructed without a persistent inventory;
- restored bytes, hashes, containment, compatibility, and launchability validated successfully;
- no owned runtime process remained;
- no model/runtime bytes entered Git or installer resources;
- the Obsidian Vault was neither read nor modified.

Rollback result: PASS. The successful feature state was restored cleanly.
````

### ПУТЬ: docs/work-packages/up05/UP05-WP00_TEST_AND_ACCEPTANCE_PLAN.md (97 строк, 6625 байт)

````markdown
# UP05-WP00 Test and Acceptance Plan

<!-- Bounded acceptance plan and completed result for WP00 only. -->

Status: WP00-affected acceptance checks passed. The broader fast stability gate reported 17/19 because of two legacy checks in untouched control-panel code; those results are retained rather than misreported as WP00 regressions.

Catalog under test: schema 1, digest `e50530563403c5e750205581576bcaf108daf08d05223d91b4ed31e107a8b33c`.

## Static catalog validation

Test canonical UTF-8/LF serialization, exact schema version/catalog identity, duplicate JSON keys, unknown keys, sorted unique IDs, bounded ID grammar, required fields, lowercase SHA-256, positive bytes, platform/architecture/variant, internal distribution flags, safe filenames, relative paths, case-fold collisions, runtime file identities, and compatibility references.

## Live installed validation

Using isolated temporary roots:

- exact runtime package is valid;
- exact GGUF is valid;
- missing artifact is unavailable;
- unknown artifact is rejected;
- size mismatch is rejected before trust;
- hash mismatch is rejected;
- invalid GGUF magic is rejected;
- absolute, drive-relative, traversal, backslash, and reparse paths are rejected;
- runtime/model incompatibility is rejected;
- unapproved neighboring files never enter approved projections;
- mutable AppData cannot add approval.

Persistent installed inventory is intentionally omitted. Every status is derived from the embedded catalog and current bytes.

Result: PASS in isolated roots and against the provisioned production artifacts. The production discovery test completed in 55.05 seconds and found the approved runtime/model installed, byte-valid, hash-valid, contained, compatible, and launchable. Unknown, tampered, path-escaping, incompatible, and AppData-claimed artifacts failed closed.

## Typed contract

Verify approved runtime/model lists, validated installed lists, one-ID status, and model readiness commands. Frontend validation must reconstruct safe metadata, reconcile catalog digest, reject malformed/extra/path-bearing fields, and expose no mutation method.

Managed runtime start accepts only a stable model ID and repeats the complete Rust validation chain immediately before launch.

Result: PASS. The frontend consumes five fixed read-only trust commands, reconstructs closed safe objects, reconciles the catalog digest, derives installation state separately from approval, and obtains fresh readiness before stable-ID start. No approval/catalog/inventory mutation command is exposed.

## Bootstrap acquisition

Record exact official source/revision, final URL, bytes, SHA-256, UTC time, license, archive members, CRC, safe paths, collisions, links/reparse flags, executable, and required DLLs. Validate only the exact Q4_K_M GGUF and CPU runtime.

Result: PASS.

- Runtime: `ggml-org/llama.cpp`, `b10068`, revision `571d0d540df04f25298d0e159e520d9fc62ed121`, `llama-b10068-bin-win-cpu-x64.zip`, 18,007,324 bytes, SHA-256 `01d5f30876acfb4a0be59396710f450213495c7181d8fbcce2fad045835ceb89`, MIT, acquired `2026-07-20T11:42:55.7121149Z`.
- Model: `Qwen/Qwen2.5-1.5B-Instruct-GGUF`, revision `91cad51170dc346986eccefdc2dd33a9da36ead9`, `qwen2.5-1.5b-instruct-q4_k_m.gguf`, 1,117,320,736 bytes, SHA-256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`, Apache-2.0, acquired `2026-07-20T11:43:27.1950378Z`.

The runtime archive passed CRC and member-safety checks and yielded exactly 31 catalog-required files. The model passed exact-size, SHA-256, GGUF magic, source, and Q4_K_M identity checks. Both were provisioned to their catalog-declared managed locations without collision; no acquired bytes entered Git or installer resources.

## Runtime acceptance

Run the approved executable only, loopback-only, with fixed LocalComet-compatible arguments. Require version identity, GGUF load, readiness, one real non-empty response, one terminal completion, clean shutdown, and zero owned orphan processes. Record load, first-token, total duration, chunk count, and bounded peak memory when available.

Result: PASS. Load-to-listen was 0.953 seconds. First non-empty content arrived at 114.378 milliseconds and total inference completed in 123.099 milliseconds. The observed output was `AI`; the stream contained three JSON SSE chunks, one non-empty content chunk, and exactly one `[DONE]`. Peak working set was 1,749,966,848 bytes. Graceful Ctrl+C shutdown left no owned or orphan `llama-server` process.

## Repository checks

Frontend:

- `npm test`: PASS, 211/211 tests
- `npm run check`: PASS, zero errors and one pre-existing warning
- `npm run build`: PASS
- typed managed-artifact and model-gateway consumer/component tests: PASS

Rust/Tauri:

- `cargo fmt --check`: PASS
- `cargo check`: PASS
- `cargo clippy --all-targets -- -D warnings`: PASS
- all Rust tests and focused catalog/inventory/typed-command tests: PASS
- owner-provisioned production discovery test: PASS in 55.05 seconds
- offline locked release build: PASS in 1 minute 10 seconds

Python/backend:

- `py_compile` for the changed Python test: PASS
- v6.84.5.1 managed-runtime regression: PASS
- clean-room model-gateway regression: PASS
- direct runtime/model acceptance and cleanup: PASS

Repository-wide supplemental gate:

- fast stability: 17/19; two failures are legacy checks in untouched `LocalComet_Control_Panel.py` code, while every WP00-affected check passed

## Negative authority checks

Prove no generic raw IPC, shell, arbitrary file read, arbitrary process launch, approval mutation, runtime automatic download, telemetry, cloud inference, Vault access, installer model payload, or public/LAN binding was introduced.

Result: PASS. Tests also covered unknown IDs, byte/hash mismatch, incompatibility, absolute/drive-relative/traversal/reparse paths, corrupt/stale/traversal inventory claims, unexpected runtime files, bad GGUF magic, source-only approval, fresh readiness, loopback listener ownership, and held launch identities. The Obsidian Vault was neither read nor modified.

## Rollback acceptance

Source reverse-apply checks against exact base `0467cf71e1cf0e0400d687c1829e7bd0de91eebc` passed. The catalog diff reversed cleanly. The exact managed runtime and model destinations were moved aside on the same volume, observed absent, and restored; unrelated managed content and user data were preserved. Live state reconstructed after restoration and exact validation returned to the successful feature state.

UP05-WP00 establishes the trust/provisioning bootstrap only. UP05-WP01 chat reliability remains incomplete and is the next work package.
````

