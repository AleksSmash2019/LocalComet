const port = process.env.CDP_PORT || '9223';
const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const target = targets.find((item) => item.type === 'page');
if (!target?.webSocketDebuggerUrl) throw new Error('No page target');
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once:true }); ws.addEventListener('error', reject, { once:true }); });
const expression = `JSON.stringify({body:(document.body.innerText||'').split('\\n').filter(x=>/Qwen3|custom-|Импорт|Модель|SHA|Источник/.test(x)).slice(-80), selects:[...document.querySelectorAll('select')].map((x,i)=>({i,value:x.value,options:[...x.options].map(o=>({value:o.value,text:o.text}))})),buttons:[...document.querySelectorAll('button')].map((x,i)=>({i,text:(x.innerText||'').trim(),disabled:x.disabled})).filter(x=>/Импорт|Подключ|Скачать|Установ|Обнов|Отключ/.test(x.text))})`;
const payload = await new Promise((resolve, reject) => { const timer=setTimeout(()=>reject(new Error('timeout')),15000); const listener=(event)=>{const m=JSON.parse(event.data);if(m.id!==1)return;clearTimeout(timer);ws.removeEventListener('message',listener);if(m.error)reject(new Error(JSON.stringify(m.error)));else resolve(m.result?.result?.value);};ws.addEventListener('message',listener);ws.send(JSON.stringify({id:1,method:'Runtime.evaluate',params:{expression,returnByValue:true}})); });
console.log(payload); ws.close();
