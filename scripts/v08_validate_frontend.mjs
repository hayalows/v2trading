import fs from 'node:fs';
import vm from 'node:vm';

const html = fs.readFileSync('web/index.html', 'utf8');
for (const required of ['V0.8 · Research brief','What to do next','Meaningful changes only','Data trust','lab-insights']) {
  if (!html.includes(required)) throw new Error(`Missing required UI marker: ${required}`);
}
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
if (!scripts.length) throw new Error('No inline application script found');
for (const [i, code] of scripts.entries()) new vm.Script(code, { filename: `inline-${i}.js` });
console.log(`v0.8 frontend validation passed: ${scripts.length} inline script(s)`);
