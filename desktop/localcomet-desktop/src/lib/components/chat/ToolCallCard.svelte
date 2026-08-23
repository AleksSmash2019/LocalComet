<script lang="ts">
  import type { ToolCallMock } from '$lib/data/mockData';
  import { t } from '$lib/i18n';
  import { parseToolCallResult } from '$lib/tools/computerUseEnvelope';

  export let tool: ToolCallMock;
  const MAX_TOOL_IMAGE_BASE64_CHARS = 4_000_000;

  $: isWebTool = tool.operation === 'web.search' || tool.operation === 'web.fetch';
  $: isCU = tool.operation === 'computer_use';

  type ComputerUseSummary = {
    action: string;
    reason: string;
    stateKey: string;
    nextKey: string | null;
  };

  type ComputerUseEvidence = {
    requestId: string;
    actionId: string;
    approvalId: string;
    approvalCallId: string;
    inputDigest: string;
    screenshotSha256: string;
    screenshotBackend: string;
    screenshotScope: string;
    screenshotBytes: string;
    status: string;
    verification: string;
  };

  function evidenceString(value: unknown): string {
    return typeof value === 'string' ? value : '';
  }

  function computerUseEvidence(result: string | undefined): ComputerUseEvidence | null {
    if (!result) return null;
    try {
      const payload = JSON.parse(result) as Record<string, unknown>;
      const execution = typeof payload.execution === 'object' && payload.execution
        ? payload.execution as Record<string, unknown>
        : {};
      const screenshotBytes = execution.screenshot_bytes ?? payload.screenshot_bytes;
      return {
        requestId: evidenceString(payload.request_id),
        actionId: evidenceString(payload.action_id),
        approvalId: evidenceString(execution.approval_id ?? payload.approval_id),
        approvalCallId: evidenceString(execution.approval_call_id ?? payload.approval_call_id),
        inputDigest: evidenceString(execution.input_digest ?? payload.input_digest),
        screenshotSha256: evidenceString(execution.screenshot_sha256 ?? payload.screenshot_sha256),
        screenshotBackend: evidenceString(execution.capture_backend ?? payload.capture_backend),
        screenshotScope: evidenceString(execution.capture_scope ?? payload.capture_scope),
        screenshotBytes: typeof screenshotBytes === 'number' ? String(screenshotBytes) : '',
        status: evidenceString(execution.status ?? payload.status),
        verification: evidenceString(execution.verification ?? payload.verification)
      };
    } catch {
      return null;
    }
  }

  function shot(result: string | undefined): string | null {
    if (!result) return null;
    const source = String(result);
    const dataIndex = source.indexOf('data:image');
    if (dataIndex !== -1) {
      const end = source.indexOf('"', dataIndex);
      const candidate = end !== -1 ? source.slice(dataIndex, end) : source.slice(dataIndex, dataIndex + 2000);
      const payload = candidate.slice(candidate.indexOf(',') + 1);
      return payload.length <= MAX_TOOL_IMAGE_BASE64_CHARS ? candidate : null;
    }
    const base64Index = source.indexOf('base64,');
    if (base64Index !== -1) {
      const payload = source.slice(base64Index + 7).split(/[^A-Za-z0-9+/=]/)[0];
      if (payload.length > 200 && payload.length <= MAX_TOOL_IMAGE_BASE64_CHARS) return `data:image/png;base64,${payload}`;
    }
    const raw = source.trim();
    if (/^[A-Za-z0-9+/=]{500,}$/.test(raw) && raw.length <= MAX_TOOL_IMAGE_BASE64_CHARS) return `data:image/png;base64,${raw}`;
    return null;
  }

  function computerUseSummary(result: string | undefined): ComputerUseSummary | null {
    if (!result) return null;
    try {
      const payload = JSON.parse(result) as Record<string, unknown>;
      const execution = typeof payload.execution === 'object' && payload.execution ? payload.execution as Record<string, unknown> : {};
      const action = typeof payload.action === 'object' && payload.action ? payload.action as Record<string, unknown> : {};
      const status = String(payload.status ?? execution.status ?? '');
      const next = String(payload.next_decision ?? '');
      const actionName = String(action.kind ?? payload.mode ?? tool.target ?? '').replaceAll('_', ' ');
      // One shared classifier (same module as the gateway store) decides
      // pending/verified/blocked/failed; this component only renders it.
      const outcome = parseToolCallResult('computer_use', payload);
      const stateKey = outcome.kind === 'blocked' ? 'tool.state_blocked'
        : payload.requires_confirmation === true ? 'tool.state_confirmation'
        : outcome.kind === 'pending' || tool.status === 'WAITING' ? 'tool.state_waiting'
        : outcome.kind === 'verified_success' ? 'tool.state_completed'
        : outcome.kind === 'unverified_success' ? 'tool.state_unverified'
        : 'tool.state_unavailable';
      const nextKey = ({
        continue: 'tool.next_continue',
        replan: 'tool.next_replan',
        observe_again: 'tool.next_observe',
        ask_user: 'tool.next_ask_user',
        stop: 'tool.next_stop'
      } as Record<string, string>)[next] ?? null;
      return {
        action: actionName,
        reason: String(payload.reason ?? execution.reason ?? tool.detail ?? ''),
        stateKey,
        nextKey
      };
    } catch {
      return {
        action: tool.target || tool.operation,
        reason: tool.detail || '',
        stateKey: tool.status === 'WAITING' ? 'tool.state_waiting' : 'tool.state_unavailable',
        nextKey: null
      };
    }
  }

  $: src = isCU ? shot(tool.result) : null;
  $: cu = isCU ? computerUseSummary(tool.result) : null;
  $: cueEvidence = isCU ? computerUseEvidence(tool.result) : null;
