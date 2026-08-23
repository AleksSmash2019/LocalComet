<script lang="ts">
  import StatusBadge from '$lib/components/common/StatusBadge.svelte';
  import TelemetryRow from '$lib/components/common/TelemetryRow.svelte';
  import {
    cancelLocalModelTurn,
    confirmBinding,
    discoverModels,
    modelGatewayStore,
    probeGateway,
    setGatewayHarness,
    setGatewayPortText,
    setSelectedModel,
    startLocalModelTurn
  } from '$lib/stores/modelGateway';
  import type { HarnessId } from '$lib/types/modelGateway';
  import { t } from '$lib/i18n';

  let prompt = '';
  $: portValid = /^\d+$/.test($modelGatewayStore.portText) && Number($modelGatewayStore.portText) >= 1024 && Number($modelGatewayStore.portText) <= 65535;
  $: canBind = portValid && Boolean($modelGatewayStore.selectedModelId);
  $: canStart = Boolean($modelGatewayStore.binding) && Boolean(prompt.trim()) && $modelGatewayStore.status !== 'Generating' && $modelGatewayStore.status !== 'Cancelling';
  $: canCancel = $modelGatewayStore.status === 'Generating' || $modelGatewayStore.status === 'Cancelling';
  $: statusTone =
    $modelGatewayStore.status === 'Bound' || $modelGatewayStore.status === 'Ready' || $modelGatewayStore.status === 'Completed'
      ? 'ready'
      : $modelGatewayStore.status === 'Failed' || $modelGatewayStore.status === 'Unavailable'
        ? 'danger'
        : $modelGatewayStore.status === 'Generating' || $modelGatewayStore.status === 'Probing' || $modelGatewayStore.status === 'Cancelling'
          ? 'info'
          : 'disabled';

  function onHarnessChange(event: Event) {
    const target = event.currentTarget as HTMLSelectElement;
    setGatewayHarness(target.value as HarnessId);
  }
</script>

