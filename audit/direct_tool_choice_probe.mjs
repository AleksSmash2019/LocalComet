import { readFileSync } from 'node:fs';

const port = process.argv[2] || '52797';
const base = `http://127.0.0.1:${port}/v1`;
const apiKey = readFileSync('C:\\Users\\DNS\\AppData\\Local\\LocalComet\\runtime-state\\key-403ff0435dc1d38145ffe6cb219ef254.txt', 'utf8').trim();
const modelsResponse = await fetch(`${base}/models`);
const models = await modelsResponse.json();
const model = models?.data?.[0]?.id;
if (!model) throw new Error(`No model id: ${JSON.stringify(models)}`);
const tool = {
  type: 'function',
  function: {
    name: 'computer_use',
    description: 'Open an allowlisted desktop app after user approval.',
    parameters: {
      type: 'object',
      properties: {
        action: { type: 'string', enum: ['open_app'] },
        target: { type: 'string' },
      },
      required: ['action', 'target'],
    },
  },
};
const choices = [
  'auto',
  'required',
  { type: 'function', function: { name: 'computer_use' } },
];
for (const toolChoice of choices) {
  const response = await fetch(`${base}/chat/completions`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: `Bearer ${apiKey}` },
    body: JSON.stringify({
      model,
      messages: [
        {
          role: 'system',
          content: 'You are a desktop assistant. Computer Use is enabled. When asked to open an app, MUST call computer_use with action open_app and target. Do not answer with prose.',
        },
        { role: 'user', content: 'Open the calculator app now.' },
      ],
      tools: [tool],
      tool_choice: toolChoice,
      stream: false,
      max_tokens: 256,
      temperature: 0,
    }),
  });
  const body = await response.json();
  const message = body?.choices?.[0]?.message;
  console.log(JSON.stringify({
    toolChoice,
    status: response.status,
    finishReason: body?.choices?.[0]?.finish_reason,
    content: message?.content ?? null,
    toolCalls: message?.tool_calls ?? null,
    error: body?.error ?? null,
  }));
}
