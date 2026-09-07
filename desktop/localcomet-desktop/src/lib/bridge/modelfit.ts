import { invoke } from '@tauri-apps/api/core';
import { WebviewWindow } from '@tauri-apps/api/webviewWindow';

type ModelFitInvoke = (command: string, args?: Record<string, unknown>) => Promise<unknown>;
type ModelFitBridgeWindow = Window & { __modelfit_invoke?: ModelFitInvoke };

export function installModelFitBridge(): () => void {
  const host = window as ModelFitBridgeWindow;
  const previousInvoke = host.__modelfit_invoke;
  host.__modelfit_invoke = (command, args) => {
    if (command !== 'scan_hardware') {
      return Promise.reject(new Error('ModelFit command is not allowlisted'));
    }
    return invoke(command, args);
  };
  return () => {
    if (previousInvoke) host.__modelfit_invoke = previousInvoke;
    else delete host.__modelfit_invoke;
  };
}

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
    maximizable: true,
    // Owned window on Windows: stays above the main window, minimizes and
    // closes with it, and never drifts away as a free-floating top-level
    // window in the taskbar/Alt-Tab.
    parent: 'main'
  });

  appWindow.once('tauri://error', (e) => {
    console.error('Failed to create ModelFit window:', e);
  });
}
