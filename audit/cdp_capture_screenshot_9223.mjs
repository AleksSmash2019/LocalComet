import fs from 'node:fs';
const output = process.argv[2] || 'localcomet_cdp_9223.png';
const targets = await (await fetch('http://127.0.0.1:9223/json/list')).json();
const page = targets.find((item) => item.type === 'page' && (item.url || '').includes('localhost:1420')) || targets.find((item) => item.type === 'page');
if (!page?.webSocketDebuggerUrl) throw new Error('No WebView2 page target');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once: true }); ws.addEventListener('error', reject, { once: true }); });
const result = await new Promise((resolve, reject) => {
  const onMessage = (event) => { const message = JSON.parse(event.data); if (message.id !== 1) return; ws.removeEventListener('message', onMessage); if (message.error) reject(new Error(JSON.stringify(message.error))); else resolve(message.result); };
  ws.addEventListener('message', onMessage);
  ws.send(JSON.stringify({ id: 1, method: 'Page.captureScreenshot', params: { format: 'png', fromSurface: true } }));
});
ws.close();
fs.writeFileSync(output, Buffer.from(result.data, 'base64'));
console.log(JSON.stringify({ output, bytes: fs.statSync(output).size, pageUrl: page.url }));
