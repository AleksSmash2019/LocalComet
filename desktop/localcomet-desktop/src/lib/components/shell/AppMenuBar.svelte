<script lang="ts">
  import { tick } from 'svelte';
  import { getCurrentWindow } from '@tauri-apps/api/window';
  import { t } from '$lib/i18n';
  import { DESKTOP_SHELL_VERSION, DESKTOP_BUILD_LABEL } from '$lib/version';

  type MenuKey = 'file' | 'view' | 'help';

  interface MenuItemDef {
    labelKey: string;
    shortcutKey?: string;
    action: () => void;
  }
  interface MenuDef {
    key: MenuKey;
    labelKey: string;
    items: MenuItemDef[];
  }

  let openMenu: MenuKey | null = null;
  let aboutOpen = false;
  let rootElement: HTMLDivElement;

  function tauriWindow(): ReturnType<typeof getCurrentWindow> | null {
    try {
      return getCurrentWindow();
    } catch {
      return null;
    }
  }

  function reloadInterface(): void {
    // Same seam the native menu uses (lc-reload -> location.reload()).
    location.reload();
  }

  function quitApplication(): void {
    // Same seam the native menu uses (lc-quit -> main window close).
    tauriWindow()?.close().catch(() => {});
  }

  function minimizeWindow(): void {
    tauriWindow()?.minimize().catch(() => {});
  }

  function toggleMaximizeWindow(): void {
    tauriWindow()?.toggleMaximize().catch(() => {});
  }

  function closeWindow(): void {
    tauriWindow()?.close().catch(() => {});
  }

  const menus: MenuDef[] = [
    {
      key: 'file',
      labelKey: 'menu.file',
      items: [
        { labelKey: 'menu.file.reload', shortcutKey: 'Ctrl+R', action: reloadInterface },
        { labelKey: 'menu.file.quit', shortcutKey: 'Ctrl+Q', action: quitApplication }
      ]
    },
    {
      key: 'view',
      labelKey: 'menu.view',
      items: [
        { labelKey: 'menu.view.minimize', action: minimizeWindow },
        { labelKey: 'menu.view.maximize', action: toggleMaximizeWindow },
        { labelKey: 'menu.view.closeWindow', action: closeWindow }
      ]
    },
    {
      key: 'help',
      labelKey: 'menu.help',
      items: [
        {
          labelKey: 'menu.help.about',
          action: () => {
            openMenu = null;
            aboutOpen = true;
          }
        }
      ]
    }
  ];

  function closeAllMenus(): void {
    openMenu = null;
  }

  function toggleMenu(key: MenuKey): void {
    openMenu = openMenu === key ? null : key;
    if (openMenu) void focusFirstItem();
  }

  async function focusFirstItem(): Promise<void> {
    await tick();
    rootElement
      ?.querySelector<HTMLButtonElement>('.menu-slot.open .menu-panel button')
      ?.focus();
  }

  function focusSiblingItem(current: HTMLButtonElement, offset: number): void {
    const items = Array.from(
      current.closest('.menu-panel')?.querySelectorAll<HTMLButtonElement>('button') ?? []
    );
    if (!items.length) return;
    const next = (items.indexOf(current) + offset + items.length) % items.length;
    items[next].focus();
  }

  function handleTriggerKeydown(event: KeyboardEvent, key: MenuKey, index: number): void {
    if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (openMenu !== key) {
        openMenu = key;
        void focusFirstItem();
      }
      return;
    }
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      event.preventDefault();
      const offset = event.key === 'ArrowRight' ? 1 : -1;
      const next = menus[(index + offset + menus.length) % menus.length];
      openMenu = openMenu === null ? null : next.key;
      rootElement
        ?.querySelectorAll<HTMLButtonElement>('.menu-trigger')
        [index + offset < 0 ? menus.length - 1 : (index + offset) % menus.length]?.focus();
      return;
    }
    if (event.key === 'Escape' && openMenu === key) {
      event.preventDefault();
      closeAllMenus();
    }
  }

  function handleItemKeydown(event: KeyboardEvent): void {
    const target = event.currentTarget as HTMLButtonElement;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      focusSiblingItem(target, 1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      focusSiblingItem(target, -1);
    } else if (event.key === 'Home') {
      event.preventDefault();
      target.closest('.menu-panel')?.querySelector<HTMLButtonElement>('button')?.focus();
    } else if (event.key === 'End') {
      event.preventDefault();
      const items = Array.from(
        target.closest('.menu-panel')?.querySelectorAll<HTMLButtonElement>('button') ?? []
      );
      items[items.length - 1]?.focus();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      closeAllMenus();
      rootElement?.querySelector<HTMLButtonElement>('.menu-slot.open .menu-trigger')?.focus();
    } else if (event.key === 'Tab') {
      closeAllMenus();
    }
  }

  function runItem(item: MenuItemDef): void {
    closeAllMenus();
    item.action();
  }

  function handleGlobalPointerDown(event: PointerEvent): void {
    if (openMenu && rootElement && !rootElement.contains(event.target as Node)) {
      closeAllMenus();
    }
  }

  function handleGlobalKeydown(event: KeyboardEvent): void {
    if (!(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey) return;
    const target = event.target as HTMLElement | null;
    if (!target || target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return;
    const key = event.key.toLowerCase();
    if (key === 'r') {
      event.preventDefault();
      reloadInterface();
    } else if (key === 'q') {
      event.preventDefault();
      quitApplication();
    }
  }
</script>

<svelte:window onpointerdown={handleGlobalPointerDown} onkeydown={handleGlobalKeydown} />

<div class="app-menu-bar" bind:this={rootElement}>
  <span class="brand" aria-hidden="true"><span>Local</span>Comet</span>
  <div class="menu-root" role="menubar" aria-label={$t('menu.bar.label')}>
    {#each menus as menu, index (menu.key)}
      <div class="menu-slot" class:open={openMenu === menu.key}>
        <button
          type="button"
          role="menuitem"
          class="menu-trigger"
          aria-haspopup="menu"
          aria-expanded={openMenu === menu.key}
          onclick={() => toggleMenu(menu.key)}
          onkeydown={(event) => handleTriggerKeydown(event, menu.key, index)}
          onpointerenter={() => {
            if (openMenu && openMenu !== menu.key) openMenu = menu.key;
          }}
        >
          {$t(menu.labelKey)}
        </button>
        {#if openMenu === menu.key}
          <div class="menu-panel" role="menu" aria-label={$t(menu.labelKey)}>
            {#each menu.items as item (item.labelKey)}
              <button
                type="button"
                role="menuitem"
                onclick={() => runItem(item)}
                onkeydown={handleItemKeydown}
              >
                <span>{$t(item.labelKey)}</span>
                {#if item.shortcutKey}
                  <kbd aria-label={item.shortcutKey}>{item.shortcutKey}</kbd>
                {/if}
              </button>
            {/each}
          </div>
        {/if}
      </div>
    {/each}
  </div>
</div>

{#if aboutOpen}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div class="about-backdrop" onclick={() => (aboutOpen = false)}>
    <div class="about-card" role="dialog" aria-modal="true" aria-labelledby="about-title">
      <p class="about-wordmark" id="about-title"><span>Local</span>Comet</p>
      <p class="about-tagline">{$t('menu.about.tagline')}</p>
      <dl class="about-facts">
        <div>
          <dt>{$t('menu.about.version')}</dt>
          <dd>{DESKTOP_SHELL_VERSION}</dd>
        </div>
        <div>
          <dt>{$t('menu.about.build')}</dt>
          <dd>{DESKTOP_BUILD_LABEL}</dd>
        </div>
      </dl>
      <button type="button" class="about-close" onclick={() => (aboutOpen = false)}>
        {$t('menu.about.close')}
      </button>
    </div>
  </div>
{/if}

<style>
  .app-menu-bar {
    grid-column: 1 / -1;
    grid-row: 1;
    display: flex;
    align-items: center;
    gap: var(--lc-space-3);
    height: var(--app-menubar-height);
    padding-inline: var(--lc-space-3);
    border-bottom: var(--border-thin);
    background: var(--lc-panel);
    user-select: none;
  }

  .brand {
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.02em;
    color: var(--lc-text);
  }

  .brand span {
    color: var(--lc-accent);
  }

  .menu-root {
    display: flex;
    align-items: stretch;
    height: 100%;
  }

  .menu-slot {
    position: relative;
    display: flex;
  }

  .menu-trigger {
    border: none;
    background: transparent;
    color: var(--lc-text);
    font: inherit;
    font-size: 12px;
    padding-inline: var(--lc-space-3);
    border-radius: var(--lc-radius-sm, 6px);
    cursor: pointer;
  }

  .menu-slot.open .menu-trigger,
  .menu-trigger:hover,
  .menu-trigger:focus-visible {
    background: color-mix(in srgb, var(--lc-accent) 16%, transparent);
    outline: none;
  }

  .menu-panel {
    position: absolute;
    top: 100%;
    left: 0;
    z-index: 60;
    min-width: 240px;
    display: flex;
    flex-direction: column;
    padding: var(--lc-space-2);
    gap: 2px;
    border: var(--border-thin);
    border-radius: 8px;
    background: var(--lc-panel-solid);
    box-shadow: var(--lc-shadow);
  }

  .menu-panel button {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--lc-space-5);
    border: none;
    background: transparent;
    color: var(--lc-text);
    font: inherit;
    font-size: 12px;
    text-align: left;
    padding: var(--lc-space-2) var(--lc-space-3);
    border-radius: 6px;
    cursor: pointer;
    white-space: nowrap;
  }

  .menu-panel button:hover,
  .menu-panel button:focus-visible {
    background: color-mix(in srgb, var(--lc-accent) 16%, transparent);
    outline: none;
  }

  .menu-panel kbd {
    min-width: 52px;
    height: 20px;
    padding-inline: 6px;
    color: var(--lc-text-muted, var(--lc-text));
    font-size: 10px;
    opacity: 0.85;
  }

  .about-backdrop {
    position: fixed;
    inset: 0;
    z-index: 70;
    display: grid;
    place-items: center;
    background: color-mix(in srgb, #000 44%, transparent);
  }

  .about-card {
    display: flex;
    flex-direction: column;
    gap: var(--lc-space-3);
    width: min(380px, calc(100vw - 48px));
    padding: var(--lc-space-5);
    border: var(--border-thin);
    border-radius: 12px;
    background: var(--lc-panel-solid);
    box-shadow: var(--lc-shadow);
  }

  .about-wordmark {
    margin: 0;
    font-size: 18px;
    font-weight: 800;
  }

  .about-wordmark span {
    color: var(--lc-accent);
  }

  .about-tagline {
    margin: 0;
    font-size: 12px;
    color: var(--lc-text-muted, var(--lc-text));
  }

  .about-facts {
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--lc-space-2);
  }

  .about-facts div {
    display: flex;
    justify-content: space-between;
    gap: var(--lc-space-3);
    font-size: 12px;
  }

  .about-facts dt {
    color: var(--lc-text-muted, var(--lc-text));
  }

  .about-facts dd {
    margin: 0;
    font-weight: 700;
  }

  .about-close {
    align-self: flex-end;
    border: var(--border-thin);
    background: transparent;
    color: var(--lc-text);
    font: inherit;
    font-size: 12px;
    padding: var(--lc-space-2) var(--lc-space-4);
    border-radius: 6px;
    cursor: pointer;
  }

  .about-close:hover,
  .about-close:focus-visible {
    background: color-mix(in srgb, var(--lc-accent) 16%, transparent);
    outline: none;
  }
</style>
