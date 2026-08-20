const targets = await (await fetch('http://127.0.0.1:9223/json/list')).json();
const page = targets.find((item) => item.type === 'page');
if (!page?.webSocketDebuggerUrl) throw new Error('No LocalComet page target on CDP 9223');
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
const expression = `(() => {
  const invoke = globalThis.__TAURI_INTERNALS__?.invoke ?? globalThis.__TAURI__?.core?.invoke;
  if (typeof invoke !== 'function') return Promise.resolve(JSON.stringify({ ok: false, reason: 'tauri_invoke_unavailable' }));
  return invoke('plugin:window|close', { label: 'main' })
    .then(() => JSON.stringify({ ok: true, method: 'plugin:window|close' }))
    .catch((error) => JSON.stringify({ ok: false, error: String(error) }));
})()`;
const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
console.log(result.result?.value ?? JSON.stringify(result));
ws.close();
