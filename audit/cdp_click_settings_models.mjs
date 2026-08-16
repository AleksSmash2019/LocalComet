const needle = '\u041c\u043e\u0434\u0435\u043b\u0438';
const targets = await (await fetch('http://127.0.0.1:9222/json/list')).json();
const page = targets.find((item) => item.type === 'page');
if (!page?.webSocketDebuggerUrl) throw new Error('No page target');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once: true }); ws.addEventListener('error', reject, { once: true }); });
const expression = `(() => { const needle=${JSON.stringify(needle)}; const candidates=[...document.querySelectorAll('#settings-panel .settings-tabs button')]; const el=candidates.find((x)=>(x.innerText||'').trim()===needle); if(!el) return JSON.stringify({result:'NOT_FOUND',tabs:candidates.map((x)=>(x.innerText||'').trim())}); el.click(); return JSON.stringify({result:'CLICKED',text:(el.innerText||'').trim()}); })()`;
ws.addEventListener('message', (event) => { const message=JSON.parse(event.data); if(message.id!==1)return; ws.close(); if(message.error){console.error(JSON.stringify(message.error));process.exitCode=1;return;} console.log(message.result?.result?.value??JSON.stringify(message.result)); });
ws.send(JSON.stringify({id:1,method:'Runtime.evaluate',params:{expression,returnByValue:true,awaitPromise:true}}));
