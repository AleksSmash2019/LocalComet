<script lang="ts">
  export let size = 42;
  export let labelled = true;
</script>

<svg
  class="security-emblem"
  xmlns="http://www.w3.org/2000/svg"
  viewBox="0 0 220 250"
  role={labelled ? 'img' : undefined}
  aria-label={labelled ? 'LocalComet security emblem' : undefined}
  aria-hidden={labelled ? undefined : 'true'}
  width={size}
  height={Math.round(size * 1.14)}
>
  <path d="M110 16 190 46v66c0 57-32 96-80 122-48-26-80-65-80-122V46l80-30Z" fill="currentColor" fill-opacity=".035" stroke="currentColor" stroke-width="4" />
  <path d="M61 69c29 13 50 29 64 50" fill="none" stroke="currentColor" stroke-width="7" stroke-linecap="round" opacity=".27" />
  <path d="M68 89c24 8 42 21 55 37" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" opacity=".76" />
  <circle cx="126" cy="139" r="31" fill="currentColor" fill-opacity=".08" stroke="currentColor" stroke-width="5" />
  <circle cx="126" cy="139" r="15" fill="currentColor" />
  <circle cx="133" cy="132" r="7" fill="var(--lc-logo-cut, #071009)" fill-opacity=".72" />
</svg>

<style>
  .security-emblem {
    display: block;
    color: var(--lc-accent);
  }
</style>
