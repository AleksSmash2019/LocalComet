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
  return Promise.all([invoke('managed_model_catalog'), invoke('managed_runtime_status'), invoke('managed_installed_artifacts')])
    .then(([catalog, status, installed]) => {
      const allModels = [...(catalog.models || []), ...(catalog.custom_models || [])];
      const model = allModels.find((item) => item.model_id === needle || item.display_name?.includes('Qwen3.8') || item.asset_filename?.includes('Qwen3.8')) || null;
      const artifacts = (installed.artifacts || installed.installed_artifacts || installed || []);
      const artifact = Array.isArray(artifacts) ? artifacts.find((item) => item.artifact_id === (model?.model_id || needle)) || null : null;
      return JSON.stringify({ ok: true, model, artifact, status, selectedModelId: status?.model_id ?? null });
    })
    .catch((error) => JSON.stringify({ ok: false, error: String(error) }));
})()`;
ws.addEventListener('message', (event) => {
  const message = JSON.parse(event.data);
  if (message.id !== 1) return;
  ws.close();
  if (message.error) { console.error(JSON.stringify(message.error)); process.exitCode = 1; return; }
  console.log(message.result?.result?.value ?? JSON.stringify(message.result));
});
ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression, returnByValue: true, awaitPromise: true } }));
