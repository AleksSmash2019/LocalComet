const targets = await (await fetch('http://127.0.0.1:9222/json/list')).json();
const page = targets.find((item) => item.type === 'page');
if (!page?.webSocketDebuggerUrl) throw new Error('No page target');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once: true }); ws.addEventListener('error', reject, { once: true }); });
const expression = `(() => { const id='llama-cpp-windows-x86-64-vulkan-bootstrap'; const item=[...document.querySelectorAll('.hf-approved-item')].find((x)=>x.querySelector('[title="'+id+'"]')); return JSON.stringify({time:new Date().toISOString(),itemText:item?.innerText||null,html:item?.innerHTML||null,bodyLines:document.body.innerText.split(/\\n+/).map((x)=>x.trim()).filter(Boolean).filter((x)=>/Vulkan|vulkan|GPU|Скач|загруз|ошиб|failed|completed|percent/i.test(x))}); })()`;
ws.addEventListener('message', (event) => { const message = JSON.parse(event.data); if (message.id !== 1) return; ws.close(); if (message.error) { console.error(JSON.stringify(message.error)); process.exitCode = 1; return; } console.log(message.result?.result?.value ?? JSON.stringify(message.result)); });
ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression, returnByValue: true, awaitPromise: true } }));
