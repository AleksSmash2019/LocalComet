const port = process.env.CDP_PORT || '9223';
const url = 'https://huggingface.co/bartowski/Qwen3.8-27B-GGUF/resolve/main/Qwen3.8-27B-Q4_K_M.gguf';
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
await new Promise((resolve, reject) => {
  ws.addEventListener('open', resolve, { once: true });
  ws.addEventListener('error', reject, { once: true });
});
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = nextId++;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const result = await send('Runtime.evaluate', {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result?.value;
}
const startExpression = `(() => {
  const invoke = globalThis.__TAURI_INTERNALS__?.invoke ?? globalThis.__TAURI__?.core?.invoke;
  if (typeof invoke !== 'function') return Promise.resolve(JSON.stringify({ ok: false, reason: 'tauri_invoke_unavailable' }));
  const url = ${JSON.stringify(url)};
  return invoke('request_approval', { tool: 'artifact.download', input: { custom_url: url } })
    .then((envelope) => invoke('start_approved_artifact_download', {
      customUrl: url,
      token: envelope.token,
      approvalId: envelope.approvalId,
      callId: envelope.callId,
    }))
    .then((state) => JSON.stringify({ ok: true, state }))
    .catch((error) => JSON.stringify({ ok: false, error: String(error) }));
})()`;
const startedRaw = await evaluate(startExpression);
console.log(startedRaw);
const started = JSON.parse(startedRaw);
if (!started.ok) {
  ws.close();
  process.exitCode = 1;
  process.exit();
}
const jobId = started.state.job_id;
if (!jobId) throw new Error('Download state missing job_id');
let last = '';
for (;;) {
  await new Promise((resolve) => setTimeout(resolve, 2000));
  const stateRaw = await evaluate(`(() => {
    const invoke = globalThis.__TAURI_INTERNALS__?.invoke ?? globalThis.__TAURI__?.core?.invoke;
    return invoke('get_artifact_download_state', { jobId: ${JSON.stringify(jobId)} })
      .then((state) => JSON.stringify(state))
      .catch((error) => JSON.stringify({ error: String(error) }));
  })()`);
  const state = JSON.parse(stateRaw);
  const line = JSON.stringify({ lifecycle: state.lifecycle, received_bytes: state.received_bytes, expected_bytes: state.expected_bytes, error_code: state.error_code, artifact_id: state.artifact_id });
  if (line !== last) { console.log(line); last = line; }
  if (['completed', 'failed', 'cancelled'].includes(state.lifecycle)) {
    ws.close();
    if (state.lifecycle !== 'completed') process.exitCode = 1;
    break;
  }
}
