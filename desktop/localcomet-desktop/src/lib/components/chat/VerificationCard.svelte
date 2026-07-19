<script lang="ts">
  import type { VerificationMock } from '$lib/data/mockData';

  export let item: VerificationMock;
</script>

<article class="verification card-surface" aria-label="Verification not run">
  <span class="status-pill"><span class="status-dot disabled"></span>{item.status}</span>
  <div>
    <h2>{item.label}</h2>
    <p>{item.detail}</p>
  </div>
</article>

<style>
  .verification {
    display: flex;
    align-items: flex-start;
    gap: var(--lc-space-4);
    padding: var(--lc-space-4);
  }

  h2,
  p {
    margin: 0;
  }

  h2 {
    font-size: 16px;
  }

  p {
    margin-top: var(--lc-space-1);
    color: var(--color-muted);
  }
</style>
