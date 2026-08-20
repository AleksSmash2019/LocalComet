const port = process.env.CDP_PORT || '9223';
const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const target = targets.find((item) => item.type === 'page');
if (!target?.webSocketDebuggerUrl) throw new Error('No page target');
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once:true }); ws.addEventListener('error', reject, { once:true }); });
const expression = `JSON.stringify([...document.querySelectorAll('select')].map((x,i)=>({i,value:x.value,options:[...x.options].map(o=>({value:o.value,text:o.text})).filter(o=>/Qwen|custom|GGUF/i.test(o.value+' '+o.text))})).filter(x=>x.options.length))`;
const result = await new Promise((resolve, reject) => { const timer=setTimeout(()=>reject(new Error('timeout')),15000); const listener=(event)=>{const m=JSON.parse(event.data);if(m.id!==1)return;clearTimeout(timer);ws.removeEventListener('message',listener);if(m.error)reject(new Error(JSON.stringify(m.error)));else resolve(m.result?.result?.value);};ws.addEventListener('message',listener);ws.send(JSON.stringify({id:1,method:'Runtime.evaluate',params:{expression,returnByValue:true}})); });
console.log(result); ws.close();
