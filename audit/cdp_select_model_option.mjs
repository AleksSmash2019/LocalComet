const port = process.env.CDP_PORT || '9223';
const value = process.argv[2];
if (!value) throw new Error('usage: cdp_select_model_option.mjs MODEL_ID');
const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const target = targets.find((item) => item.type === 'page');
if (!target?.webSocketDebuggerUrl) throw new Error('No page target');
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once: true }); ws.addEventListener('error', reject, { once: true }); });
const expression = `(() => {
  const value = ${JSON.stringify(value)};
  const selects = [...document.querySelectorAll('select')];
  const select = selects.find((candidate) => [...candidate.options].some((option) => option.value === value));
  if (!select) return JSON.stringify({ ok: false, reason: 'model-option-not-found', values: selects.flatMap((candidate) => [...candidate.options].map((option) => option.value)) });
  const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value')?.set;
  if (setter) setter.call(select, value); else select.value = value;
  select.dispatchEvent(new Event('input', { bubbles: true }));
  select.dispatchEvent(new Event('change', { bubbles: true }));
  return JSON.stringify({ ok: true, value: select.value, selectedText: select.options[select.selectedIndex]?.textContent?.trim() });
})()`;
ws.addEventListener('message', (event) => {
  const message = JSON.parse(event.data);
  if (message.id !== 1) return;
  ws.close();
  if (message.error) { console.error(JSON.stringify(message.error)); process.exitCode = 1; return; }
  console.log(message.result?.result?.value ?? JSON.stringify(message.result));
});
ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression, returnByValue: true } }));