</script>

<article
  class="tool-card tool-surface"
  aria-label={isCU ? $t('tool.computer_use') : isWebTool ? `${$t('tool.web_prefix')} ${tool.status}` : $t('tool.tools_disabled')}
  data-cu-request-id={cueEvidence?.requestId ?? ''}
  data-cu-action-id={cueEvidence?.actionId ?? ''}
  data-cu-approval-id={cueEvidence?.approvalId ?? ''}
  data-cu-approval-call-id={cueEvidence?.approvalCallId ?? ''}
  data-cu-input-digest={cueEvidence?.inputDigest ?? ''}
  data-cu-screenshot-sha256={cueEvidence?.screenshotSha256 ?? ''}
  data-cu-screenshot-backend={cueEvidence?.screenshotBackend ?? ''}
  data-cu-screenshot-scope={cueEvidence?.screenshotScope ?? ''}
  data-cu-screenshot-bytes={cueEvidence?.screenshotBytes ?? ''}
  data-cu-status={cueEvidence?.status ?? ''}
  data-cu-verification={cueEvidence?.verification ?? ''}
>
  <div class="tool-head">
    <div>
      <span class="eyebrow" class:computer-use={isCU}>{isCU ? $t('tool.computer_use_upper') : isWebTool ? (tool.operation === 'web.search' ? $t('tool.web_search_upper') : $t('tool.web_fetch_upper')) : $t('tool.runtime')}</span>
      <h2>{tool.operation}</h2>
    </div>
    <span class="status-pill" class:computer-use={isCU}><span class="status-dot" class:computer-use={isCU} class:disabled={tool.status === 'SKIPPED'}></span>{tool.status}</span>
  </div>

  {#if isCU && src}
    <div class="cu-shot"><img class="cu-img" src={src} alt={$t('tool.screenshot_preview')} loading="lazy" /></div>
  {/if}

  {#if isCU && cu}
    <dl class="cu-meta">
      <div><dt>{$t('tool.action')}</dt><dd>{cu.action}</dd></div>
      <div><dt>{$t('tool.state')}</dt><dd>{$t(cu.stateKey)}</dd></div>
      {#if cu.nextKey}<div><dt>{$t('tool.next_step')}</dt><dd>{$t(cu.nextKey)}</dd></div>{/if}
    </dl>
    {#if cu.reason}<p class="cu-reason">{cu.reason}</p>{/if}
  {:else if !isCU && !isWebTool}
    <dl>
      <div><dt>{$t('tool.target')}</dt><dd>{tool.target}</dd></div>
      <div><dt>{$t('tool.elapsed')}</dt><dd>{tool.elapsed}</dd></div>
    </dl>
  {:else if isWebTool}
    <div class="web-meta"><dt>{$t('tool.source')}</dt><dd class="mono">{tool.target}</dd></div>
  {/if}

  <details>
    <summary>{isWebTool || isCU ? $t('tool.view_result') : $t('tool.details')}</summary>
    {#if isCU && src}
      <p class="mono">[screenshot — preview above, {tool.result?.length ?? 0} chars]</p>
    {:else if !isCU}
      <p>{tool.detail}</p>
    {/if}
    {#if isWebTool && tool.result}
      <div class="web-result">
        <pre>{tool.result.slice(0, 4000)}</pre>
        {#if tool.result.length > 4000}<span class="truncated-note">{$t('tool.truncated')}</span>{/if}
      </div>
    {:else if !isCU}
      <pre>{tool.result}</pre>
    {/if}
  </details>
</article>

<style>
  .tool-card { padding: var(--lc-space-4); }
  .tool-head { display: flex; justify-content: space-between; gap: var(--lc-space-4); }
  .eyebrow, dt { color: var(--color-muted); font-size: 12px; font-weight: 700; }
  h2 { margin: var(--lc-space-1) 0 0; font-size: 16px; }
  dl { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--lc-space-4); margin: var(--lc-space-4) 0; }
  dd { margin: var(--lc-space-1) 0 0; font-family: var(--font-mono); overflow-wrap: anywhere; }
  summary { cursor: pointer; color: var(--color-muted); font-weight: 700; }
  p, pre { margin: var(--lc-space-3) 0 0; }
  pre { overflow-x: auto; border-radius: var(--lc-radius-sm); background: var(--color-code); color: var(--color-text); padding: var(--lc-space-3); font-family: var(--font-mono); }
  .web-meta { margin: var(--lc-space-3) 0; display: flex; flex-direction: column; gap: 2px; }
  .mono { font-family: var(--font-mono); font-size: 11px; overflow-wrap: anywhere; color: var(--lc-text); }
  .web-result pre { max-height: 320px; overflow-y: auto; }
  .truncated-note { display: block; margin-top: 6px; color: var(--lc-muted); font-size: 11px; }
  .status-dot.disabled { background: var(--lc-muted); }
  .eyebrow.computer-use { color: var(--lc-accent-strong); background: var(--lc-accent-dim); border-radius: 999px; padding: 1px 6px; }
  .status-dot.computer-use { background: var(--lc-accent); }
  .status-pill.computer-use { background: var(--lc-accent-dim); border: 1px solid color-mix(in srgb, var(--lc-accent) 40%, transparent); border-radius: 999px; }
  .cu-shot { margin: var(--lc-space-3) 0; }
  .cu-img { max-height: 240px; max-width: 100%; border: 1px solid var(--color-border); border-radius: 8px; object-fit: contain; display: block; }
  .cu-meta { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--lc-space-3); margin: var(--lc-space-3) 0 0; padding: var(--lc-space-3); border: 1px solid color-mix(in srgb, var(--lc-accent) 24%, var(--color-border)); border-radius: var(--lc-radius-sm); background: color-mix(in srgb, var(--lc-accent) 6%, transparent); }
  .cu-reason { margin-top: var(--lc-space-3); color: var(--lc-muted); font-size: 13px; line-height: 1.45; }
</style>
