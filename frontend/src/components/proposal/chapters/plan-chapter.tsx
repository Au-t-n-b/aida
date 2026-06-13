'use client';

import { useEffect, useState } from 'react';
import {
  ProposalChapterCard,
  ProposalDataTable,
  ProposalDataTableBody,
  ProposalDataTableHead,
} from '../primitives';
import { PLAN_ACTIVITIES } from '../proposal-data';

interface PlanChapterProps {
  initialRows?: unknown;
  onRowsChange?: (rows: Array<Record<string, unknown>>) => void;
}

function PlanProgress({ value, tone }: { value: number; tone: 'blue' | 'green' }) {
  return (
    <span className="plan-progress-cell">
      <span className={`plan-progress-dot tone-${tone}`} />
      {value}%
    </span>
  );
}

function _defaultRows() {
  return PLAN_ACTIVITIES.map((row) => ({ ...row }));
}

function _normalizeRows(input: unknown) {
  if (!Array.isArray(input) || input.length === 0) {
    return _defaultRows();
  }
  const rows = input
    .filter((row) => typeof row === 'object' && row !== null)
    .map((row) => {
      const item = row as Record<string, unknown>;
      return {
        name: String(item.name ?? ''),
        start: String(item.start ?? ''),
        end: String(item.end ?? ''),
        actualStart: String(item.actualStart ?? ''),
        actualEnd: String(item.actualEnd ?? ''),
        owner: String(item.owner ?? ''),
        unit: String(item.unit ?? ''),
        status: String(item.status ?? ''),
        progress: Number(item.progress ?? 0) || 0,
        progressTone: (item.progressTone === 'green' ? 'green' : 'blue') as 'blue' | 'green',
      };
    });
  return rows.length ? rows : _defaultRows();
}

export function PlanChapter({ initialRows, onRowsChange }: PlanChapterProps) {
  const [rows, setRows] = useState(() => _normalizeRows(initialRows));

  useEffect(() => {
    setRows(_normalizeRows(initialRows));
  }, [initialRows]);

  useEffect(() => {
    onRowsChange?.(rows.map((row) => ({ ...row })));
  }, [onRowsChange, rows]);

  return (
    <ProposalChapterCard id="panel-plan" title="10. 计划">
      <ProposalDataTable equalCols leftAlign>
        <ProposalDataTableHead>
          <tr>
            <th>活动名称</th>
            <th>开始日期</th>
            <th>结束日期</th>
            <th>实际开始日期</th>
            <th>实际结束日期</th>
            <th>责任人</th>
            <th>管理单元</th>
            <th>任务状态</th>
            <th>进度</th>
          </tr>
        </ProposalDataTableHead>
        <ProposalDataTableBody>
          {rows.map((row, i) => (
            <tr key={i}>
              <td>{row.name}</td>
              <td>{row.start}</td>
              <td>{row.end}</td>
              <td>{row.actualStart}</td>
              <td>{row.actualEnd}</td>
              <td>{row.owner}</td>
              <td>{row.unit}</td>
              <td>{row.status}</td>
              <td>
                <PlanProgress value={row.progress} tone={row.progressTone} />
              </td>
            </tr>
          ))}
        </ProposalDataTableBody>
      </ProposalDataTable>
    </ProposalChapterCard>
  );
}
