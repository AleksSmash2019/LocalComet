const port = process.env.CDP_PORT || '9223';
const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const target = targets.find((item) => item.type === 'page');
if (!target?.webSocketDebuggerUrl) throw new Error('No page target');
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once: true }); ws.addEventListener('error', reject, { once: true }); });
const expression = `(() => {
  const visible = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden'; };
  return JSON.stringify({
    inputs: [...document.querySelectorAll('input, textarea, [contenteditable="true"]')].filter(visible).map((el) => ({tag: el.tagName, placeholder: el.getAttribute('placeholder'), aria: el.getAttribute('aria-label'), name: el.getAttribute('name'), type: el.getAttribute('type'), value: el.value ?? el.textContent ?? ''})),
    buttons: [...document.querySelectorAll('button,[role="button"]')].filter(visible).map((el) => ({text: (el.innerText || '').trim(), aria: el.getAttribute('aria-label'), title: el.getAttribute('title'), disabled: el.disabled ?? false})).filter((x) => x.text || x.aria || x.title)
  });
})()`;
ws.addEventListener('message', (event) => {
  const message = JSON.parse(event.data);
  if (message.id !== 1) return;
  ws.close();
  if (message.error) { console.error(JSON.stringify(message.error)); process.exitCode = 1; return; }
  console.log(message.result?.result?.value ?? JSON.stringify(message.result));
});
ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression, returnByValue: true } }));
