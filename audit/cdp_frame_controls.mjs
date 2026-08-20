const cdpPort = process.env.CDP_PORT || '9222';
const list = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
const target = list.find((item) => item.type === 'page');
if (!target?.webSocketDebuggerUrl) throw new Error('No WebView2 page target');
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, { once: true });
  socket.addEventListener('error', reject, { once: true });
});
const expression = `(() => {
  const frame = document.querySelector('iframe[src="/modelfit.html"]');
  const doc = frame?.contentDocument;
  if (!doc) return JSON.stringify({ok:false,reason:'iframe-not-ready'});
  const controls = [...doc.querySelectorAll('input,select,textarea,button')].map((x, index) => ({
    index,
    tag:x.tagName,
    type:x.type || null,
    name:x.name || null,
    id:x.id || null,
    value:x.value || null,
    placeholder:x.getAttribute('placeholder'),
    aria:x.getAttribute('aria-label'),
    text:(x.innerText || '').trim().slice(0,160),
    disabled:!!x.disabled
  }));
  return JSON.stringify({ok:true,controls});
})()`;
const id = 1;
const result = await new Promise((resolve, reject) => {
  const onMessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.id !== id) return;
    socket.removeEventListener('message', onMessage);
    if (message.error) reject(new Error(JSON.stringify(message.error)));
    else resolve(message.result?.result?.value);
  };
  socket.addEventListener('message', onMessage);
  socket.send(JSON.stringify({id, method:'Runtime.evaluate', params:{expression, returnByValue:true, awaitPromise:true}}));
});
console.log(result);
socket.close();
