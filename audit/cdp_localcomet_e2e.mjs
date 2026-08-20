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
  modelfit: `(() => { const frame = document.querySelector('iframe[src="/modelfit.html"]'); const doc = frame?.contentDocument; if (!doc) return JSON.stringify({ ok: false, reason: 'iframe-not-ready' }); return JSON.stringify({ ok: true, url: frame.src, bodyText: doc.body?.innerText || '', controls: [...doc.querySelectorAll('button,a,input,select,[role="button"]')].map((x) => ({ tag: x.tagName, text: (x.innerText || x.getAttribute('aria-label') || x.getAttribute('title') || x.value || '').trim(), disabled: !!x.disabled })).filter((x) => x.text) }); })()`,
  modelfitClick: `(() => { const frame = document.querySelector('iframe[src="/modelfit.html"]'); const doc = frame?.contentDocument; const needle = 'Выбрать сценарий'; const el = [...(doc?.querySelectorAll('button,a,[role="button"]') || [])].find((x) => (x.innerText || '').includes(needle)); if (!el) return JSON.stringify({ ok: false, reason: 'not-found', bodyText: doc?.body?.innerText || '' }); el.click(); return JSON.stringify({ ok: true, clicked: (el.innerText || '').trim() }); })()`,
  modelfitSelect: `(() => { const frame = document.querySelector('iframe[src="/modelfit.html"]'); const doc = frame?.contentDocument; const needle = 'Русский язык'; const els = [...(doc?.querySelectorAll('button,a,[role="button"],div') || [])].filter((x) => (x.innerText || '').trim() === needle); const el = els[els.length - 1]; if (!el) return JSON.stringify({ ok: false, reason: 'not-found', bodyText: doc?.body?.innerText || '' }); el.click(); return JSON.stringify({ ok: true, tag: el.tagName, clicked: (el.innerText || '').trim(), outer: el.outerHTML.slice(0, 1200) }); })()`,
  modelfitNative: `(async () => { const frame = document.querySelector('iframe[src="/modelfit.html"]'); const w = frame?.contentWindow; const invoke = w?.__TAURI_INTERNALS__?.invoke || window.__TAURI_INTERNALS__?.invoke; if (typeof invoke !== 'function') return JSON.stringify({ ok: false, reason: 'invoke-not-found', iframeTauri: !!w?.__TAURI_INTERNALS__, parentTauri: !!window.__TAURI_INTERNALS__ }); try { const result = await invoke('scan_hardware'); return JSON.stringify({ ok: true, result }); } catch (error) { return JSON.stringify({ ok: false, reason: String(error), stack: error?.stack || '' }); } })()`,
  modelfitScan: `(() => { const frame = document.querySelector('iframe[src="/modelfit.html"]'); const doc = frame?.contentDocument; const el = [...(doc?.querySelectorAll('button,a,[role="button"]') || [])].find((x) => (x.innerText || '').includes('Сканировать ПК')); if (!el) return JSON.stringify({ ok: false, reason: 'not-found', bodyText: doc?.body?.innerText || '' }); el.click(); return JSON.stringify({ ok: true, clicked: (el.innerText || '').trim() }); })()`,
  permission: `(() => { const elements = [...document.querySelectorAll('[aria-pressed]')].map((x) => ({ text: (x.innerText || '').trim(), label: x.getAttribute('aria-label'), title: x.getAttribute('title'), pressed: x.getAttribute('aria-pressed') })); const computer = elements.find((x) => /компьютер|computer/i.test([x.text, x.label, x.title].join(' '))); return JSON.stringify({ computer, prefs: localStorage.getItem('localcomet.ui.preferences.v1') }); })()`,
  runtimeStatus: `(async () => { const invoke = window.__TAURI_INTERNALS__?.invoke || window.__TAURI__?.core?.invoke || window.__TAURI__?.invoke; if (typeof invoke !== 'function') return JSON.stringify({ ok: false, reason: 'invoke-not-found' }); try { return JSON.stringify({ ok: true, result: await invoke('managed_runtime_status') }); } catch (error) { return JSON.stringify({ ok: false, reason: String(error), stack: error?.stack || '' }); } })()`,
  approvalState: `(() => { const dialog = document.querySelector('[role="dialog"]'); return JSON.stringify({ dialog: dialog ? { text: dialog.innerText, html: dialog.outerHTML.slice(0, 3000) } : null, alerts: [...document.querySelectorAll('[role="alert"]')].map((x) => x.innerText) }); })()`,
  tauriGlobals: `(() => { const a = window.__TAURI_INTERNALS__; const b = window.__TAURI__; return JSON.stringify({ internalsType: typeof a, internalsKeys: a && Object.keys(a), invokeType: typeof a?.invoke, tauriType: typeof b, tauriKeys: b && Object.keys(b), coreKeys: b?.core && Object.keys(b.core), coreInvokeType: typeof b?.core?.invoke }); })()`,
  clickAISetup: `(() => { const needle = 'Настроить локальный AI'; const el = [...document.querySelectorAll('button')].find((x) => (x.innerText || '').trim() === needle); if (!el) return JSON.stringify({ ok: false, reason: 'button-not-found' }); el.click(); return JSON.stringify({ ok: true, clicked: (el.innerText || '').trim(), html: el.outerHTML.slice(0, 500) }); })()`,
};

if (!expressions[action]) throw new Error(`Unknown action: ${action}`);
const result = await evaluate(expressions[action]);
console.log(result);
