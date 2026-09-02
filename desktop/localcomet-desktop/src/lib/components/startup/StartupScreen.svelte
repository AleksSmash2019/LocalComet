<script lang="ts">
  import LocalCometLogo from '$lib/components/common/LocalCometLogo.svelte';
  import { t } from '$lib/i18n';

  interface Props {
    /** True when startup exceeded the bounded timeout: show the escape hatch. */
    timedOut?: boolean;
    /** Continue with limited functionality: hide the overlay. */
    onContinue?: () => void;
  }

  let { timedOut = false, onContinue }: Props = $props();
</script>

<svelte:head>
  <title>LocalComet</title>
  <meta name="application-name" content="LocalComet" />
  <meta name="theme-color" content="#09090b" />
</svelte:head>

<main class="startup-screen" aria-label="LocalComet startup">
  <div class="startup-mark" aria-hidden="true">
    <LocalCometLogo size={92} labelled={false} />
  </div>
  <h1>{$t('startup.title')}</h1>
  <p class="startup-subtitle">{$t('startup.subtitle')}</p>
  <p class="startup-status" aria-live="polite">
    <span class="startup-indicator" aria-hidden="true"></span>
    {$t('startup.status')}
  </p>
  {#if timedOut}
    <p class="startup-timeout" aria-live="polite">{$t('startup.timeout')}</p>
    <button type="button" class="startup-continue" onclick={() => onContinue?.()}>
      {$t('startup.continue')}
    </button>
  {/if}
</main>

<style>
  .startup-screen {
    position: fixed;
    inset: 0;
    z-index: 1000;
    display: grid;
    place-content: center;
    justify-items: center;
    gap: 6px;
    width: 100vw;
    height: 100vh;
    min-height: 100vh;
    overflow: hidden;
    background:
      radial-gradient(circle at 50% 42%, color-mix(in srgb, var(--lc-accent) 13%, transparent), transparent 34%),
      var(--lc-bg);
    color: var(--lc-text);
    text-align: center;
  }

  .startup-mark {
    display: grid;
    place-items: center;
    width: 124px;
    height: 124px;
    margin-bottom: 14px;
    border: 1px solid color-mix(in srgb, var(--lc-accent) 32%, var(--lc-line));
    border-radius: 32px;
    background: color-mix(in srgb, var(--lc-panel-solid) 88%, var(--lc-accent));
    box-shadow: 0 18px 54px color-mix(in srgb, var(--lc-accent) 14%, transparent);
  }

  h1 {
    margin: 0;
    font-size: clamp(26px, 4vw, 34px);
    font-weight: 720;
    letter-spacing: -0.04em;
  }

  .startup-subtitle,
  .startup-status {
    margin: 0;
    color: var(--lc-muted);
  }

  .startup-subtitle {
    font-size: 14px;
  }

  .startup-status {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    margin-top: 16px;
    font-size: 12px;
  }

  .startup-timeout {
    margin: 12px 0 0;
    max-width: 420px;
    font-size: 12px;
    color: var(--lc-muted);
  }

  .startup-continue {
    margin-top: 14px;
    padding: 8px 20px;
    border: 1px solid color-mix(in srgb, var(--lc-accent) 40%, var(--lc-line));
    border-radius: 10px;
    background: color-mix(in srgb, var(--lc-accent) 14%, transparent);
    color: var(--lc-text);
    font: inherit;
    font-size: 13px;
    cursor: pointer;
  }

  .startup-continue:hover,
  .startup-continue:focus-visible {
    background: color-mix(in srgb, var(--lc-accent) 24%, transparent);
    outline: none;
  }

  .startup-indicator {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--lc-accent);
    box-shadow: 0 0 0 4px color-mix(in srgb, var(--lc-accent) 15%, transparent);
    animation: startup-pulse 1.4s ease-in-out infinite;
  }

  @keyframes startup-pulse {
    50% { opacity: 0.42; transform: scale(0.78); }
  }

  @media (prefers-reduced-motion: reduce) {
    .startup-indicator { animation: none; }
  }
</style>
