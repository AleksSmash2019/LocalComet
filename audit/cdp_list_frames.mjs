const cdpPort = process.env.CDP_PORT || '9222';
const targets = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
const target = targets.find((item) => item.type === 'page');
if (!target?.webSocketDebuggerUrl) throw new Error('No WebView2 page target');
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, { once: true });
  socket.addEventListener('error', reject, { once: true });
});
const expression = `JSON.stringify({url:location.href,title:document.title,bodyText:(document.body?.innerText||'').slice(0,1200),frames:[...document.querySelectorAll('iframe')].map((x)=>({src:x.getAttribute('src'),currentSrc:x.contentWindow?.location?.href||null,ready:!!x.contentDocument,body:(x.contentDocument?.body?.innerText||'').slice(0,800)}))})`;
const result = await new Promise((resolve, reject) => {
  const onMessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.id !== 1) return;
    socket.removeEventListener('message', onMessage);
    if (message.error) reject(new Error(JSON.stringify(message.error)));
    else resolve(message.result?.result?.value ?? message.result);
  };
  socket.addEventListener('message', onMessage);
  socket.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression, returnByValue: true, awaitPromise: true } }));
});
console.log(result);
socket.close();
