import { WebviewWindow } from '@tauri-apps/api/webviewWindow';

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
