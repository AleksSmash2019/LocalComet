const cdpPort = process.env.CDP_PORT || '9222';
const targets = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
const target = targets.find((item) => item.type === 'page');
if (!target?.webSocketDebuggerUrl) throw new Error('No WebView2 page target');
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, { once: true });
  socket.addEventListener('error', reject, { once: true });
});
const expression = `(() => { const frame = document.querySelector('iframe[src="/modelfit.html"]'); const doc = frame?.contentDocument; return JSON.stringify({ ok: !!doc, bodyText: doc?.body?.innerText || '', buttons: [...(doc?.querySelectorAll('button') || [])].map((x) => ({ text: (x.innerText || '').trim(), disabled: !!x.disabled })), title: doc?.title || '' }); })()`;
const result = await new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error('CDP frame summary timeout')), 30000);
  const onMessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.id !== 1) return;
    clearTimeout(timer);
    socket.removeEventListener('message', onMessage);
    if (message.error) reject(new Error(JSON.stringify(message.error)));
    else resolve(message.result?.result?.value ?? message.result);
  };
  socket.addEventListener('message', onMessage);
  socket.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression, returnByValue: true, awaitPromise: true } }));
});
console.log(result);
socket.close();
