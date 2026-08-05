import { describe, expect, it } from 'vitest';
import {
  followTranscriptToEnd,
  isTranscriptNearBottom,
  transcriptDistanceFromBottom
} from '../src/lib/components/chat/transcriptScroll';

const sourceModules = import.meta.glob('../src/**/*.{css,svelte,ts}', {
  eager: true,
  query: '?raw',
  import: 'default'
}) as Record<string, string>;

function source(relativePath: string): string {
  const content = sourceModules[relativePath];
  if (typeof content !== 'string') throw new Error(`Source fixture not found: ${relativePath}`);
  return content;
}

describe('bounded chat layout', () => {
  it('closes the grid height chain and gives scrolling only to the transcript', () => {
    const css = source('../src/lib/components/shell/AppShell.svelte');
    expect(css).toMatch(/\.app-shell\s*\{[^}]*height:\s*100dvh;[^}]*overflow:\s*hidden;/s);
    expect(css).toMatch(/\.shell-body\s*\{[^}]*min-width:\s*0;[^}]*min-height:\s*0;[^}]*overflow:\s*hidden;/s);
    expect(css).toMatch(/\.main-workspace\s*\{[^}]*min-height:\s*0;[^}]*grid-template-rows:\s*auto minmax\(0, 1fr\) auto;[^}]*overflow:\s*hidden;/s);
    expect(css).toMatch(/\.chat-scroll\s*\{[^}]*min-height:\s*0;[^}]*overflow-y:\s*auto;[^}]*overflow-x:\s*hidden;[^}]*overscroll-behavior:\s*contain;/s);
  });

  it('keeps the truthful knowledge status and composer in one bounded footer grid item', () => {
    const composer = source('../src/lib/components/chat/MessageComposer.svelte');
    expect(composer).toContain('<div class="composer-region">');
    expect(composer).toMatch(/<div class="composer-region">\s*<form class="composer-wrap"/s);
    expect(composer).toContain('<KnowledgeToggle />');
    expect(composer).not.toContain('<KnowledgePreviewPanel />');
    expect(composer).toMatch(/\.composer-region\s*\{[^}]*min-width:\s*0;[^}]*min-height:\s*0;/s);
    expect(composer.match(/await restoreFocusAfterRequest\(\);/g)).toHaveLength(2);
    expect(composer).toContain('active === document.documentElement');
    expect(composer).toMatch(/if \(!textarea \|\| textarea\.disabled\) return;\s*restoreComposerFocus = false;/s);
    expect(composer).toMatch(/const generatingNow = isGenerating;\s*if \(previouslyGenerating && !generatingNow\)[\s\S]*previouslyGenerating = generatingNow;/);
  });

  it('keeps the owner-directed donor proportions and bubble geometry', () => {
    const messages = source('../src/lib/components/chat/MessageList.svelte');
    const composer = source('../src/lib/components/chat/MessageComposer.svelte');

    expect(messages).toMatch(/\.bubble\s*\{[^}]*max-width:\s*80%;[^}]*border-radius:\s*var\(--lc-radius-lg\);/s);
    expect(messages).toMatch(/\.user \.bubble\s*\{[^}]*background:\s*var\(--lc-accent\);/s);
    expect(composer).toMatch(/\.composer\s*\{[^}]*border-radius:\s*(?:var\(--lc-radius-lg\)|26px);[^}]*box-shadow:\s*var\(--lc-shadow-e1\);/s);
  });

  it.each([
    ['1920×1080', 1920, 1080, 1],
    ['1366×768', 1366, 768, 1],
    ['1280×720', 1280, 720, 1],
    ['1024×640', 1024, 640, 1],
    ['125% equivalent', 1280, 720, 1.25],
    ['150% equivalent', 1024, 640, 1.5]
  ])('keeps a bounded positive transcript viewport at %s', (_name, width, height, scale) => {
    const titleBar = 48 * scale;
    const header = 48 * scale;
    const composer = 118 * scale;
    expect(width / scale).toBeGreaterThanOrEqual(682);
    expect(height - titleBar - header - composer).toBeGreaterThan(300);
  });

  it('makes the transcript keyboard-focusable and records manual scroll position', () => {
    const shell = source('../src/lib/components/shell/AppShell.svelte');
    expect(shell).toContain('bind:this={transcriptViewport}');
    expect(shell).toContain('tabindex="0"');
    expect(shell).toContain('onscroll={recordTranscriptPosition}');
    expect(shell).toContain('onkeydown={handleTranscriptKeydown}');
    expect(shell).toContain('isTranscriptNearBottom(transcriptViewport)');
    expect(shell).toContain("event.key === 'PageUp'");
    expect(shell).toContain("event.key === 'PageDown'");
    expect(shell).toContain("event.key === 'Home'");
    expect(shell).toContain("event.key === 'End'");
  });
});

describe('near-bottom transcript follow policy', () => {
  it('treats a one-message non-overflowing transcript as at bottom', () => {
    expect(isTranscriptNearBottom({ scrollTop: 0, clientHeight: 600, scrollHeight: 240 })).toBe(true);
  });

  it('follows a long or streaming transcript only near its bottom', () => {
    expect(isTranscriptNearBottom({ scrollTop: 2304, clientHeight: 600, scrollHeight: 3000 })).toBe(true);
    expect(isTranscriptNearBottom({ scrollTop: 1200, clientHeight: 600, scrollHeight: 3000 })).toBe(false);
  });

  it('does not mutate manual upward scrolling while tokens arrive', () => {
    const viewport = { scrollTop: 1200, clientHeight: 600, scrollHeight: 3100 };
    expect(followTranscriptToEnd(viewport, isTranscriptNearBottom(viewport))).toBe(false);
    expect(viewport.scrollTop).toBe(1200);
    expect(transcriptDistanceFromBottom(viewport)).toBe(1300);
  });

  it('resumes following after the user returns to the bottom', () => {
    const viewport = { scrollTop: 2500, clientHeight: 600, scrollHeight: 3100 };
    expect(followTranscriptToEnd(viewport, isTranscriptNearBottom(viewport))).toBe(true);
    expect(viewport.scrollTop).toBe(3100);
  });
});
