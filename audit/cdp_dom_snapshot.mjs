const cdpPort = process.env.CDP_PORT || '9223';
const targets = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
const target = targets.find((item) => item.type === 'page');
if (!target?.webSocketDebuggerUrl) throw new Error('No WebView2 page target');
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, { once: true });
  socket.addEventListener('error', reject, { once: true });
});
const expression = `JSON.stringify({
  title: document.title,
  url: location.href,
  approvalOverlayCount: document.querySelectorAll('.modal-backdrop,[role="dialog"]').length,
  approvalBackdropCount: document.querySelectorAll('.modal-backdrop').length,
  dialogCount: document.querySelectorAll('[role="dialog"]').length,
  approvalText: Array.from(document.querySelectorAll('.modal-backdrop')).map((node) => node.textContent?.trim()).filter(Boolean),
  dialogText: Array.from(document.querySelectorAll('[role="dialog"]')).map((node) => node.textContent?.trim()).filter(Boolean),
  bodyText: document.body?.innerText?.slice(0, 4000) || ''
})`;
const result = await new Promise((resolve, reject) => {
  const id = 1;
  const timer = setTimeout(() => reject(new Error('CDP DOM snapshot timeout')), 15000);
  const onMessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.id !== id) return;
    clearTimeout(timer);
    socket.removeEventListener('message', onMessage);
    if (message.error) reject(new Error(JSON.stringify(message.error)));
    else resolve(message.result?.result?.value ?? message.result);
  };
  socket.addEventListener('message', onMessage);
  socket.send(JSON.stringify({ id, method: 'Runtime.evaluate', params: { expression, returnByValue: true } }));
});
console.log(result);
socket.close();
