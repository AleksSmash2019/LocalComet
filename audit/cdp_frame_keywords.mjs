const cdpPort = process.env.CDP_PORT || '9222';
const pattern = process.argv.slice(2).join(' ') || 'РЕКОМЕНДУЕМАЯ|Режим запуска|Потребление|Ожидаемая|Итоговая|Q4|Q5|Q8|VRAM|RAM|Ollama|llama.cpp|CPU|предупреждение|ПК';
const list = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
const target = list.find((item) => item.type === 'page');
if (!target?.webSocketDebuggerUrl) throw new Error('No WebView2 page target');
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, { once: true });
  socket.addEventListener('error', reject, { once: true });
});
const encoded = JSON.stringify(pattern);
const expression = `(() => {
  const frame = document.querySelector('iframe[src="/modelfit.html"]');
  const doc = frame?.contentDocument;
  if (!doc) return JSON.stringify({ok:false,reason:'iframe-not-ready'});
  const re = new RegExp(${encoded}, 'i');
  const lines = (doc.body?.innerText || '').split(/\\n+/).map((x) => x.trim()).filter(Boolean).filter((x) => re.test(x));
  return JSON.stringify({ok:true,lines});
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
