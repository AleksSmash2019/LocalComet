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
 * Execute the ModelFit React bundle inside the MAIN window document.
 *
 * Two delivery paths are proven broken and must not come back:
 *  - <iframe src="/modelfit.html">: WebView2 fires onload but the frame stays
 *    an empty cross-origin document (CDP-verified; DOM search finds nothing).
 *  - injecting the html's inline <script> text into the main document: the
 *    main window CSP is script-src 'self', inline scripts never execute.
 *
 * The bundle is therefore shipped as real same-origin files under
 * /modelfit-generated/ (tools/extract_modelfit_bundle.py splits the html):
 * bundle.css carries the styles, boot.js the small setup scripts, and
 * bundle.module.js is the React module that mounts onto the FIRST #root in
 * the document — the one this component provides.
 */
export async function mountModelFitBundle(host: HTMLElement): Promise<() => void> {
  const root = document.createElement('div');
  root.id = 'root';
  host.appendChild(root);

  const cleanupNodes: (HTMLElement | SVGElement)[] = [root];

  const css = document.createElement('link');
  css.rel = 'stylesheet';
  css.href = '/modelfit-generated/bundle.css';
  document.head.appendChild(css);
  cleanupNodes.push(css);

  const boot = document.createElement('script');
  boot.src = '/modelfit-generated/boot.js';
  document.head.appendChild(boot);
  cleanupNodes.push(boot);

  const loaded = new Promise<void>((resolve, reject) => {
    const bundle = document.createElement('script');
    bundle.type = 'module';
    bundle.src = '/modelfit-generated/bundle.module.js';
    bundle.onload = () => resolve();
    bundle.onerror = () => reject(new Error('ModelFit bundle failed to load'));
    document.head.appendChild(bundle);
    cleanupNodes.push(bundle);
  });

  await loaded;

  return () => {
    for (const node of cleanupNodes) {
      node.remove();
    }
  };
}
