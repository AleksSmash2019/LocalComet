const targets = await (await fetch('http://127.0.0.1:9222/json/list')).json();
const page = targets.find((item) => item.type === 'page');
if (!page?.webSocketDebuggerUrl) throw new Error('No page target');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once: true }); ws.addEventListener('error', reject, { once: true }); });
const expression = `(() => {
  const lines = document.body.innerText.split(/\\n+/).map((x) => x.trim()).filter(Boolean);
  const needles = ['Vulkan','vulkan','GPU','CPU','движок','Движок','установ','Установ','engine','Engine','runtime','Runtime'];
  const matches = lines.filter((line) => needles.some((needle) => line.includes(needle)));
  const controls = [...document.querySelectorAll('button,select,input,[role="button"]')].map((x) => ({tag:x.tagName,text:(x.innerText||'').trim(),aria:x.getAttribute('aria-label'),value:x.value||null,disabled:x.disabled||false})).filter((x) => needles.some((needle) => (x.text||'').includes(needle) || (x.aria||'').includes(needle) || (x.value||'').includes(needle)));
  return JSON.stringify({url:location.href,matches,controls});
})()`;
ws.addEventListener('message', (event) => { const message = JSON.parse(event.data); if (message.id !== 1) return; ws.close(); if (message.error) { console.error(JSON.stringify(message.error)); process.exitCode = 1; return; } console.log(message.result?.result?.value ?? JSON.stringify(message.result)); });
ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression, returnByValue: true, awaitPromise: true } }));
