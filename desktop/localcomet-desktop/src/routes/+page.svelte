<script lang="ts">
  import { onDestroy } from 'svelte';
  import AppShell from '$lib/components/shell/AppShell.svelte';
  import StartupScreen from '$lib/components/startup/StartupScreen.svelte';
  import { controlPlaneBridgeState } from '$lib/stores/controlPlane';
  import { modelGatewayStore } from '$lib/stores/modelGateway';

  // Bounded startup: a hung bridge/gateway invoke must never keep the
  // fixed-position splash overlay above the app forever. After
  // STARTUP_TIMEOUT_MS the user gets an explicit continue button.
  const STARTUP_TIMEOUT_MS = 20_000;
  let startupTimedOut = false;
  let dismissed = false;
  let startupTimer: ReturnType<typeof setTimeout> | undefined;

  startupTimer = setTimeout(() => {
    startupTimedOut = true;
  }, STARTUP_TIMEOUT_MS);
  onDestroy(() => clearTimeout(startupTimer));

  $: startupReady = $controlPlaneBridgeState !== 'CONNECTING' && $modelGatewayStore.initialized;
  $: if (startupReady && startupTimer !== undefined) {
    clearTimeout(startupTimer);
    startupTimer = undefined;
  }
</script>

<div class="page-root">
  <AppShell />
  {#if !startupReady && !dismissed}
    <StartupScreen timedOut={startupTimedOut} onContinue={() => (dismissed = true)} />
  {/if}
</div>

<style>
  .page-root {
    width: 100%;
    height: 100%;
  }
</style>
