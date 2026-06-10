#!/usr/bin/env node
/** One-time: copy Next app pages to src/routes with import rewrites */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const NEXT_ROOT = path.resolve(ROOT, '../claw-delivery-ui/src/app');
const OUT = path.join(ROOT, 'src/routes');

const PAGES = [
  'login', 'landing', 'cockpit', 'assets', 'config', 'design', 'foundation',
  'milestones', 'admin', 'commissioning', 'sandbox', 'proposal', 'preview',
  'plan', 'onboard', 'journey', 'create',
];

function transform(content) {
  return content
    .replace(/^'use client';\r?\n\r?\n?/m, '')
    .replace(/export const metadata = [\s\S]*?;\r?\n\r?\n?/g, '')
    .replace(/\.\.\/\.\.\/\.\.\/components/g, '@/components')
    .replace(/\.\.\/\.\.\/\.\.\/lib/g, '@/lib')
    .replace(/\.\.\/\.\.\/\.\.\/data/g, '@/data')
    .replace(/\.\.\/\.\.\/components/g, '@/components')
    .replace(/\.\.\/\.\.\/lib/g, '@/lib')
    .replace(/\.\.\/\.\.\/data/g, '@/data')
    .replace(/\.\.\/version-bar/g, '@/components/version-bar');
}

fs.mkdirSync(OUT, { recursive: true });

for (const name of PAGES) {
  const src = path.join(NEXT_ROOT, name, 'page.tsx');
  if (!fs.existsSync(src)) {
    console.warn('skip missing', name);
    continue;
  }
  let content = fs.readFileSync(src, 'utf8');
  if (!content.includes('// @ts-nocheck')) {
    content = '// @ts-nocheck\n' + content;
  }
  content = transform(content);
  fs.writeFileSync(path.join(OUT, `${name}.tsx`), content);
  console.log('wrote', name);
}

// module route from module-client
let mod = fs.readFileSync(path.join(NEXT_ROOT, 'module/[key]/module-client.tsx'), 'utf8');
mod = mod
  .replace(/^'use client';\r?\n\r?\n?/m, '')
  .replace(/import \{ use \} from 'react';\r?\n/, '')
  .replace(
    /export default function ModuleClient\(\{[\s\S]*?\}\) \{[\s\S]*?const params[\s\S]*?const key = params\.key[\s\S]*?;/,
    `export default function ModuleRoutePage() {
  const { key: rawKey } = useParams();
  const key = rawKey ?? 'survey';`,
  );
mod = `// @ts-nocheck\nimport { useParams } from 'react-router-dom';\n` + mod.replace(/^\/\/ @ts-nocheck\n/, '');
mod = transform(mod);
fs.writeFileSync(path.join(OUT, 'module.tsx'), mod);
console.log('wrote module');
