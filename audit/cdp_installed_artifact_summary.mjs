const port = process.env.CDP_PORT || '9223';
const needle = process.argv[2] || 'custom-hf-e7cb624491843a8f27cac1e728539ed6bc64e7dbca8f8c373eb53dc4b4a602ff';
const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const page = targets.find((item) => item.type === 'page');
if (!page?.webSocketDebuggerUrl) throw new Error('No LocalComet page target');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once: true }); ws.addEventListener('error', reject, { once: true }); });
const expression = `(() => {
  const invoke = globalThis.__TAURI_INTERNALS__?.invoke ?? globalThis.__TAURI__?.core?.invoke;
  if (typeof invoke !== 'function') return Promise.resolve(JSON.stringify({ ok: false, reason: 'tauri_invoke_unavailable' }));
  const needle = ${JSON.stringify(needle)};
  const walk = (value, path = '$', out = []) => {
    if (out.length >= 50 || value == null) return out;
    if (Array.isArray(value)) { value.forEach((item, index) => walk(item, path + '[' + index + ']', out)); return out; }
    if (typeof value === 'object') {
      if (value.artifact_id === needle || value.model_id === needle) out.push({ path, value });
      Object.entries(value).forEach(([key, child]) => walk(child, path + '.' + key, out));
    }
    return out;
  };
  return invoke('managed_installed_artifacts').then((installed) => JSON.stringify({ ok: true, rootType: Array.isArray(installed) ? 'array' : typeof installed, rootKeys: installed && typeof installed === 'object' ? Object.keys(installed) : [], matches: walk(installed) })).catch((error) => JSON.stringify({ ok: false, error: String(error) }));
})()`;
ws.addEventListener('message', (event) => {
  const message = JSON.parse(event.data);
  if (message.id !== 1) return;
  ws.close();
  if (message.error) { console.error(JSON.stringify(message.error)); process.exitCode = 1; return; }
  console.log(message.result?.result?.value ?? JSON.stringify(message.result));
});
ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression, returnByValue: true, awaitPromise: true } }));
