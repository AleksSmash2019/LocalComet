const port = process.env.CDP_PORT || '9223';
const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const target = targets.find((item) => item.type === 'page');
if (!target?.webSocketDebuggerUrl) throw new Error('No page target');
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once: true }); ws.addEventListener('error', reject, { once: true }); });
const expression = `(() => {
  const candidates = [...document.querySelectorAll('[role="dialog"], .settings-panel, main, section, div')];
  const scrollable = candidates.filter((el) => el.scrollHeight > el.clientHeight + 10).sort((a, b) => b.scrollHeight - a.scrollHeight)[0];
  if (!scrollable) return JSON.stringify({ ok: false, reason: 'scrollable-not-found' });
  scrollable.scrollTop = scrollable.scrollHeight;
  return JSON.stringify({ ok: true, tag: scrollable.tagName, className: scrollable.className, scrollTop: scrollable.scrollTop, scrollHeight: scrollable.scrollHeight, clientHeight: scrollable.clientHeight });
})()`;
ws.addEventListener('message', (event) => {
  const message = JSON.parse(event.data);
  if (message.id !== 1) return;
  ws.close();
  if (message.error) { console.error(JSON.stringify(message.error)); process.exitCode = 1; return; }
  console.log(message.result?.result?.value ?? JSON.stringify(message.result));
});
ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression, returnByValue: true } }));
