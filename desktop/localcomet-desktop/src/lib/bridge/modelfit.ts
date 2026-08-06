import { WebviewWindow } from '@tauri-apps/api/webviewWindow';
import { invoke } from '@tauri-apps/api/core';

export async function openModelFitWindow(): Promise<void> {
  const appWindow = new WebviewWindow('modelfit', {
    url: '/modelfit.html',
    title: 'ModelFit AI',
    width: 1100,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    center: true,
    decorations: true,
    resizable: true,
    maximizable: true
  });

  appWindow.once('tauri://error', (e) => {
    console.error('Failed to create ModelFit window:', e);
  });
}

/** Expose the Tauri invoke function on window so the modelfit iframe can use it. */
export function exposeInvokeForModelFit(): void {
  // @ts-ignore
  window.__modelfit_invoke = invoke;
}
