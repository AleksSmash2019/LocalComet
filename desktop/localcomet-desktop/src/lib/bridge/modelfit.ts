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

/**
 * Parse the standalone modelfit.html bundle and execute it inside the MAIN
 * window document. An <iframe src="/modelfit.html"> is not viable: WebView2
 * fires the load event but the frame stays an empty cross-origin document
 * (CDP-verified, DOM search finds nothing). The bundle itself is a
 * self-contained React app that mounts to the first #root element and
 * resolves its bridge from its own window.__TAURI__ (withGlobalTauri), so
 * running it in the main document is equivalent to running it standalone.
 */
export async function mountModelFitBundle(host: HTMLElement): Promise<() => void> {
  const response = await fetch('/modelfit.html');
  if (!response.ok) {
    throw new Error(`modelfit bundle fetch failed: ${response.status}`);
  }
  const html = await response.text();
  const parsed = new DOMParser().parseFromString(html, 'text/html');

  const root = document.createElement('div');
  root.id = 'root';
  host.appendChild(root);

  const cleanupNodes: (HTMLElement | SVGElement)[] = [root];
  const injectedScripts: HTMLScriptElement[] = [];

  for (const sourceStyle of Array.from(parsed.querySelectorAll('style'))) {
    const style = document.createElement('style');
    style.textContent = sourceStyle.textContent;
    document.head.appendChild(style);
    cleanupNodes.push(style);
  }

  for (const sourceScript of Array.from(parsed.querySelectorAll('script'))) {
    const script = document.createElement('script');
    for (const attr of Array.from(sourceScript.attributes)) {
      script.setAttribute(attr.name, attr.value);
    }
    script.textContent = sourceScript.textContent;
    document.head.appendChild(script);
    injectedScripts.push(script);
  }

  return () => {
    for (const script of injectedScripts) {
      script.remove();
    }
    for (const node of cleanupNodes) {
      node.remove();
    }
  };
}
