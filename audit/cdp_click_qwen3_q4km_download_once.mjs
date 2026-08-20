const port = process.env.CDP_PORT || '9223';
const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const target = targets.find((item) => item.type === 'page');
if (!target?.webSocketDebuggerUrl) throw new Error('No page target');
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once:true }); ws.addEventListener('error', reject, { once:true }); });
const expression = `(() => { const wanted='Qwen3-1.7B.Q4_K_M.gguf'; const nodes=[...document.querySelectorAll('*')].filter(x=>(x.textContent||'').trim()===wanted); const node=nodes[0]; if(!node) return JSON.stringify({ok:false,reason:'file-not-found'}); let el=node; for(let i=0;i<6 && el;i++,el=el.parentElement){ const button=[...el.querySelectorAll('button')].find(x=>(x.innerText||'').trim()==='Скачать'); if(button){button.click(); return JSON.stringify({ok:true,ancestor:el.tagName,buttonText:button.innerText});} } return JSON.stringify({ok:false,reason:'download-button-not-found',tag:node.tagName}); })()`;
const result = await new Promise((resolve, reject) => { const timer=setTimeout(()=>reject(new Error('timeout')),15000); const listener=(event)=>{const m=JSON.parse(event.data);if(m.id!==1)return;clearTimeout(timer);ws.removeEventListener('message',listener);if(m.error)reject(new Error(JSON.stringify(m.error)));else resolve(m.result?.result?.value);};ws.addEventListener('message',listener);ws.send(JSON.stringify({id:1,method:'Runtime.evaluate',params:{expression,returnByValue:true}})); });
console.log(result); ws.close();
