'use client';

import { useState } from 'react';
import { ProposalChapterCard } from '../primitives';
import { INTEL_PARTS } from '../proposal-data';

const PART_TYPES = ['CPU', 'NPU', 'DPU', 'GPU', '网卡', 'RAID卡', '内存', '硬盘', '电源', '主板'];
const SOURCE_TEXT: Record<string, string> = { BOQ: '自动解析', HLD: '人工录入', 人工: '人工录入' };
const srcLabel = (s: string) => SOURCE_TEXT[s] ?? s;

interface PartRow {
  id: number;
  cat: string;
  code: string;
  vendor: string;
  name: string;
  source: string;
}
type PartField = 'cat' | 'code' | 'vendor' | 'name';

const INPUT_CLS =
  'w-full rounded border border-transparent bg-transparent px-2 py-1 text-sm text-slate-700 transition-colors hover:border-slate-200 focus:border-blue-400 focus:bg-white focus:outline-none';

export function PartsChapter() {
  const [rows, setRows] = useState<PartRow[]>(() =>
    INTEL_PARTS.map((p, i) => ({
      id: i + 1,
      cat: p.cat,
      code: p.code,
      vendor: p.vendor,
      name: p.name,
      source: p.source,
    })),
  );

  const update = (id: number, key: PartField, value: string) =>
    setRows((rs) => rs.map((r) => (r.id === id ? { ...r, [key]: value } : r)));
  const addRow = () =>
    setRows((rs) => [
      ...rs,
      { id: (rs.at(-1)?.id ?? 0) + 1, cat: 'CPU', code: '', vendor: '', name: '', source: '自动解析' },
    ]);
  const removeRow = (id: number) => setRows((rs) => rs.filter((r) => r.id !== id));

  return (
    <ProposalChapterCard id="sec-ch-3" title="3. 部件配置信息">
      <div className="overflow-hidden rounded-md border border-slate-100">
        <table className="w-full table-fixed border-collapse text-sm">
          <thead>
            <tr className="bg-slate-50/90 text-left text-sm text-slate-700">
              <th className="px-3 py-2.5 font-semibold">部件类型</th>
              <th className="px-3 py-2.5 font-semibold">部件编码</th>
              <th className="px-3 py-2.5 font-semibold">厂商</th>
              <th className="px-3 py-2.5 font-semibold">部件名称</th>
              <th className="px-3 py-2.5 font-semibold">来源</th>
              <th className="w-10 px-3 py-2.5 font-semibold"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-slate-100 align-middle">
                <td className="px-2 py-1.5">
                  <select
                    value={r.cat}
                    onChange={(e) => update(r.id, 'cat', e.target.value)}
                    className={`${INPUT_CLS} cursor-pointer`}
                  >
                    {(PART_TYPES.includes(r.cat) ? PART_TYPES : [r.cat, ...PART_TYPES]).map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-2 py-1.5">
                  <input
                    value={r.code}
                    onChange={(e) => update(r.id, 'code', e.target.value)}
                    className={`${INPUT_CLS} font-mono text-xs`}
                  />
                </td>
                <td className="px-2 py-1.5">
                  <input value={r.vendor} onChange={(e) => update(r.id, 'vendor', e.target.value)} className={INPUT_CLS} />
                </td>
                <td className="px-2 py-1.5">
                  <input value={r.name} onChange={(e) => update(r.id, 'name', e.target.value)} className={INPUT_CLS} />
                </td>
                <td className="px-3 py-1.5 text-slate-500">{srcLabel(r.source)}</td>
                <td className="px-2 py-1.5 text-center">
                  <button
                    type="button"
                    onClick={() => removeRow(r.id)}
                    title="删除此行"
                    className="rounded p-1 text-slate-300 transition-colors hover:bg-red-50 hover:text-red-500"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button
        type="button"
        onClick={addRow}
        className="mt-3 rounded-md border border-dashed border-slate-300 px-3 py-1.5 text-xs font-normal text-slate-500 transition-colors hover:border-blue-400 hover:text-blue-600"
      >
        ＋ 新增一行
      </button>
    </ProposalChapterCard>
  );
}
