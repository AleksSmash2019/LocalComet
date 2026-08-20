const targets = await (await fetch('http://127.0.0.1:9222/json/list')).json();
const page = targets.find((item) => item.type === 'page');
if (!page?.webSocketDebuggerUrl) throw new Error('No page target');
const ws = new WebSocket(page.webSocketDebuggerUrl);
const logs = [];
let nextId = 1;
const pending = new Map();
ws.addEventListener('message', (event) => {
  const message = JSON.parse(event.data);
  if (message.method === 'Runtime.consoleAPICalled') {
    logs.push({ type: message.params.type, args: message.params.args?.map((arg) => arg.value ?? arg.description ?? '') });
  }
  if (message.method === 'Runtime.exceptionThrown') {
    logs.push({ type: 'exception', text: message.params.exceptionDetails?.text, description: message.params.exceptionDetails?.exception?.description });
  }
  const waiter = pending.get(message.id);
  if (waiter) { pending.delete(message.id); waiter(message); }
});
await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once: true }); ws.addEventListener('error', reject, { once: true }); });
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const id = nextId++;
  pending.set(id, (message) => message.error ? reject(new Error(JSON.stringify(message.error))) : resolve(message.result));
  ws.send(JSON.stringify({ id, method, params }));
});
await send('Runtime.enable');
await send('Runtime.evaluate', { expression: `document.addEventListener('click', (event) => console.log('CAPTURE_CLICK', event.target?.outerHTML?.slice(0, 400) || event.target?.tagName), true)`, returnByValue: true, awaitPromise: true });
const target = await send('Runtime.evaluate', {
  expression: `(() => { const el = document.querySelector('[role="dialog"] .btn-approve'); if (!el) return null; const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2, text: (el.innerText || '').trim() }; })()`,
  returnByValue: true,
  awaitPromise: true
});
const point = target?.result?.value;
if (!point) throw new Error('Approval button not found');
await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: point.x, y: point.y, button: 'left', clickCount: 1 });
await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: point.x, y: point.y, button: 'left', clickCount: 1 });
await new Promise((resolve) => setTimeout(resolve, 5000));
const state = await send('Runtime.evaluate', {
  expression: `JSON.stringify({ dialog: document.querySelector('[role="dialog"]')?.innerText || null, approve: (() => { const x = document.querySelector('[role="dialog"] .btn-approve'); return x ? { disabled: x.disabled, className: x.className } : null; })(), alerts: [...document.querySelectorAll('[role="alert"],.approval-error')].map((x) => x.innerText) })`,
  returnByValue: true,
  awaitPromise: true
});
console.log(JSON.stringify({ point, state: state?.result?.value, logs }, null, 2));
ws.close();
