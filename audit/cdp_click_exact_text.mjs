const port = process.env.CDP_PORT || '9223';
const needle = process.argv.slice(2).join(' ');
if (!needle) throw new Error('usage: cdp_click_exact_text.mjs TEXT');
const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const target = targets.find((item) => item.type === 'page');
if (!target?.webSocketDebuggerUrl) throw new Error('No page target');
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  ws.addEventListener('open', resolve, { once: true });
  ws.addEventListener('error', reject, { once: true });
});
const expression = `(() => {
  const needle = ${JSON.stringify(needle)};
  const els = [...document.querySelectorAll('button,a,[role="button"]')];
  const getText = (x) => (x.innerText || x.getAttribute('aria-label') || x.getAttribute('title') || '').trim();
  const matches = els.filter((x) => getText(x) === needle);
  const el = matches.find((x) => {
    const rect = x.getBoundingClientRect();
    const style = getComputedStyle(x);
    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
  }) || matches[0];
  if (!el) return JSON.stringify({ok:false, reason:'exact-visible-not-found', needle, candidates:els.map(getText).filter(Boolean)});
  el.click();
  return JSON.stringify({ok:true, text:getText(el), count:matches.length});
})()`;
const result = await new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error('timeout')), 15000);
  const listener = (event) => {
    const message = JSON.parse(event.data);
    if (message.id !== 1) return;
    clearTimeout(timer);
    ws.removeEventListener('message', listener);
    if (message.error) reject(new Error(JSON.stringify(message.error)));
    else resolve(message.result?.result?.value);
  };
  ws.addEventListener('message', listener);
  ws.send(JSON.stringify({id:1, method:'Runtime.evaluate', params:{expression, returnByValue:true}}));
});
console.log(result);
ws.close();
