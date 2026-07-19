<script lang="ts">
  export let tone: StatusTone | string = 'unknown';
  export let label = 'Unknown';

  type StatusTone = 'ready' | 'info' | 'waiting' | 'danger' | 'disabled' | 'unknown';
</script>

<span class="status-dot {tone}" aria-hidden="true"></span>
<span class="sr-only">{label}</span>
