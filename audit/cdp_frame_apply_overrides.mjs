const cdpPort = process.env.CDP_PORT || '9222';
const ram = process.env.OVERRIDE_RAM || '8';
const vram = process.env.OVERRIDE_VRAM || '4';
const disk = process.env.OVERRIDE_DISK || '50';
const gpu = process.env.OVERRIDE_GPU || 'NVIDIA';
const list = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
const target = list.find((item) => item.type === 'page');
if (!target?.webSocketDebuggerUrl) throw new Error('No WebView2 page target');
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, { once: true });
  socket.addEventListener('error', reject, { once: true });
});
const args = JSON.stringify({ ram, vram, disk, gpu });
const expression = `(() => {
  const cfg = ${args};
  const frame = document.querySelector('iframe[src="/modelfit.html"]');
  const doc = frame?.contentDocument;
  if (!doc) return JSON.stringify({ok:false,reason:'iframe-not-ready'});
  const inputs = [...doc.querySelectorAll('input[type="number"]')];
  const select = doc.querySelector('select');
  const buttons = [...doc.querySelectorAll('button')];
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
  const setInput = (el, value) => { if (setter) setter.call(el, value); else el.value = value; el.dispatchEvent(new Event('input', {bubbles:true})); el.dispatchEvent(new Event('change', {bubbles:true})); };
  if (inputs.length < 3 || !select) return JSON.stringify({ok:false,reason:'controls-not-found',inputCount:inputs.length,hasSelect:!!select});
  setInput(inputs[0], cfg.ram);
  setInput(inputs[1], cfg.vram);
  setInput(inputs[2], cfg.disk);
  select.value = cfg.gpu;
  select.dispatchEvent(new Event('change', {bubbles:true}));
  const apply = buttons.find((x) => (x.innerText || '').trim() === 'Применить');
  if (!apply) return JSON.stringify({ok:false,reason:'apply-not-found'});
  apply.click();
  return JSON.stringify({ok:true,ram:inputs[0].value,vram:inputs[1].value,disk:inputs[2].value,gpu:select.value});
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
