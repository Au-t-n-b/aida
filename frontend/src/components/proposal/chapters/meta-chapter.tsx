'use client';

import { useEffect, useState } from 'react';
import { ProposalChapterCard } from '../primitives';
import type { CumulativeChangeEntry } from '@/lib/proposal-api';

interface DisplayRow {
  id: number;
  seq: number;
  chapter: string;
  desc: string;
  editable: boolean;
}

/** 将累计修改记录展开为「章节 / 修改描述」行（发布快照只读，手工行可编辑） */
function cumulativeToDisplayRows(entries: CumulativeChangeEntry[]): DisplayRow[] {
  const rows: DisplayRow[] = [];
  let id = 1;
  let fallbackSeq = 0;

  const pushRow = (row: Omit<DisplayRow, 'id' | 'seq'> & { seq?: number }) => {
    fallbackSeq += 1;
    rows.push({
      id: id++,
      seq: row.seq ?? fallbackSeq,
      chapter: row.chapter,
      desc: row.desc,
      editable: row.editable,
    });
  };

  for (const e of entries) {
    const isManual = e.source === 'manual' || (e.editable !== false && e.source !== 'snapshot');

    if (isManual) {
      pushRow({
        seq: e.seq,
        chapter: e.chapter || '',
        desc: e.changeDescription || '',
        editable: true,
      });
      continue;
    }

    // changeRecords 行已有独立 chapter/description，勿再按「章节：描述」合并文本解析
    if ((e.chapter ?? '').trim()) {
      pushRow({
        seq: e.seq,
        chapter: e.chapter!.trim(),
        desc: e.changeDescription || '',
        editable: false,
      });
      continue;
    }

    const text = (e.changeDescription || '').trim();
    if (!text || text === '—') continue;

    const parts = text.split('；').map((p) => p.trim()).filter(Boolean);
    if (parts.length === 0) {
      pushRow({ seq: e.seq, chapter: '', desc: text, editable: false });
      continue;
    }

    for (const part of parts) {
      const colon = part.indexOf('：');
      if (colon >= 0) {
        pushRow({
          seq: e.seq,
          chapter: part.slice(0, colon).trim(),
          desc: part.slice(colon + 1).trim(),
          editable: false,
        });
      } else {
        pushRow({ seq: e.seq, chapter: part, desc: '', editable: false });
      }
    }
  }

  return rows;
}

function manualEntriesFromRows(rows: DisplayRow[]): CumulativeChangeEntry[] {
  const snapshotCount = rows.filter((r) => !r.editable).length;
  return rows
    .filter((r) => r.editable)
    .filter((r) => r.chapter.trim() || r.desc.trim())
    .map((r, i) => ({
      seq: r.seq || snapshotCount + i + 1,
      chapter: r.chapter.trim(),
      changeDescription: r.desc,
      editable: true,
      source: 'manual' as const,
    }));
}

export function MetaChapter({
  cumulativeLog = [],
  readOnly = false,
  onCumulativeLogChange,
}: {
  cumulativeLog?: CumulativeChangeEntry[];
  readOnly?: boolean;
  onCumulativeLogChange?: (manualEntries: CumulativeChangeEntry[]) => void;
}) {
  const [rows, setRows] = useState<DisplayRow[]>(() => cumulativeToDisplayRows(cumulativeLog));

  useEffect(() => {
    setRows(cumulativeToDisplayRows(cumulativeLog));
  }, [cumulativeLog]);

  const emitManual = (next: DisplayRow[]) => {
    setRows(next);
    onCumulativeLogChange?.(manualEntriesFromRows(next));
  };

  const updateRow = (id: number, key: 'chapter' | 'desc', value: string) =>
    emitManual(rows.map((r) => (r.id === id ? { ...r, [key]: value } : r)));

  const addRow = () => {
    const nextSeq = (rows.at(-1)?.seq ?? 0) + 1;
    emitManual([
      ...rows,
      { id: (rows.at(-1)?.id ?? 0) + 1, seq: nextSeq, chapter: '', desc: '', editable: true },
    ]);
  };

  const removeRow = (id: number) => emitManual(rows.filter((r) => r.id !== id));

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
            <tr className="bg-slate-50/90 text-left text-xs text-slate-500">
              <th className="px-3 py-2 font-normal">序号</th>
              <th className="px-3 py-2 font-normal">章节</th>
              <th className="px-3 py-2 font-normal">修改描述</th>
              <th className="px-3 py-2 font-normal"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.id} className="border-t border-slate-100 align-top">
                <td className="px-3 py-2 text-slate-400">[{r.seq}]</td>
                <td className="px-2 py-1.5">
                  {readOnly || !r.editable ? (
                    <span className="px-2 py-1 text-sm text-slate-700">{r.chapter || '—'}</span>
                  ) : (
                    <input
                      value={r.chapter}
                      onChange={(e) => updateRow(r.id, 'chapter', e.target.value)}
                      placeholder="章节名称"
                      className="w-full rounded border border-transparent bg-transparent px-2 py-1 text-sm text-slate-700 transition-colors hover:border-slate-200 focus:border-blue-400 focus:bg-white focus:outline-none"
                    />
                  )}
                </td>
                <td className="px-2 py-1.5">
                  {readOnly || !r.editable ? (
                    <span className="px-2 py-1 text-sm leading-relaxed text-slate-700">
                      {r.desc || '—'}
                    </span>
                  ) : (
                    <textarea
                      value={r.desc}
                      rows={1}
                      onChange={(e) => updateRow(r.id, 'desc', e.target.value)}
                      placeholder="填写本次修改内容"
                      className="w-full rounded border border-transparent bg-transparent px-2 py-1 text-sm leading-relaxed text-slate-700 transition-colors hover:border-slate-200 focus:border-blue-400 focus:bg-white focus:outline-none resize-none"
                    />
                  )}
                </td>
                <td className="px-2 py-1.5 text-center">
                  {!readOnly && r.editable && (
                    <button
                      type="button"
                      onClick={() => removeRow(r.id)}
                      title="删除此行"
                      className="rounded p-1 text-slate-300 transition-colors hover:bg-red-50 hover:text-red-500"
                    >
                      ✕
                    </button>
                  )}
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
      {!readOnly && (
        <button
          type="button"
          onClick={addRow}
          className="mt-3 rounded-md border border-dashed border-slate-300 px-3 py-1.5 text-xs font-normal text-slate-500 transition-colors hover:border-blue-400 hover:text-blue-600"
        >
          ＋ 新增一行
        </button>
      )}
    </ProposalChapterCard>
  );
}
