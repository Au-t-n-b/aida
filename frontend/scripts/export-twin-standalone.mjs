/* 导出"算力底座孪生"单文件发布版：
 * vite 构建 twin-standalone 入口 → JS/CSS 内联进 HTML → 注入两个子页 base64（物理/数字孪生 srcDoc）。
 * 用法：node scripts/export-twin-standalone.mjs [输出路径]（默认 ../../aida-twin-standalone.html） */
import { build } from 'vite';
import react from '@vitejs/plugin-react';
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const outDir = path.join(frontendDir, 'dist-twin-standalone');
const outFile = path.resolve(process.argv[2] || path.join(frontendDir, '../../aida-twin-standalone.html'));

await build({
  configFile: false,
  root: frontendDir,
  plugins: [react()],
  resolve: { alias: { '@': path.join(frontendDir, 'src') } },
  base: './',
  logLevel: 'warn',
  build: {
    outDir,
    emptyOutDir: true,
    cssCodeSplit: false,
    assetsInlineLimit: 1024 * 1024 * 100, // 字体/图片全部内联为 data URI
    rollupOptions: { input: path.join(frontendDir, 'twin-standalone.html') },
  },
});

let html = readFileSync(path.join(outDir, 'twin-standalone.html'), 'utf-8');
const assets = readdirSync(path.join(outDir, 'assets'));

// CSS 内联
for (const f of assets.filter((f) => f.endsWith('.css'))) {
  const css = readFileSync(path.join(outDir, 'assets', f), 'utf-8').replace(/<\/style/gi, '<\\/style');
  html = html.replace(new RegExp(`<link[^>]*href="\\./assets/${f}"[^>]*>`), () => `<style>${css}</style>`);
}
// JS 内联（</script> 转义防止提前闭合）
for (const f of assets.filter((f) => f.endsWith('.js'))) {
  const js = readFileSync(path.join(outDir, 'assets', f), 'utf-8').replace(/<\/script/gi, '<\\/script');
  html = html.replace(new RegExp(`<script[^>]*src="\\./assets/${f}"[^>]*></script>`), () => `<script type="module">${js}</script>`);
}
if (/\.\/assets\//.test(html)) throw new Error('仍有未内联的资源引用，请检查构建产物');

// 注入两个子页 base64（必须在 bundle 之前执行的经典脚本）
const b64 = (p) => readFileSync(path.join(frontendDir, p)).toString('base64');
const inject = `<script>window.__PHYSICAL_TWIN_B64="${b64('public/twin/physical-twin.html')}";window.__DIGITAL_TWIN_B64="${b64('public/twin/digital-twin.html')}";</script>`;
html = html.replace('<script type="module">', `${inject}<script type="module">`);

writeFileSync(outFile, html);
console.log(`OK ${outFile} (${(html.length / 1024 / 1024).toFixed(1)} MB)`);
