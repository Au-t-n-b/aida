#!/usr/bin/env node
/**
 * @ts-nocheck 守门
 * - 比对当前 @ts-nocheck 文件数与 baseline
 * - 多了 → 失败（不允许新增）
 * - 少了 → 自动更新 baseline + 成功
 * - 持平 → 成功
 *
 * 用法：node scripts/check-ts-nocheck.mjs
 *
 * Baseline 文件：.ts-nocheck-baseline（仓库根目录）
 * 内容仅一行整数，表示当前允许的最大 @ts-nocheck 文件数。
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const BASELINE_PATH = path.join(ROOT, '.ts-nocheck-baseline');
const SRC = path.join(ROOT, 'src');

function walk(dir, acc = []) {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name);
    const stat = fs.statSync(p);
    if (stat.isDirectory()) walk(p, acc);
    else if (/\.(ts|tsx)$/.test(name)) acc.push(p);
  }
  return acc;
}

const files = walk(SRC);
const offenders = files.filter(f => {
  const head = fs.readFileSync(f, 'utf8').slice(0, 200);
  return /@ts-nocheck/.test(head);
});
const count = offenders.length;

let baseline = Number.POSITIVE_INFINITY;
try {
  baseline = parseInt(fs.readFileSync(BASELINE_PATH, 'utf8').trim(), 10);
} catch {
  baseline = count;
  fs.writeFileSync(BASELINE_PATH, `${count}\n`);
  console.log(`✓ baseline 初始化：${count}`);
  process.exit(0);
}

if (count > baseline) {
  console.error(`\n❌ @ts-nocheck 文件数 ${count} 超出 baseline ${baseline}。`);
  console.error('新增 @ts-nocheck 不允许。请去掉首行 // @ts-nocheck 并补上类型。\n');
  console.error('当前文件清单：');
  offenders.slice(0, baseline + 5).forEach(f => {
    console.error('  · ' + path.relative(ROOT, f));
  });
  process.exit(1);
}

if (count < baseline) {
  fs.writeFileSync(BASELINE_PATH, `${count}\n`);
  console.log(`✓ @ts-nocheck 减少：${baseline} → ${count}，baseline 自动更新。`);
} else {
  console.log(`✓ @ts-nocheck 数维持在 ${count}（baseline ${baseline}）。`);
}
