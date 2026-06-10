#!/usr/bin/env node
/** Build Vite dist + copy to desktop folder for offline demo */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const DIST = path.join(ROOT, 'dist');
const DEST =
  process.env.AIDA_DESKTOP_DIR ||
  path.join(process.env.USERPROFILE || process.env.HOME || '', 'Desktop', 'AIDA-vite-双击即看');

console.log('→ npm run build');
execSync('npm run build', { cwd: ROOT, stdio: 'inherit' });

console.log('→ node scripts/gen-offline-html.mjs (optional SPA shells for file://)');
try {
  execSync('node scripts/gen-offline-html.mjs', { cwd: ROOT, stdio: 'inherit' });
} catch {
  console.warn('gen-offline-html skipped or failed');
}

if (!fs.existsSync(DEST)) fs.mkdirSync(DEST, { recursive: true });

function copyDir(src, dst) {
  fs.mkdirSync(dst, { recursive: true });
  for (const name of fs.readdirSync(src)) {
    const s = path.join(src, name);
    const d = path.join(dst, name);
    if (fs.statSync(s).isDirectory()) copyDir(s, d);
    else fs.copyFileSync(s, d);
  }
}

console.log(`→ copy dist/ → ${DEST}`);
for (const name of fs.readdirSync(DIST)) {
  const s = path.join(DIST, name);
  const d = path.join(DEST, name);
  if (fs.existsSync(d)) fs.rmSync(d, { recursive: true, force: true });
  if (fs.statSync(s).isDirectory()) copyDir(s, d);
  else fs.copyFileSync(s, d);
}

console.log('✓ Done. Open index.html in browser (use local server or file:// with route shells).');
