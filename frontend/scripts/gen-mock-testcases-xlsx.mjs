/**
 * 从 proposal-testcases.ts 导出 mock 测试用例new.xlsx（输入模板）
 * 运行：node scripts/gen-mock-testcases-xlsx.mjs
 */
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import XLSX from 'xlsx';

const __dirname = dirname(fileURLToPath(import.meta.url));
const srcPath = join(__dirname, '../src/components/proposal/proposal-testcases.ts');
const outPaths = [
  join(__dirname, '../../mock数据/早期介入/交付预案/输入文件/测试用例new.xlsx'),
  join(__dirname, '../../mock数据/JD2项目_test-boq/早期介入/交付预案/输入文件/测试用例new.xlsx'),
];

const raw = readFileSync(srcPath, 'utf8');
const match = raw.match(/export const ACCEPTANCE_TEST_CASES[^=]*=\s*(\[[\s\S]*?\]);/);
if (!match) {
  console.error('无法解析 ACCEPTANCE_TEST_CASES');
  process.exit(1);
}

const cases = JSON.parse(match[1]);
const rows = cases.map((c) => ({
  一级分类: c.l1,
  二级分类: c.l2,
  三级分类: c.l3,
  用例编号: c.id,
  测试目的: c.purpose,
  测试组网: c.topology,
  预置条件: c.pre,
  测试步骤: (c.steps || []).join('\n'),
}));

const wb = XLSX.utils.book_new();
const ws = XLSX.utils.json_to_sheet(rows);
XLSX.utils.book_append_sheet(wb, ws, '测试用例');
const buf = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });
for (const outPath of outPaths) {
  mkdirSync(dirname(outPath), { recursive: true });
  writeFileSync(outPath, buf);
  console.log(`已生成 ${outPath} (${rows.length} 行)`);
}
