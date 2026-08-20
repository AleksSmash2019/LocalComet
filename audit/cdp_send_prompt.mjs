const prompt = process.argv.slice(2).join(' ') || 'Ответь одним предложением: что такое локальная модель?';
const cdpPort = process.env.CDP_PORT || '9223';
const targets = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
const target = targets.find((item) => item.type === 'page');
if (!target?.webSocketDebuggerUrl) throw new Error('No WebView2 page target');
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, { once: true });
  socket.addEventListener('error', reject, { once: true });
});
const escapedPrompt = JSON.stringify(prompt);
const expression = `(async () => {
  const text = ${escapedPrompt};
  const editor = document.querySelector('textarea') || document.querySelector('[contenteditable="true"]');
  if (!editor) return JSON.stringify({ ok: false, reason: 'composer-not-found' });
  editor.focus();
  if (editor instanceof HTMLTextAreaElement || editor instanceof HTMLInputElement) {
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')?.set
      || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
    if (setter) setter.call(editor, text);
    else editor.value = text;
  } else {
    editor.textContent = text;
  }
  editor.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: text }));
  editor.dispatchEvent(new Event('change', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 250));
  const send = [...document.querySelectorAll('button')].find((button) => button.textContent?.includes('Отправить'))
    || [...document.querySelectorAll('[role="button"],button')].find((button) => button.getAttribute('aria-label')?.includes('Отправить'));
  const before = { value: editor.value ?? editor.textContent ?? '', disabled: send?.disabled ?? null };
  if (!send || send.disabled) return JSON.stringify({ ok: false, reason: 'send-disabled', before });
  send.click();
  return JSON.stringify({ ok: true, before, clicked: true });
})()`;
const result = await new Promise((resolve, reject) => {
  const id = 1;
  const timer = setTimeout(() => reject(new Error('CDP send prompt timeout')), 30000);
  const onMessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.id !== id) return;
    clearTimeout(timer);
    socket.removeEventListener('message', onMessage);
    if (message.error) reject(new Error(JSON.stringify(message.error)));
    else resolve(message.result?.result?.value ?? message.result);
  };
  socket.addEventListener('message', onMessage);
  socket.send(JSON.stringify({ id, method: 'Runtime.evaluate', params: { expression, returnByValue: true, awaitPromise: true } }));
});
console.log(result);
socket.close();
