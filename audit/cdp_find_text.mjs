const targetText = process.argv.slice(2).join(' ') || 'Настроить локальный AI';
const targets = await (await fetch('http://127.0.0.1:9222/json/list')).json();
const page = targets.find((item) => item.type === 'page');
if (!page?.webSocketDebuggerUrl) throw new Error('No page target');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once: true }); ws.addEventListener('error', reject, { once: true }); });
const expression = `JSON.stringify([...document.querySelectorAll('*')].filter((el) => (el.innerText || '').trim() === ${JSON.stringify(targetText)}).map((el) => ({ tag: el.tagName, className: el.className, id: el.id, role: el.getAttribute('role'), aria: el.getAttribute('aria-label'), html: el.outerHTML.slice(0, 1200) })))`;
const result = await new Promise((resolve, reject) => {
  const onMessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.id !== 1) return;
    ws.removeEventListener('message', onMessage);
    if (message.error) reject(new Error(JSON.stringify(message.error))); else resolve(message.result?.result?.value);
  };
  ws.addEventListener('message', onMessage);
  ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression, returnByValue: true } }));
});
ws.close();
console.log(result);
