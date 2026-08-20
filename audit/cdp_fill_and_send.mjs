const prompt = process.argv.slice(2).join(' ') || 'Кратко ответь по-русски: это проверка локального inference flow LocalComet.';

const cdpPort = process.env.CDP_PORT || '9222';

async function getTarget() {
  const response = await fetch(`http://127.0.0.1:${cdpPort}/json/list`);
  const targets = await response.json();
  const target = targets.find((item) => item.type === 'page');
  if (!target?.webSocketDebuggerUrl) throw new Error('No WebView2 page target');
  return target;
}

async function evaluate(expression) {
  const target = await getTarget();
  const socket = new WebSocket(target.webSocketDebuggerUrl);
  return await new Promise((resolve, reject) => {
    const id = 1;
    const timeout = setTimeout(() => {
      socket.close();
      reject(new Error('CDP Runtime.evaluate timeout'));
    }, 30000);
    const onMessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.id !== id) return;
      clearTimeout(timeout);
      socket.removeEventListener('message', onMessage);
      socket.close();
      if (message.error) reject(new Error(JSON.stringify(message.error)));
      else resolve(message.result?.result?.value ?? message.result);
    };
    socket.addEventListener('message', onMessage);
    socket.addEventListener('open', () => {
      socket.send(JSON.stringify({
        id,
        method: 'Runtime.evaluate',
        params: { expression, returnByValue: true, awaitPromise: true },
      }));
    });
  });
}

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
  await new Promise((resolve) => setTimeout(resolve, 150));
  const send = [...document.querySelectorAll('button')].find((button) => button.textContent?.includes('Отправить'))
    || [...document.querySelectorAll('[role="button"],button')].find((button) => button.getAttribute('aria-label')?.includes('Отправить'));
  const before = {
    value: editor.value ?? editor.textContent ?? '',
    disabled: send?.disabled ?? null,
    editor: { tag: editor.tagName, type: editor.getAttribute('type'), aria: editor.getAttribute('aria-label'), outer: editor.outerHTML.slice(0, 600) },
    send: send ? { outer: send.outerHTML.slice(0, 800), text: send.textContent } : null,
    buttons: [...document.querySelectorAll('button')].map((button) => ({ text: button.textContent?.trim(), disabled: button.disabled, aria: button.getAttribute('aria-label') })).slice(-5),
  };
  if (!send || send.disabled) return JSON.stringify({ ok: false, reason: 'send-disabled', before });
  send.click();
  return JSON.stringify({ ok: true, before, clicked: true });
})()`;

try {
  console.log(await evaluate(expression));
} catch (error) {
  console.error(error.stack || error);
  process.exitCode = 1;
}
