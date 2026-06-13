'use client';

import { useEffect, useMemo } from 'react';
import {
  ProposalChapterCard,
  ProposalDataTable,
  ProposalDataTableBody,
  ProposalDataTableHead,
} from '../primitives';
import { PRE_INTEGRATION } from '../proposal-data';

interface IntegrationChapterProps {
  initialRows?: unknown;
  onRowsChange?: (rows: Array<Record<string, unknown>>) => void;
}

function _normalizeRows(input: unknown) {
  if (!Array.isArray(input) || input.length === 0) {
    return PRE_INTEGRATION.map((row) => ({ ...row }));
  }
  const rows = input
    .filter((row) => typeof row === 'object' && row !== null)
    .map((row) => {
      const item = row as Record<string, unknown>;
      return {
        cat: String(item.cat ?? ''),
        desc: String(item.desc ?? ''),
        hw: String(item.hw ?? ''),
        sw: String(item.sw ?? ''),
        owner: String(item.owner ?? ''),
        state: String(item.state ?? ''),
        date: String(item.date ?? ''),
      };
    });
  return rows.length ? rows : PRE_INTEGRATION.map((row) => ({ ...row }));
}

export function IntegrationChapter({ initialRows, onRowsChange }: IntegrationChapterProps) {
  const rows = useMemo(() => _normalizeRows(initialRows), [initialRows]);

  useEffect(() => {
    onRowsChange?.(rows.map((row) => ({ ...row })));
  }, [onRowsChange, rows]);

  return (
    <ProposalChapterCard id="panel-pre" title="6. 集成验证需求信息">
      <ProposalDataTable equalCols leftAlign>
        <ProposalDataTableHead>
          <tr>
            <th>分类</th>
            <th>预集成验证需求</th>
            <th>硬件需求</th>
            <th>软件需求</th>
            <th>责任人</th>
            <th>完成状态</th>
            <th>完成时间</th>
          </tr>
        </ProposalDataTableHead>
        <ProposalDataTableBody>
          {rows.map((p, i) => (
            <tr key={i}>
              <td>{p.cat}</td>
              <td><div className="proposal-clamp-2" title={p.desc}>{p.desc}</div></td>
              <td className="text-xs">{p.hw}</td>
              <td className="text-xs">{p.sw}</td>
              <td>{p.owner}</td>
              <td>{p.state}</td>
              <td>{p.date}</td>
            </tr>
          ))}
        </ProposalDataTableBody>
      </ProposalDataTable>
    </ProposalChapterCard>
  );
}
