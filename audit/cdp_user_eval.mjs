import fs from 'node:fs';

const action = process.argv[2];
const value = process.argv.slice(3).join(' ');
const cdpPort = process.env.CDP_PORT || '9222';
const list = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
const target = list.find((item) => item.type === 'page');
if (!target?.webSocketDebuggerUrl) throw new Error('No WebView2 page target');
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, { once: true });
  socket.addEventListener('error', reject, { once: true });
});
let expression;
if (action === 'click-text') {
  const encoded = JSON.stringify(value);
  expression = `(() => { const needle = ${encoded}; const els = [...document.querySelectorAll('button,a,[role="button"]')]; const getText = (x) => (x.innerText || x.getAttribute('aria-label') || x.getAttribute('title') || '').trim(); const el = els.find((x) => getText(x) === needle) || els.find((x) => getText(x).includes(needle)); if (!el) return JSON.stringify({ok:false,reason:'not-found',bodyText:document.body.innerText}); el.click(); return JSON.stringify({ok:true,text:getText(el)}); })()`;
} else if (action === 'dom-summary') {
  expression = `JSON.stringify({bodyText:document.body.innerText, dialogs:[...document.querySelectorAll('[role="dialog"]')].map((x)=>x.innerText), alerts:[...document.querySelectorAll('[role="alert"]')].map((x)=>x.innerText), pressed:[...document.querySelectorAll('[aria-pressed]')].map((x)=>({text:(x.innerText||'').trim(),label:x.getAttribute('aria-label'),pressed:x.getAttribute('aria-pressed')}))})`;
} else if (action === 'composer-style') {
  expression = `(() => { const root=document.querySelector('.composer'); const textarea=document.querySelector('#composer-draft'); const send=document.querySelector('button.send-button'); const rootStyle=root?getComputedStyle(root):null; const taStyle=textarea?getComputedStyle(textarea):null; return JSON.stringify({root:rootStyle?{borderRadius:rootStyle.borderRadius,boxShadow:rootStyle.boxShadow,borderColor:rootStyle.borderColor}:null,textarea:taStyle?{outline:taStyle.outline,boxShadow:taStyle.boxShadow}:null,send:send?{borderRadius:getComputedStyle(send).borderRadius,disabled:send.disabled}:null}); })()`;
} else if (action === 'frame-click-text') {
  const encoded = JSON.stringify(value);
  expression = `(() => { const needle = ${encoded}; const frame = document.querySelector('iframe[src="/modelfit.html"]'); const doc = frame?.contentDocument; if (!doc) return JSON.stringify({ok:false,reason:'iframe-not-ready'}); const els = [...doc.querySelectorAll('button,a,[role="button"]')]; const getText = (x) => (x.innerText || x.getAttribute('aria-label') || x.getAttribute('title') || '').trim(); const el = els.find((x) => getText(x) === needle) || els.find((x) => getText(x).includes(needle)); if (!el) return JSON.stringify({ok:false,reason:'not-found',bodyText:doc.body?.innerText || ''}); el.click(); return JSON.stringify({ok:true,text:getText(el)}); })()`;
  } else if (action === 'settings-summary') {
    expression = `JSON.stringify([...document.querySelectorAll('button,[role="button"],input,select,label')].map((x)=>({tag:x.tagName,text:(x.innerText||x.getAttribute('aria-label')||x.getAttribute('title')||x.value||'').trim().slice(0,300),pressed:x.getAttribute('aria-pressed'),checked:x.checked,disabled:!!x.disabled,role:x.getAttribute('role')})).filter((x)=>x.text || x.pressed !== null || x.checked || x.tag === 'INPUT' || x.tag === 'SELECT'))`;
  } else if (action === 'model-connect-controls') {
    expression = `JSON.stringify({selects:[...document.querySelectorAll('[role="dialog"] select,select')].map((x)=>({value:x.value,disabled:x.disabled,options:[...x.options].map((o)=>({value:o.value,text:o.text,selected:o.selected}))})),buttons:[...document.querySelectorAll('[role="dialog"] button,button')].map((x,i)=>({i,text:(x.innerText||x.getAttribute('aria-label')||'').trim(),disabled:x.disabled})).filter((x)=>x.text)})`;
  } else if (action === 'select-model') {
    const encoded = JSON.stringify(value);
    expression = `(() => { const select=document.querySelector('[role="dialog"] select,select'); if(!select) return JSON.stringify({ok:false,reason:'select-not-found'}); const wanted=${encoded}; if(![...select.options].some((o)=>o.value===wanted)) return JSON.stringify({ok:false,reason:'option-not-found',options:[...select.options].map((o)=>o.value)}); select.value=wanted; select.dispatchEvent(new Event('change',{bubbles:true})); return JSON.stringify({ok:true,value:select.value}); })()`;
  } else if (action === 'settings-matches') {
  expression = `JSON.stringify([...document.querySelectorAll('button,[role="button"],input,select,label')].map((x)=>({tag:x.tagName,text:(x.innerText||x.getAttribute('aria-label')||x.getAttribute('title')||x.value||'').trim().slice(0,300),pressed:x.getAttribute('aria-pressed'),checked:x.checked,disabled:!!x.disabled,role:x.getAttribute('role')})).filter((x)=>/computer|компьют|разреш|permission|runtime|настро/i.test(x.text)))`;
  } else if (action === 'message-summary') {
    expression = `JSON.stringify([...document.querySelectorAll('[data-message-role],.message,.bubble')].map((x)=>({text:(x.innerText||'').trim().slice(0,800),role:x.getAttribute('data-message-role'),class:x.className})).filter((x)=>x.text))`;
  } else if (action === 'skills-summary') {
    expression = `JSON.stringify({dialogs:[...document.querySelectorAll('[role="dialog"]')].map((x)=>({text:(x.innerText||'').split('\\n').filter((line)=>/Навык|skills_list|Command not found|Нет установленных|Установить/.test(line)).slice(0,30)})),bodyMatches:(document.body.innerText||'').split('\\n').filter((line)=>/Навык|skills_list|Command not found|Нет установленных|Установить/.test(line)).slice(0,30)})`;
  } else if (action === 'hf-aria') {
    expression = `JSON.stringify([...document.querySelectorAll('input.hf-search-input')].map((x)=>({type:x.type,placeholder:x.getAttribute('placeholder'),ariaLabel:x.getAttribute('aria-label')})))`;
  } else if (action === 'approval-controls') {
    expression = `JSON.stringify([...document.querySelectorAll('button,[role="button"]')].map((x)=>({text:(x.innerText||x.getAttribute('aria-label')||x.getAttribute('title')||'').trim(),disabled:!!x.disabled,outer:x.outerHTML.slice(0,500)})).filter((x)=>/WAITING|View result|Подтвердить|Отклонить|Повторить|computer_use/i.test(x.text)))`;
  } else if (action === 'cu-status') {
    expression = `JSON.stringify((document.body.innerText||'').split('\\n').filter((line)=>/computer_use|WAITING|PASS|FAIL|SKIPPED|Результат|ошиб|ошибка|ожид|калькулятор|Calculator|выполн|открыт|повторить/i.test(line)).slice(-60))`;
  } else if (action === 'install-invoke-probe') {
    expression = `(() => { const internals = window.__TAURI_INTERNALS__; if (!internals?.invoke) return JSON.stringify({ok:false,reason:'tauri-invoke-unavailable'}); if (window.__localcometInvokeProbeInstalled) return JSON.stringify({ok:true,already:true}); const original = internals.invoke.bind(internals); window.__localcometInvokeProbe = []; internals.invoke = async (cmd, args) => { try { const value = await original(cmd, args); window.__localcometInvokeProbe.push({cmd,ok:true,value: cmd === 'model_turn_start' ? {request_id:value?.request_id,turn_id:value?.turn_id,model_id:value?.model_id} : undefined}); return value; } catch (error) { window.__localcometInvokeProbe.push({cmd,ok:false,error:{code:error?.code,message:error?.message}}); throw error; } }; window.__localcometInvokeProbeInstalled = true; return JSON.stringify({ok:true}); })()`;
  } else if (action === 'read-invoke-probe') {
    expression = `JSON.stringify(window.__localcometInvokeProbe || [])`;
  } else if (action === 'read-model-turn-probe') {
    expression = `JSON.stringify(window.__localcometModelTurnProbe || [])`;
  } else if (action === 'reload-page') {
    expression = `(() => { location.reload(); return JSON.stringify({ok:true}); })()`;
  } else if (action === 'dialog-actions') {
    expression = `JSON.stringify([...document.querySelectorAll('[role="dialog"] button,button')].map((x)=>({text:(x.innerText||x.getAttribute('aria-label')||x.getAttribute('title')||'').trim(),disabled:!!x.disabled})).filter((x)=>/подключ|запустить|закрыть|модель|connect|start|close/i.test(x.text)))`;
  } else if (action === 'read-last-event-probe') {
    expression = `JSON.stringify((window.__localcometModelTurnProbe || []).filter((entry)=>entry.phase === 'event-received').slice(-3))`;
  } else if (action === 'read-last-failure-probe') {
    expression = `(() => { const entries=(window.__localcometModelTurnProbe || []).filter((entry)=>entry.phase==='event-received' && entry.method==='model.turn.failed'); const entry=entries[entries.length-1]; return JSON.stringify(entry ? {method:entry.method,state:entry.state,reply_to:entry.reply_to,object_keys:entry.object_keys,metadata_keys:entry.metadata_keys,metadata_error:entry.metadata_error} : null); })()`;
  } else if (action === 'invoke-model-turn') {
    const encoded = JSON.stringify(value);
    expression = `(async () => { const input = JSON.parse(${encoded}); const invoke = window.__TAURI_INTERNALS__?.invoke; if (!invoke) return JSON.stringify({ok:false,reason:'tauri-invoke-unavailable'}); try { const result = await invoke('model_turn_start', {requestId: input.requestId, chatSessionId: input.chatSessionId, modelId: input.modelId, submittedAtUnixMs: input.submittedAtUnixMs, maxTokens: input.maxTokens, seed: input.seed, effort: input.effort, prompt: input.prompt, fileIds: [], locale: 'ru', bindingFingerprint: input.bindingFingerprint, agentPermissions: input.agentPermissions || {files:true,shell:false,computerUse:false,tools:true,internet:false}, messages: input.messages}); return JSON.stringify({ok:true,result_type:typeof result,result_keys:Object.keys(result || {}),result_raw:JSON.stringify(result)}); } catch (error) { return JSON.stringify({ok:false,error:{code:error?.code || '',message:error?.message || String(error)}}); } })()`;
  } else {
  throw new Error('Unknown action');
}
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
  socket.send(JSON.stringify({id,method:'Runtime.evaluate',params:{expression,returnByValue:true,awaitPromise:true}}));
});
console.log(result);
socket.close();
