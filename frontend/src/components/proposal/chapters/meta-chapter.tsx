'use client';

import { useEffect, useState } from 'react';
import { ProposalChapterCard } from '../primitives';
import { SNAPSHOTS, type SnapKey } from '../proposal-data';

interface ChangeRow {
  id: number;
  chapter: string;
  desc: string;
}

/** 把快照的 highlights（形如「6. 机房信息：新增…」）拆成 章节 / 描述 两列 */
function seedRows(snapKey: SnapKey): ChangeRow[] {
  const hs = SNAPSHOTS[snapKey]?.diffSummary?.highlights ?? [];
  return hs.map((h: string, i: number) => {
    const idx = h.indexOf('：');
    const chapter = idx >= 0 ? h.slice(0, idx).trim() : h.trim();
    const desc = idx >= 0 ? h.slice(idx + 1).trim() : '';
    return { id: i + 1, chapter, desc };
  });
}

export function MetaChapter({ snapKey }: { snapKey: SnapKey }) {
  const [rows, setRows] = useState<ChangeRow[]>(() => seedRows(snapKey));

  useEffect(() => {
    setRows(seedRows(snapKey));
  }, [snapKey]);

  const updateRow = (id: number, key: 'chapter' | 'desc', value: string) =>
    setRows((rs) => rs.map((r) => (r.id === id ? { ...r, [key]: value } : r)));

  const addRow = () =>
    setRows((rs) => [...rs, { id: (rs.at(-1)?.id ?? 0) + 1, chapter: '', desc: '' }]);

  const removeRow = (id: number) => setRows((rs) => rs.filter((r) => r.id !== id));

  return (
    <ProposalChapterCard id="panel-meta" title="修改记录">
      <div className="overflow-hidden rounded-md border border-slate-100">
        <table className="w-full border-collapse text-sm">
          <colgroup>
            <col style={{ width: 64 }} />
            <col style={{ width: '28%' }} />
            <col />
            <col style={{ width: 56 }} />
          </colgroup>
          <thead>
            <tr className="bg-slate-50/90 text-left text-sm text-slate-700">
              <th className="px-3 py-2.5 font-semibold">序号</th>
              <th className="px-3 py-2.5 font-semibold">章节</th>
              <th className="px-3 py-2.5 font-semibold">修改描述</th>
              <th className="px-3 py-2.5 font-semibold"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.id} className="border-t border-slate-100 align-top">
                <td className="px-3 py-2 text-slate-400">[{i + 1}]</td>
                <td className="px-2 py-1.5">
                  <input
                    value={r.chapter}
                    onChange={(e) => updateRow(r.id, 'chapter', e.target.value)}
                    placeholder="章节名称"
                    className="w-full rounded border border-transparent bg-transparent px-2 py-1 text-sm text-slate-700 transition-colors hover:border-slate-200 focus:border-blue-400 focus:bg-white focus:outline-none"
                  />
                </td>
                <td className="px-2 py-1.5">
                  <textarea
                    value={r.desc}
                    rows={1}
                    onChange={(e) => updateRow(r.id, 'desc', e.target.value)}
                    placeholder="填写本次修改内容"
                    className="w-full rounded border border-transparent bg-transparent px-2 py-1 text-sm leading-relaxed text-slate-700 transition-colors hover:border-slate-200 focus:border-blue-400 focus:bg-white focus:outline-none resize-none"
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
            {rows.length === 0 && (
              <tr className="border-t border-slate-100">
                <td colSpan={4} className="px-3 py-6 text-center text-sm text-slate-400">
                  暂无修改记录，点击下方「新增一行」开始记录。
                </td>
              </tr>
            )}
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
