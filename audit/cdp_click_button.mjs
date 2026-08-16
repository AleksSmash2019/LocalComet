const needle = process.argv.slice(2).join(' ') || 'Модели HF';
const targets = await (await fetch('http://127.0.0.1:9222/json/list')).json();
const page = targets.find((item) => item.type === 'page');
if (!page?.webSocketDebuggerUrl) throw new Error('No page target');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  ws.addEventListener('open', resolve, { once: true });
  ws.addEventListener('error', reject, { once: true });
});
const expression = `(() => {
  const needle = ${JSON.stringify(needle)};
  const candidates = [...document.querySelectorAll('button,a,[role="button"]')];
  const el = candidates.find((x) => (x.innerText || x.getAttribute('aria-label') || x.getAttribute('title') || '').trim().includes(needle));
  if (!el) return JSON.stringify({ result: 'NOT_FOUND', needle, candidates: candidates.map((x) => (x.innerText || x.getAttribute('aria-label') || x.getAttribute('title') || '').trim()).filter(Boolean) });
  if (el.disabled) return JSON.stringify({ result: 'DISABLED', text: el.innerText?.trim(), html: el.outerHTML.slice(0, 600) });
  el.click();
  return JSON.stringify({ result: 'CLICKED', text: el.innerText?.trim(), html: el.outerHTML.slice(0, 600) });
})()`;
await new Promise((resolve, reject) => {
  const onMessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.id !== 1) return;
    ws.removeEventListener('message', onMessage);
    ws.close();
    if (message.error) reject(new Error(JSON.stringify(message.error)));
    else { console.log(message.result?.result?.value ?? message.result); resolve(); }
  };
  ws.addEventListener('message', onMessage);
  ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression, returnByValue: true, awaitPromise: true } }));
});
