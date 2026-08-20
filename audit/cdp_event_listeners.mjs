import { writeFileSync } from 'node:fs';

const targets = await (await fetch('http://127.0.0.1:9222/json/list')).json();
const page = targets.find((item) => item.type === 'page');
if (!page?.webSocketDebuggerUrl) throw new Error('No page target');
const ws = new WebSocket(page.webSocketDebuggerUrl);
let nextId = 1;
const pending = new Map();
ws.addEventListener('message', (event) => {
  const message = JSON.parse(event.data);
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
await send('Debugger.enable');
const button = await send('Runtime.evaluate', { expression: `document.querySelector('[role="dialog"] .btn-approve')`, objectGroup: 'probe', returnByValue: false });
const documentObject = await send('Runtime.evaluate', { expression: `document`, objectGroup: 'probe', returnByValue: false });
const windowObject = await send('Runtime.evaluate', { expression: `window`, objectGroup: 'probe', returnByValue: false });
if (!button?.result?.objectId) throw new Error('Approval button not found');
const buttonKeys = await send('Runtime.callFunctionOn', { objectId: button.result.objectId, functionDeclaration: `function() { return JSON.stringify({ meta: this.__svelte_meta || null, own: Object.getOwnPropertyNames(this).filter((key) => /click|event|svelte|listener|__/.test(key)), values: Object.getOwnPropertyNames(this).filter((key) => /click|event|svelte|listener|__/.test(key)).map((key) => ({ key, type: typeof this[key], value: typeof this[key] === 'function' ? this[key].toString().slice(0, 200) : String(this[key]).slice(0, 200) })) }); }`, returnByValue: true });
const buttonListeners = await send('DOMDebugger.getEventListeners', { objectId: button.result.objectId });
const documentListeners = await send('DOMDebugger.getEventListeners', { objectId: documentObject.result.objectId });
const sourceResult = await send('Debugger.getScriptSource', { scriptId: '65' });
const source = sourceResult?.scriptSource || '';
const marker = source.indexOf('resolve_tool_approval');
const sourceSnippet = marker >= 0 ? source.slice(Math.max(0, marker - 1000), marker + 1800) : source.slice(0, 500);
const windowListeners = await send('DOMDebugger.getEventListeners', { objectId: windowObject.result.objectId });
const summarize = (value) => value.listeners?.map((item) => ({ type: item.type, useCapture: item.useCapture, passive: item.passive, once: item.once, handler: item.scriptId }));
writeFileSync('audit/compiled-approval-handler-snippet.txt', sourceSnippet, 'utf8');
console.log(JSON.stringify({ buttonKeys: buttonKeys?.result?.value, button: summarize(buttonListeners), documentClick: documentListeners.listeners?.filter((item) => item.type === 'click').map((item) => ({ type: item.type, scriptId: item.scriptId, lineNumber: item.lineNumber, columnNumber: item.columnNumber, handler: item.handler })), saved: 'audit/compiled-approval-handler-snippet.txt' }, null, 2));
ws.close();
