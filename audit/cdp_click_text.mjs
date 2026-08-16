const targetText = process.argv.slice(2).join(' ');
if (!targetText) throw new Error('Usage: node cdp_click_text.mjs <visible text>');
const targets = await (await fetch('http://127.0.0.1:9222/json/list')).json();
const page = targets.find((item) => item.type === 'page');
if (!page?.webSocketDebuggerUrl) throw new Error('No page target');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once: true }); ws.addEventListener('error', reject, { once: true }); });
const expression = `(() => { const needle = ${JSON.stringify(targetText)}; const candidates = [...document.querySelectorAll('button,a,[role="button"],select,input,[tabindex]')]; const el = candidates.find((x) => ((x.innerText || x.getAttribute('aria-label') || x.getAttribute('title') || x.value || '').trim()).includes(needle)); if (!el) return JSON.stringify({ result: 'NOT_FOUND', needle, candidates: candidates.map((x) => ((x.innerText || x.getAttribute('aria-label') || x.getAttribute('title') || x.value || '').trim())).filter(Boolean) }); el.click(); return JSON.stringify({ result: 'CLICKED', text: (el.innerText || el.value || '').trim(), tag: el.tagName, html: el.outerHTML.slice(0, 600) }); })()`;
const result = await new Promise((resolve, reject) => {
  const onMessage = (event) => { const message = JSON.parse(event.data); if (message.id !== 1) return; ws.removeEventListener('message', onMessage); if (message.error) reject(new Error(JSON.stringify(message.error))); else resolve(message.result?.result?.value); };
  ws.addEventListener('message', onMessage);
  ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression, returnByValue: true } }));
});
ws.close();
console.log(result);
