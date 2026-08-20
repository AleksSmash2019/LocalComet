const cdpPort = process.env.CDP_PORT || '9222';
const wanted = process.env.MODEL_NAME || 'Qwen2.5 1.5B Instruct Q4_K_M';
const list = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
const target = list.find((item) => item.type === 'page');
if (!target?.webSocketDebuggerUrl) throw new Error('No WebView2 page target');
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, { once: true });
  socket.addEventListener('error', reject, { once: true });
});
const encoded = JSON.stringify(wanted);
const expression = `(() => {
  const wanted = ${encoded};
  const selects = [...document.querySelectorAll('select')];
  const select = selects.find((x) => [...x.options].some((o) => o.textContent.trim().startsWith(wanted)));
  if (!select) return JSON.stringify({ok:false,reason:'model-select-not-found',selectCount:selects.length});
  const option = [...select.options].find((o) => o.textContent.trim().startsWith(wanted));
  const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value')?.set;
  if (setter) setter.call(select, option.value); else select.value = option.value;
  select.dispatchEvent(new Event('change', {bubbles:true}));
  select.dispatchEvent(new Event('input', {bubbles:true}));
  const buttons = [...document.querySelectorAll('button')];
  const launch = buttons.find((x) => (x.innerText || '').includes('Запустить выбранную')) || buttons.find((x) => ['Подключить модель', 'Подключить'].includes((x.innerText || '').trim()));
  if (!launch) return JSON.stringify({ok:false,reason:'launch-button-not-found',selected:select.value});
  launch.click();
  return JSON.stringify({ok:true,selected:select.value,label:option.textContent.trim(),button:(launch.innerText || '').trim()});
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
