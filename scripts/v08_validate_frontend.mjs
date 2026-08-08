import fs from 'node:fs';
import vm from 'node:vm';

const html = fs.readFileSync('web/index.html', 'utf8');
const required = [
  'Version 1.0',
  'Material+Symbols+Rounded',
  'Understand the market before you inspect the chart.',
  'Next checkpoint',
  'Market at a glance',
  'Trend by timeframe',
  'Meaningful changes',
  'Know what you can trust',
  'bottom-nav',
  'nav-rail',
  'lab-insights',
  's3.tradingview.com',
  'aria-label="Primary navigation"',
  'min-width:48px',
  ':focus-visible',
  'prefers-reduced-motion'
];
for (const marker of required) {
  if (!html.includes(marker)) throw new Error(`Missing v1 UI/accessibility marker: ${marker}`);
}
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
if (!scripts.length) throw new Error('No inline application script found');
for (const [i, code] of scripts.entries()) new vm.Script(code, { filename: `inline-${i}.js` });

const touchRules = [...html.matchAll(/min-(?:width|height):48px/g)].length;
if (touchRules < 2) throw new Error('Expected explicit 48px minimum interactive target rules');
if (!html.includes('@media(min-width:960px)')) throw new Error('Missing expanded adaptive layout breakpoint');
if (!html.includes('@media(min-width:700px)')) throw new Error('Missing medium adaptive layout breakpoint');

console.log(`v1.0 frontend validation passed: ${scripts.length} inline script(s), adaptive navigation and accessibility markers present`);