<section class="model-panel card-surface" aria-label={$t('model.external_local_server')}>
  <header class="model-panel-header">
    <div>
      <p class="eyebrow">{$t('model.external_local_server')}</p>
      <h2>{$t('model.openai_compatible_local')}</h2>
    </div>
    <StatusBadge label={$modelGatewayStore.status} tone={statusTone} />
  </header>

  <div class="gateway-grid">
    <TelemetryRow label={$t('model.provider')} value="openai-compatible-local" mono />
    <TelemetryRow label={$t('model.host')} value="127.0.0.1" mono />
    <TelemetryRow label={$t('model.tools_executed')} value={$modelGatewayStore.toolsExecuted} tone="disabled" mono />
    <TelemetryRow label={$t('model.persistence')} value={$modelGatewayStore.persistence} tone="disabled" />
  </div>

  <div class="gateway-controls" aria-label={$t('model.gateway_controls')}>
    <label>
      <span>{$t('model.port')}</span>
      <input
        inputmode="numeric"
        pattern="[0-9]*"
        maxlength="5"
        value={$modelGatewayStore.portText}
        aria-invalid={!portValid}
        oninput={(event) => setGatewayPortText((event.currentTarget as HTMLInputElement).value)}
      />
    </label>
    <button type="button" disabled={!portValid || $modelGatewayStore.status === 'Probing'} onclick={() => void probeGateway()}>{$t('model.probe')}</button>
    <button type="button" disabled={!portValid || $modelGatewayStore.status === 'Probing'} onclick={() => void discoverModels()}>{$t('model.list_models')}</button>
  </div>

  <div class="gateway-controls" aria-label={$t('model.binding_controls')}>
    <label>
      <span>{$t('model.model')}</span>
      <select value={$modelGatewayStore.selectedModelId} onchange={(event) => setSelectedModel((event.currentTarget as HTMLSelectElement).value)}>
        <option value="">{$t('model.select_discovered')}</option>
        {#each $modelGatewayStore.models as model}
          <option value={model.model_id}>{model.model_id}</option>
        {/each}
      </select>
    </label>
    <label>
      <span>{$t('model.harness')}</span>
      <select value={$modelGatewayStore.harnessId} onchange={onHarnessChange}>
        <option value="minimal">{$t('model.harness_minimal')}</option>
        <option value="native-localcomet">{$t('model.harness_native')}</option>
      </select>
    </label>
    <button type="button" disabled={!canBind} onclick={() => void confirmBinding()}>{$t('model.confirm_binding')}</button>
  </div>

  <div class="fingerprint" aria-label={$t('model.binding_fingerprint')}>
    <span>{$t('model.fingerprint')}</span>
    <code>{$modelGatewayStore.binding?.binding_fingerprint ?? $t('model.binding_required')}</code>
  </div>

  <label class="prompt-box">
    <span>{$t('model.prompt')}</span>
    <textarea
      bind:value={prompt}
      rows="3"
      maxlength="12000"
      disabled={!$modelGatewayStore.binding || canCancel}
      placeholder={$modelGatewayStore.binding ? $t('model.local_prompt_placeholder') : $t('model.binding_prompt_placeholder')}
    ></textarea>
  </label>

  <div class="turn-actions">
    <button type="button" disabled={!canStart} onclick={() => void startLocalModelTurn(prompt)}>{$t('model.start')}</button>
    <button type="button" disabled={!canCancel} onclick={() => void cancelLocalModelTurn()}>{$t('model.cancel')}</button>
    <StatusBadge label={$modelGatewayStore.modelCalled ? $t('model.called_yes') : $t('model.called_no')} tone={$modelGatewayStore.modelCalled ? 'ready' : 'disabled'} />
  </div>

  {#if $modelGatewayStore.generatedText}
    <pre class="generated" aria-label={$t('model.generated_text')}>{$modelGatewayStore.generatedText}</pre>
  {/if}
  {#if $modelGatewayStore.lastError}
    <p class="gateway-error" role="status">{$modelGatewayStore.lastError.message}</p>
  {/if}
</section>

<style>
  .model-panel {
    display: grid;
    gap: 14px;
    padding: 16px;
    border-color: var(--lc-border-strong);
  }

  .model-panel-header,
  .gateway-controls,
  .turn-actions {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .model-panel-header {
    justify-content: space-between;
  }

  .eyebrow {
    margin: 0 0 3px;
    color: var(--lc-muted);
    font-family: var(--lc-mono);
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
  }

  h2 {
    margin: 0;
    font-size: 16px;
  }

  .gateway-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  label {
    display: grid;
    gap: 5px;
    min-width: 150px;
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 700;
  }

  input,
  select,
  textarea {
    min-height: 36px;
    border: 1px solid var(--lc-border);
    border-radius: 6px;
    background: var(--lc-panel-soft);
    color: var(--lc-text);
    font: inherit;
    padding: 8px 10px;
  }

  textarea {
    resize: vertical;
    min-height: 76px;
  }

  button {
    min-height: 36px;
  }

  .fingerprint {
    display: grid;
    gap: 5px;
    min-width: 0;
    color: var(--lc-muted);
    font-size: 12px;
    font-weight: 700;
  }

  code,
  .generated {
    overflow-wrap: anywhere;
    font-family: var(--lc-mono);
  }

  .generated {
    max-height: 180px;
    margin: 0;
    overflow: auto;
    white-space: pre-wrap;
    border: 1px solid var(--lc-border);
    border-radius: 6px;
    background: var(--lc-panel-soft);
    color: var(--lc-text);
    padding: 12px;
  }

  .gateway-error {
    margin: 0;
    color: var(--lc-danger);
    font-weight: 700;
  }

  @media (max-width: 720px) {
    .gateway-grid {
      grid-template-columns: 1fr;
    }

    label,
    .gateway-controls button {
      width: 100%;
    }
  }
</style>
