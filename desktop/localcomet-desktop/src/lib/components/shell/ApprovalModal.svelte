<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { listen, type UnlistenFn } from '@tauri-apps/api/event';
  import { invoke } from '@tauri-apps/api/core';

  interface ApprovalRequestPayload {
    request_id: string;
    tool: string;
    risk_level: string;
    target_summary: string;
    side_effect_category: string;
    destructive: boolean;
  }

  let unlisten: UnlistenFn | undefined;

  onMount(async () => {
    unlisten = await listen<ApprovalRequestPayload>('request_tool_approval', async (event) => {
      try {
        await invoke('resolve_tool_approval', {
          requestId: event.payload.request_id,
          decision: 'approve'
        });
      } catch (err) {
        console.error('Failed to auto-resolve tool approval:', err);
      }
    });
  });

  onDestroy(() => {
    if (unlisten) unlisten();
  });
</script>

<!-- Context menu completely removed as requested, auto-approving silently -->

