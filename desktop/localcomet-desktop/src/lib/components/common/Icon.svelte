<script lang="ts">
  export let name: string;
  export let size = 20;

  const paths: Record<string, string> = {
    add: '<path d="M12 5v14M5 12h14"/>',
    search: '<path d="m21 21-4.4-4.4"/><circle cx="11" cy="11" r="6"/>',
    chat: '<path d="M5 6h14v10H8l-3 3V6z"/>',
    tasks: '<path d="M9 6h11M9 12h11M9 18h11"/><path d="m4 6 1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2"/>',
    inspector: '<path d="M4 5h16v14H4z"/><path d="M8 9h8M8 13h5"/>',
    audit: '<path d="M6 3h9l3 3v15H6z"/><path d="M14 3v4h4M9 13l2 2 4-5"/>',
    project: '<path d="M4 7h16v11H4z"/><path d="M8 7V5h8v2"/>',
    run: '<path d="M7 5v14l11-7z"/>',
    model: '<circle cx="12" cy="12" r="7"/><path d="M12 5v14M5 12h14"/>',
    tool: '<path d="m14 6 4 4-8 8H6v-4z"/><path d="M12 8l4 4"/>',
    diag: '<path d="M5 18h14M7 14h10M9 10h6M11 6h2"/>',
    settings: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.09a2 2 0 0 1 1 1.74v.5a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.38a2 2 0 0 0-.73-2.73l-.15-.09a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    moon: '<path d="M20 14.5A7.5 7.5 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
    system: '<rect x="4" y="5" width="16" height="11" rx="2"/><path d="M9 20h6M12 16v4"/>',
    collapse: '<path d="m15 6-6 6 6 6"/>',
    expand: '<path d="m9 6 6 6-6 6"/>',
    menu: '<path d="M5 7h14M5 12h14M5 17h14"/>',
    attach: '<path d="m8 12 5.5-5.5a3 3 0 0 1 4.2 4.2L10 18.4a5 5 0 1 1-7-7l7.8-7.8"/>',
    send: '<path d="m4 4 16 8-16 8 4-8z"/><path d="M8 12h12"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    shield: '<path d="M12 3 5 6v6c0 4 3 7 7 9 4-2 7-5 7-9V6z"/>',
    cancel: '<path d="M6 6l12 12M18 6 6 18"/>',
    spark: '<path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z"/>',
    link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    refresh: '<path d="M23 4v6h-6"/><path d="M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>',
    play: '<polygon points="5 3 19 12 5 21 5 3"/>',
    stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>'
  };
</script>

<svg
  class="lc-icon"
  aria-hidden="true"
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="2"
  stroke-linecap="round"
  stroke-linejoin="round"
>
  {@html paths[name] ?? paths.chat}
</svg>
