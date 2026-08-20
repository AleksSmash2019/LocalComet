const port = process.env.CDP_PORT || '9223';
const needle = process.argv.slice(2).join(' ').toLowerCase();
if (!needle) throw new Error('usage: cdp_find_text_nodes.mjs TEXT');
const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const target = targets.find((item) => item.type === 'page');
if (!target?.webSocketDebuggerUrl) throw new Error('No page target');
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once: true }); ws.addEventListener('error', reject, { once: true }); });
const expression = `(() => {
  const needle = ${JSON.stringify(needle)};
  const visible = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden'; };
  const nodes = [...document.querySelectorAll('button,a,[role="button"],select,option,input,label,div,span')].filter(visible).filter((el) => (el.innerText || el.textContent || el.getAttribute('aria-label') || '').toLowerCase().includes(needle));
  return JSON.stringify(nodes.slice(0, 30).map((el) => ({tag: el.tagName, text: (el.innerText || el.textContent || '').trim().slice(0, 300), aria: el.getAttribute('aria-label'), disabled: el.disabled ?? false, outer: el.outerHTML.slice(0, 700)})));
})()`;
ws.addEventListener('message', (event) => {
  const message = JSON.parse(event.data);
  if (message.id !== 1) return;
  ws.close();
  if (message.error) { console.error(JSON.stringify(message.error)); process.exitCode = 1; return; }
  console.log(message.result?.result?.value ?? JSON.stringify(message.result));
});
ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression, returnByValue: true } }));
