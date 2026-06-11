#!/usr/bin/env node
/**
 * BrowserRouter + file://: duplicate index.html per route path so direct opens work.
 * Run after vite build. Requires dist/index.html and assets with base './'.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DIST = path.join(path.resolve(__dirname, '..'), 'dist');

const ROUTES = [
  'login', 'landing', 'cockpit', 'assets', 'config', 'design', 'foundation',
  'milestones', 'admin', 'commissioning', 'sandbox', 'proposal', 'preview',
  'plan', 'onboard', 'journey', 'create',
];

const MODULE_KEYS = ['survey', 'modeling', 'job', 'design', 'install', 'deploy', 'accept'];

if (!fs.existsSync(path.join(DIST, 'index.html'))) {
  console.error('dist/index.html missing — run vite build first');
  process.exit(1);
}

const rootHtml = fs.readFileSync(path.join(DIST, 'index.html'), 'utf8');

function depthPrefix(depth) {
  if (depth <= 0) return './';
  return '../'.repeat(depth);
}

function rewriteForDepth(html, depth) {
  const prefix = depthPrefix(depth);
  let out = html;
  out = out.replace(/(href|src)="\/assets\//g, `$1="${prefix}assets/`);
  out = out.replace(/(href|src)="\/([^/"][^"]*)"/g, (m, attr, val) => {
    if (val.startsWith('assets/')) return m;
    return `${attr}="${prefix}${val}"`;
  });
  return out;
}

function writeRoute(routePath, depth) {
  const dir = path.join(DIST, routePath);
  fs.mkdirSync(dir, { recursive: true });
  const html = rewriteForDepth(rootHtml, depth);
  fs.writeFileSync(path.join(dir, 'index.html'), html);
}

for (const r of ROUTES) writeRoute(r, 1);

for (const key of MODULE_KEYS) {
  writeRoute(path.join('module', key), 2);
}

console.log(`✓ Wrote offline shells for ${ROUTES.length} routes + ${MODULE_KEYS.length} module keys`);
