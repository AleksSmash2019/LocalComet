const action = process.argv[2] || 'inspect';

async function getTarget() {
  const response = await fetch('http://127.0.0.1:9222/json/list');
  const targets = await response.json();
  const target = targets.find((item) => item.type === 'page');
  if (!target?.webSocketDebuggerUrl) throw new Error('No WebView2 page target');
  return target;
}

async function evaluate(expression) {
  const target = await getTarget();
  const socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, { once: true });
    socket.addEventListener('error', reject, { once: true });
  });
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
    socket.send(JSON.stringify({
      id,
      method: 'Runtime.evaluate',
      params: { expression, returnByValue: true, awaitPromise: true },
    }));
  });
  socket.close();
  return result;
}

const expressions = {
  inspect: `JSON.stringify({
    url: location.href,
    title: document.title,
    bodyText: document.body.innerText,
    controls: [...document.querySelectorAll('button,a,[role="button"],input')].map((el) => ({
      tag: el.tagName,
      text: (el.innerText || el.getAttribute('aria-label') || el.getAttribute('title') || el.value || '').trim(),
      disabled: !!el.disabled,
      role: el.getAttribute('role'),
    })).filter((item) => item.text)
  })`,
  snapshot: `JSON.stringify({ url: location.href, title: document.title, bodyText: document.body.innerText })`,
  clickSettings: `(() => { const el = [...document.querySelectorAll('button,a,[role="button"]')].find((x) => (x.innerText || '').includes('Настроить локальный AI')); if (!el) return 'NOT_FOUND'; el.click(); return 'CLICKED:' + el.innerText.trim(); })()`,
  clickChat: `(() => { const el = [...document.querySelectorAll('button,a,[role="button"]')].find((x) => (x.innerText || '').trim() === 'Чат' || (x.innerText || '').trim() === 'Chat'); if (!el) return 'NOT_FOUND'; el.click(); return 'CLICKED:' + el.innerText.trim(); })()`,
  clickHf: `(() => { const el = [...document.querySelectorAll('button,a,[role="button"]')].find((x) => (x.innerText || '').includes('Модели НФ')); if (!el) return 'NOT_FOUND'; el.click(); return 'CLICKED:' + el.innerText.trim(); })()`,
  clickFit: `(() => { const el = [...document.querySelectorAll('button,a,[role="button"]')].find((x) => (x.innerText || '').includes('Подобрать модель')); if (!el) return 'NOT_FOUND'; el.click(); return 'CLICKED:' + el.innerText.trim(); })()`,
};

if (!expressions[action]) throw new Error(`Unknown action: ${action}`);
const result = await evaluate(expressions[action]);
console.log(result);
