'use client';

import { useState } from 'react';
import { ProposalChapterCard } from '../primitives';
import { SOFTWARE_STACK } from '../proposal-data';

const SOURCE_OPTIONS = ['自动解析', '人工录入'];

interface SoftRow {
  id: number;
  type: string;
  isHW: boolean;
  software: string;
  ver: string;
  source: string;
  remark: string;
}
type SoftField = 'type' | 'software' | 'ver' | 'source' | 'remark';

const INPUT_CLS =
  'w-full rounded border border-transparent bg-transparent px-2 py-1 text-sm text-slate-700 transition-colors hover:border-slate-200 focus:border-blue-400 focus:bg-white focus:outline-none';

export function SoftwareChapter() {
  const [rows, setRows] = useState<SoftRow[]>(() =>
    SOFTWARE_STACK.map((s, i) => ({
      id: i + 1,
      type: s.type,
      isHW: s.isHW,
      software: s.software,
      ver: s.ver,
      source: s.source,
      remark: s.remark,
    })),
  );

  const update = (id: number, key: SoftField, value: string) =>
    setRows((rs) => rs.map((r) => (r.id === id ? { ...r, [key]: value } : r)));
  const updateHW = (id: number, value: boolean) =>
    setRows((rs) => rs.map((r) => (r.id === id ? { ...r, isHW: value } : r)));
  const addRow = () =>
    setRows((rs) => [
      ...rs,
      { id: (rs.at(-1)?.id ?? 0) + 1, type: '', isHW: true, software: '', ver: '', source: '自动解析', remark: '' },
    ]);
  const removeRow = (id: number) => setRows((rs) => rs.filter((r) => r.id !== id));

  return (
    <ProposalChapterCard id="sec-ch-4" title="4. 软件配置信息">
      <div className="overflow-hidden rounded-md border border-slate-100">
        <table className="w-full table-fixed border-collapse text-sm">
          <thead>
            <tr className="bg-slate-50/90 text-left text-sm text-slate-700">
              <th className="px-3 py-2.5 font-semibold">类型</th>
              <th className="px-3 py-2.5 font-semibold">华为软件</th>
              <th className="px-3 py-2.5 font-semibold">软件型号</th>
              <th className="px-3 py-2.5 font-semibold">版本</th>
              <th className="px-3 py-2.5 font-semibold">来源</th>
              <th className="px-3 py-2.5 font-semibold">备注</th>
              <th className="w-10 px-3 py-2.5 font-semibold"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-slate-100 align-middle">
                <td className="px-2 py-1.5">
                  <input value={r.type} onChange={(e) => update(r.id, 'type', e.target.value)} className={INPUT_CLS} />
                </td>
                <td className="px-2 py-1.5">
                  <select
                    value={r.isHW ? '是' : '否'}
                    onChange={(e) => updateHW(r.id, e.target.value === '是')}
                    className={`${INPUT_CLS} cursor-pointer`}
                  >
                    <option value="是">是</option>
                    <option value="否">否</option>
                  </select>
                </td>
                <td className="px-2 py-1.5">
                  <input
                    value={r.software}
                    onChange={(e) => update(r.id, 'software', e.target.value)}
                    className={INPUT_CLS}
                  />
                </td>
                <td className="px-2 py-1.5">
                  <input
                    value={r.ver}
                    onChange={(e) => update(r.id, 'ver', e.target.value)}
                    className={`${INPUT_CLS} font-mono text-xs`}
                  />
                </td>
                <td className="px-2 py-1.5">
                  <select
                    value={r.source}
                    onChange={(e) => update(r.id, 'source', e.target.value)}
                    className={`${INPUT_CLS} cursor-pointer`}
                  >
                    {(SOURCE_OPTIONS.includes(r.source) ? SOURCE_OPTIONS : [r.source, ...SOURCE_OPTIONS]).map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-2 py-1.5">
                  <input
                    value={r.remark}
                    onChange={(e) => update(r.id, 'remark', e.target.value)}
                    placeholder="备注"
                    className={INPUT_CLS}
                  />
                </td>
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
