#!/usr/bin/env node
/**
 * Sync framework-agnostic sources from claw-delivery-ui (Next) into this Vite project.
 * Does NOT overwrite routes/, compat/, main.tsx, router.tsx.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const NEXT_SRC = path.resolve(ROOT, '../claw-delivery-ui/src');

const DIRS = ['components', 'data', 'lib', 'types'];
const FILES = [['app/globals.css', 'styles/globals.css']];

function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const name of fs.readdirSync(src)) {
    const s = path.join(src, name);
    const d = path.join(dest, name);
    if (fs.statSync(s).isDirectory()) copyDir(s, d);
    else fs.copyFileSync(s, d);
  }
}

for (const dir of DIRS) {
  const from = path.join(NEXT_SRC, dir);
  const to = path.join(ROOT, 'src', dir);
  if (!fs.existsSync(from)) {
    console.warn('skip missing', from);
    continue;
  }
  if (fs.existsSync(to)) fs.rmSync(to, { recursive: true, force: true });
  copyDir(from, to);
  console.log('synced', dir);
}

for (const [fromRel, toRel] of FILES) {
  const from = path.join(NEXT_SRC, fromRel);
  const to = path.join(ROOT, 'src', toRel);
  fs.mkdirSync(path.dirname(to), { recursive: true });
  fs.copyFileSync(from, to);
  console.log('synced', toRel);
}

console.log('\nReminder: re-apply compat imports if app-shell/claw-rail were overwritten:');
console.log("  next/link -> @/compat/link");
console.log("  next/navigation -> @/compat/navigation");
