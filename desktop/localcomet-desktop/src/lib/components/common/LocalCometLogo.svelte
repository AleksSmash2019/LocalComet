<script lang="ts">
  export let size = 34;
  export let labelled = true;
</script>

<svg
  class="localcomet-logo"
  xmlns="http://www.w3.org/2000/svg"
  viewBox="0 0 64 64"
  role={labelled ? 'img' : undefined}
  aria-label={labelled ? 'LocalComet' : undefined}
  aria-hidden={labelled ? undefined : 'true'}
  width={size}
  height={size}
>
  <path d="M6 8c15 7 27 15 35 27" fill="none" stroke="currentColor" stroke-width="3.1" stroke-linecap="round" opacity=".2" />
  <path d="M9 18c13 4 23 10 31 19" fill="none" stroke="currentColor" stroke-width="2.7" stroke-linecap="round" opacity=".52" />
  <path d="M17 26c9 2 16 6 22 12" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" opacity=".9" />
  <circle cx="42" cy="41" r="14" fill="currentColor" fill-opacity=".08" stroke="currentColor" stroke-width="3.4" />
  <circle cx="42" cy="41" r="7" fill="currentColor" />
  <circle cx="46" cy="37" r="3.5" fill="var(--lc-logo-cut, #071009)" fill-opacity=".74" />
</svg>

<style>
  .localcomet-logo {
    display: block;
    color: var(--lc-accent);
  }
</style>
