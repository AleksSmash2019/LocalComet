import fs from 'node:fs';
const path = process.argv[2];
const needles = process.argv.slice(3);
const text = fs.readFileSync(path, 'utf8');
for (const needle of needles) {
  let offset = 0;
  let found = 0;
  while (true) {
    const index = text.indexOf(needle, offset);
    if (index < 0) break;
    const start = Math.max(0, index - 700);
    const end = Math.min(text.length, index + needle.length + 1200);
    console.log(`--- ${needle} occurrence ${++found} at ${index} ---`);
    console.log(text.slice(start, end));
    offset = index + needle.length;
    if (found >= 5) break;
  }
  if (!found) console.log(`--- ${needle}: NOT FOUND ---`);
}
