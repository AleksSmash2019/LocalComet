const port = process.env.CDP_PORT || '9223';
const needle = process.argv[2] || '';
const value = process.argv.slice(3).join(' ');
if (!needle || !value) throw new Error('usage: cdp_fill_input.mjs INPUT_HINT TEXT');
const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const target = targets.find((item) => item.type === 'page');
if (!target?.webSocketDebuggerUrl) throw new Error('No page target');
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once: true }); ws.addEventListener('error', reject, { once: true }); });
const expression = `(() => {
  const hint = ${JSON.stringify(needle)}.toLowerCase();
  const text = ${JSON.stringify(value)};
  const inputs = [...document.querySelectorAll('input, textarea, [contenteditable="true"]')];
  const describe = (el) => [el.getAttribute('placeholder'), el.getAttribute('aria-label'), el.getAttribute('name'), el.getAttribute('type')].filter(Boolean).join(' ').toLowerCase();
  const visible = inputs.filter((el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden'; });
  const el = visible.find((candidate) => describe(candidate).includes(hint));
  if (!el) return JSON.stringify({ ok: false, reason: 'input-not-found', inputs: visible.map((candidate) => ({ tag: candidate.tagName, placeholder: candidate.getAttribute('placeholder'), aria: candidate.getAttribute('aria-label'), name: candidate.getAttribute('name'), type: candidate.getAttribute('type') })) });
  el.focus();
  if (el instanceof HTMLInputElement) {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
    if (setter) setter.call(el, text); else el.value = text;
  } else if (el instanceof HTMLTextAreaElement) {
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')?.set;
    if (setter) setter.call(el, text); else el.value = text;
  } else {
    el.textContent = text;
  }
  el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: text }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
  return JSON.stringify({ ok: true, value: el.value ?? el.textContent ?? '', descriptor: describe(el) });
})()`;
ws.addEventListener('message', (event) => {
  const message = JSON.parse(event.data);
  if (message.id !== 1) return;
  ws.close();
  if (message.error) { console.error(JSON.stringify(message.error)); process.exitCode = 1; return; }
  console.log(message.result?.result?.value ?? JSON.stringify(message.result));
});
ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression, returnByValue: true } }));
