import { invoke } from '@tauri-apps/api/core';

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
  // The window is created Rust-side (open_modelfit_window) so it can be owned
  // by "main": owned windows stay above their owner, minimize/close with it,
  // and never drift off detached from the app. The JS create path with a
  // parent option deadlocks (never settles) on tauri 2.11.5 — CDP-verified.
  await invoke('open_modelfit_window');
}
