'use client';

import {
  ProposalChapterCard,
  ProposalDataTable,
  ProposalDataTableBody,
  ProposalDataTableHead,
} from '../primitives';
import { useProposalData } from '@/hooks/useProposalData';

function PlanProgress({ value, tone }: { value: number; tone: 'blue' | 'green' }) {
  return (
    <span className="plan-progress-cell">
      <span className={`plan-progress-dot tone-${tone}`} />
      {value}%
    </span>
  );
}

export function PlanChapter() {
  const { planRows, loading } = useProposalData();

  return (
    <ProposalChapterCard id="panel-plan" title="10. 计划">
      {loading && <p className="mb-2 text-xs text-slate-400">正在加载计划…</p>}
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
          {planRows.map((row, i) => (
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
