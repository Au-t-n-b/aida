'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ProposalChapterCard } from '../primitives';
import { roomRackApi, type RoomRackRow } from '@/lib/proposal-api';

const INPUT_CLS =
  'w-full rounded border border-transparent bg-transparent px-2 py-1 text-sm text-slate-700 transition-colors hover:border-slate-200 focus:border-blue-400 focus:bg-white focus:outline-none';
const DEL_BTN_CLS =
  'rounded p-1 text-slate-300 transition-colors hover:bg-red-50 hover:text-red-500';
const TH_CLS = 'px-3 py-2.5 font-semibold';
const HEAD_TR_CLS = 'bg-slate-50/90 text-left text-sm text-slate-700';

const COLS: { key: keyof RoomRackRow; label: string }[] = [
  { key: 'pod_name', label: 'PoD名称' },
  { key: 'room_name', label: '机房名称' },
  { key: 'compute', label: '计算柜' },
  { key: 'bus', label: '总线柜' },
  { key: 'param_leaf', label: '参数面Leaf柜' },
  { key: 'biz_leaf', label: '业务面Leaf柜' },
  { key: 'mgmt', label: '管理面柜' },
  { key: 'sample_leaf', label: '样本面Leaf柜' },
];

const EMPTY_ROW = {
  pod_name: '',
  room_name: '',
  compute: '',
  bus: '',
  param_leaf: '',
  biz_leaf: '',
  mgmt: '',
  sample_leaf: '',
};

export function RoomChapter() {
  const [rows, setRows] = useState<RoomRackRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const debounceTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await roomRackApi.list();
      setRows(data.rows);
    } catch (e) {
      setToast({ type: 'error', message: e instanceof Error ? e.message : '加载失败' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => () => debounceTimers.current.forEach((timer) => clearTimeout(timer)), []);

  const handleUpdate = (rowId: string, field: keyof typeof EMPTY_ROW, value: string) => {
    setRows((current) => current.map((row) => (row.row_id === rowId ? { ...row, [field]: value } : row)));
    const existingTimer = debounceTimers.current.get(rowId);
    if (existingTimer) clearTimeout(existingTimer);
    debounceTimers.current.set(rowId, setTimeout(async () => {
      debounceTimers.current.delete(rowId);
      try {
        await roomRackApi.update(rowId, { [field]: value });
      } catch (e) {
        setToast({ type: 'error', message: e instanceof Error ? e.message : '更新失败' });
        load();
      }
    }, 500));
  };

  const handleAdd = async (sourceRowId: string) => {
    try {
      const row = await roomRackApi.createAfter(sourceRowId, EMPTY_ROW);
      setRows((current) => {
        const index = current.findIndex((item) => item.row_id === sourceRowId);
        if (index < 0) return [...current, row];
        return [...current.slice(0, index + 1), row, ...current.slice(index + 1)];
      });
    } catch (e) {
      setToast({ type: 'error', message: e instanceof Error ? e.message : '新增失败' });
    }
  };

  const handleDelete = async (rowId: string) => {
    const previous = rows;
    setRows((current) => current.filter((row) => row.row_id !== rowId));
    try {
      await roomRackApi.delete(rowId);
    } catch (e) {
      setRows(previous);
      setToast({ type: 'error', message: e instanceof Error ? e.message : '删除失败' });
    }
  };

  const handleExport = async () => {
    if (exporting || rows.length === 0) return;
    setExporting(true);
    try {
      const data = await roomRackApi.export(rows);
      setToast({ type: 'success', message: `已保存到 ${data.saved_path}` });
    } catch (e) {
      setToast({ type: 'error', message: e instanceof Error ? e.message : '导出失败' });
    } finally {
      setExporting(false);
    }
  };

  return (
    <ProposalChapterCard id="panel-rooms" title="7. 机房信息">
      {toast && (
        <div className={`mb-3 rounded border px-3 py-2 text-sm ${
          toast.type === 'error' ? 'border-red-200 bg-red-50 text-red-700' : 'border-green-200 bg-green-50 text-green-700'
        }`}>
          {toast.message}
        </div>
      )}
      <div className="overflow-x-auto rounded-md border border-slate-100">
        <table className="w-full min-w-[1080px] border-collapse text-sm">
          <thead>
            <tr className={HEAD_TR_CLS}>
              <th className="w-8 px-1"></th>
              {COLS.map((column) => <th key={column.key} className={TH_CLS}>{column.label}</th>)}
              <th className="w-8 px-1"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.row_id} className="border-t border-slate-100 align-middle">
                <td className="w-8 px-1 text-center">
                  <button
                    type="button"
                    title="在当前行下方新增"
                    onClick={() => handleAdd(row.row_id)}
                    className="grid h-5 w-5 place-items-center rounded text-xs text-slate-400 transition-colors hover:bg-blue-50 hover:text-blue-600"
                  >＋</button>
                </td>
                {COLS.map((column) => (
                  <td key={column.key} className="px-2 py-1.5">
                    <input
                      value={String(row[column.key] ?? '')}
                      onChange={(event) => handleUpdate(row.row_id, column.key as keyof typeof EMPTY_ROW, event.target.value)}
                      className={INPUT_CLS}
                    />
                  </td>
                ))}
                <td className="w-8 px-1 text-center">
                  <button type="button" onClick={() => handleDelete(row.row_id)} title="删除此行" className={DEL_BTN_CLS}>✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && rows.length === 0 && (
          <div className="border-t border-slate-100 px-4 py-8 text-center text-sm text-slate-400">
            暂无机房信息，请确认设备信息表已解析或手动新增 PoD 行。
          </div>
        )}
      </div>
      <div className="mt-3 flex items-center justify-between">
        <div className="text-xs text-slate-500">{loading ? '加载中…' : `共 ${rows.length} 个 PoD`}</div>
        <button
          type="button"
          onClick={handleExport}
          disabled={loading || exporting || rows.length === 0}
          className={`rounded-md border px-3 py-1.5 text-xs font-normal transition-colors ${
            loading || exporting || rows.length === 0
              ? 'cursor-not-allowed border-slate-200 text-slate-300'
              : 'border-green-300 text-green-600 hover:border-green-400 hover:bg-green-50'
          }`}
        >
          {exporting ? '保存中…' : '导出 Excel'}
        </button>
      </div>
    </ProposalChapterCard>
  );
}
