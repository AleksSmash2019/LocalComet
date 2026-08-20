const port = process.env.CDP_PORT || '9223';
const modelId = 'custom-hf-e7cb624491843a8f27cac1e728539ed6bc64e7dbca8f8c373eb53dc4b4a602ff';
const runtimeId = 'llama-cpp-windows-x86-64-vulkan-bootstrap';
const customSha256 = 'e103abf9d914d1d7b2f2592f055f2759a71195c350a01c135f71aaae86bca52b';
const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const page = targets.find((item) => item.type === 'page');
if (!page?.webSocketDebuggerUrl) throw new Error('No LocalComet page target');
const ws = new WebSocket(page.webSocketDebuggerUrl);
let nextId = 1;
const pending = new Map();
ws.addEventListener('message', (event) => {
  const message = JSON.parse(event.data);
  const waiter = pending.get(message.id);
  if (!waiter) return;
  pending.delete(message.id);
  if (message.error) waiter.reject(new Error(JSON.stringify(message.error)));
  else waiter.resolve(message.result);
});
await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once: true }); ws.addEventListener('error', reject, { once: true }); });
function send(method, params = {}) { return new Promise((resolve, reject) => { const id = nextId++; pending.set(id, { resolve, reject }); ws.send(JSON.stringify({ id, method, params })); }); }
async function evaluate(expression) { const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true }); if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails)); return result.result?.value; }
const startExpression = `(() => {
  const invoke = globalThis.__TAURI_INTERNALS__?.invoke ?? globalThis.__TAURI__?.core?.invoke;
  if (typeof invoke !== 'function') return Promise.resolve(JSON.stringify({ ok: false, reason: 'tauri_invoke_unavailable' }));
  const input = { model_id: ${JSON.stringify(modelId)}, custom_sha256: ${JSON.stringify(customSha256)}, runtime_id: ${JSON.stringify(runtimeId)}, ctx_size_override: null, gpu_layers_override: null };
  return invoke('request_approval', { tool: 'runtime.start', input })
    .then((envelope) => invoke('managed_runtime_start', { modelId: ${JSON.stringify(modelId)}, customSha256: ${JSON.stringify(customSha256)}, runtimeId: ${JSON.stringify(runtimeId)}, ctxSizeOverride: null, gpuLayersOverride: null, token: envelope.token, approvalId: envelope.approvalId, callId: envelope.callId }))
    .then((state) => JSON.stringify({ ok: true, state }))
    .catch((error) => JSON.stringify({ ok: false, error: String(error) }));
})()`;
const startedRaw = await evaluate(startExpression);
console.log(startedRaw);
const started = JSON.parse(startedRaw);
if (!started.ok) { ws.close(); process.exitCode = 1; process.exit(); }
let last = '';
const deadline = Date.now() + 15 * 60 * 1000;
for (;;) {
  await new Promise((resolve) => setTimeout(resolve, 5000));
  const statusRaw = await evaluate(`(() => { const invoke = globalThis.__TAURI_INTERNALS__?.invoke ?? globalThis.__TAURI__?.core?.invoke; return invoke('managed_runtime_status').then((status) => JSON.stringify(status)).catch((error) => JSON.stringify({ error: String(error) })); })()`);
  const status = JSON.parse(statusRaw);
  const line = JSON.stringify({ state: status.state, model_state: status.model_state, inference_ready: status.inference_ready, model_id: status.model_id, loading_phase: status.loading_phase, last_error: status.last_error });
  if (line !== last) { console.log(line); last = line; }
  if (['Ready', 'Stopped', 'Failed'].includes(status.state) && status.state !== 'Starting') { ws.close(); if (status.state !== 'Ready') process.exitCode = 1; break; }
  if (Date.now() > deadline) { console.log(JSON.stringify({ timeout: true })); ws.close(); process.exitCode = 2; break; }
}
