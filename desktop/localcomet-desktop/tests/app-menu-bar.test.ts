import { render } from 'svelte/server';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const windowMock = vi.hoisted(() => ({
  getCurrentWindow: vi.fn(() => ({
    close: vi.fn().mockResolvedValue(undefined),
    minimize: vi.fn().mockResolvedValue(undefined),
    toggleMaximize: vi.fn().mockResolvedValue(undefined)
  }))
}));

vi.mock('@tauri-apps/api/window', () => ({
  getCurrentWindow: windowMock.getCurrentWindow
}));

import AppMenuBar from '../src/lib/components/shell/AppMenuBar.svelte';
import { setLocale } from '../src/lib/i18n';

const menuBarSourceModules = import.meta.glob(
  ['../src/lib/components/shell/AppMenuBar.svelte'],
  { eager: true, query: '?raw', import: 'default' }
) as Record<string, string>;

function menuBarSource(): string {
  const content = menuBarSourceModules['../src/lib/components/shell/AppMenuBar.svelte'];
  if (typeof content !== 'string') {
    throw new Error('AppMenuBar source fixture not found');
  }
  return content;
}

function menuHtml(language: 'ru' | 'en'): string {
  setLocale(language);
  return render(AppMenuBar).body;
}

beforeEach(() => {
  windowMock.getCurrentWindow.mockClear();
});

describe('AppMenuBar (web menubar that replaced the native Win32 menu)', () => {
  it('renders the menubar with three canonical triggers in ru', () => {
    const html = menuHtml('ru');
    expect(html).toContain('role="menubar"');
    expect(html).toContain('Файл');
    expect(html).toContain('Вид');
    expect(html).toContain('Справка');
  });

  it('renders the menubar with three canonical triggers in en', () => {
    const html = menuHtml('en');
    expect(html).toContain('File');
    expect(html).toContain('View');
    expect(html).toContain('Help');
  });

  it('keeps every former native-menu action in the menu definitions (source inventory)', () => {
    const source = menuBarSource();
    // The removed native menu (commit 25c38e7) had exactly these actions;
    // each must survive in the web menu item table via its i18n key.
    expect(source).toContain("labelKey: 'menu.file.reload'");
    expect(source).toContain("labelKey: 'menu.file.quit'");
    expect(source).toContain("labelKey: 'menu.view.minimize'");
    expect(source).toContain("labelKey: 'menu.view.maximize'");
    expect(source).toContain("labelKey: 'menu.view.closeWindow'");
    expect(source).toContain("labelKey: 'menu.help.about'");
  });

  it('advertises Ctrl+R / Ctrl+Q shortcuts and handles both ctrl and meta keys', () => {
    const source = menuBarSource();
    expect(source).toContain("shortcutKey: 'Ctrl+R'");
    expect(source).toContain("shortcutKey: 'Ctrl+Q'");
    // Cross-platform accelerator handling: Windows/Linux Ctrl, macOS Cmd.
    expect(source).toContain('event.ctrlKey || event.metaKey');
  });

  it('resolves Tauri window handles lazily inside action handlers only', () => {
    menuHtml('en');
    expect(windowMock.getCurrentWindow).not.toHaveBeenCalled();
  });

  it('does not render the About dialog while all menus are closed', () => {
    const html = menuHtml('ru');
    expect(html).not.toContain('about-card');
  });
});