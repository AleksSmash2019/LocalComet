const runtimeId = 'llama-cpp-windows-x86-64-vulkan-bootstrap';
const targets = await (await fetch('http://127.0.0.1:9222/json/list')).json();
const page = targets.find((item) => item.type === 'page');
if (!page?.webSocketDebuggerUrl) throw new Error('No page target');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once: true }); ws.addEventListener('error', reject, { once: true }); });
const expression = `(() => {
  const runtimeId = ${JSON.stringify(runtimeId)};
  const item = [...document.querySelectorAll('.hf-approved-item')].find((x) => x.querySelector('[title="' + runtimeId + '"]'));
  const button = item?.querySelector('button.hf-download-btn');
  if (!item || !button) return JSON.stringify({ result: 'NOT_FOUND', runtimeId, items: [...document.querySelectorAll('.hf-approved-item')].map((x) => ({ title: x.querySelector('[title]')?.getAttribute('title') || null, buttons: [...x.querySelectorAll('button')].map((b) => (b.innerText || '').trim()) })) });
  const before = { runtimeId, text: (button.innerText || '').trim(), disabled: button.disabled };
  button.click();
  return JSON.stringify({ result: 'CLICKED', before });
})()`;
ws.addEventListener('message', (event) => { const message = JSON.parse(event.data); if (message.id !== 1) return; ws.close(); if (message.error) { console.error(JSON.stringify(message.error)); process.exitCode = 1; return; } console.log(message.result?.result?.value ?? JSON.stringify(message.result)); });
ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression, returnByValue: true, awaitPromise: true } }));
