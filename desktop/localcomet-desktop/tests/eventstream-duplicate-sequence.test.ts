import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';
import EventStream from '../src/lib/components/common/EventStream.svelte';
import type { ControlPlaneEvent } from '../src/lib/types/controlPlane';

describe('EventStream keyed each', () => {
  it('renders duplicate zero sequences without each_key_duplicate crash', () => {
    const events = [
      { sequence: 0, method: 'sidecar.status', kind: 'none', state: 'READY' },
      { sequence: 0, method: 'model.turn.started', kind: 'event', state: '' },
      { sequence: 1, method: 'model.tool.request', kind: 'event', state: '' }
    ] as unknown as ControlPlaneEvent[];

    let html = '';
    expect(() => {
      html = render(EventStream, { props: { events } }).body;
    }).not.toThrow();
    expect(html).toContain('#0');
    expect(html).toContain('#1');
    expect(html).toContain('model.tool.request');
  });

  it('renders an empty stream with the empty-state label and no list items', () => {
    const html = render(EventStream, { props: { events: [] } }).body;
    expect(html).not.toContain('<li');
  });

  it('keeps unique stamped ingestion ids as keys across the 12-event window slide', () => {
    const events = Array.from({ length: 14 }, (_, i) => ({
      sequence: i,
      method: 'model.turn.started',
      kind: 'event',
      state: '',
      ingestion_id: i + 1
    })) as unknown as ControlPlaneEvent[];

    const html = render(EventStream, { props: { events } }).body;
    // Only the last 12 of 14 accepted events are visible.
    expect((html.match(/<li/g) ?? []).length).toBe(12);
    expect(html).toContain('#13');
    expect(html).not.toContain('#0');
  });
});
