'use client';

import {
  ProposalChapterCard,
  ProposalDataTable,
  ProposalDataTableBody,
} from '../primitives';
import { PROJECT_BACKGROUND } from '../proposal-data';

const BACKGROUND_ROWS = (b: typeof PROJECT_BACKGROUND) => [
  { label: '客户项目背景', value: b.background },
  { label: '客户项目目标', value: b.goal },
  { label: '客户项目范围', value: b.scope },
  { label: '客户项目计划', value: b.planSummary },
];

export function CustomerProjectChapter() {
  const b = PROJECT_BACKGROUND;
  return (
    <ProposalChapterCard id="sec-1-1" title="1. 项目背景">
      <ProposalDataTable leftAlign>
        <ProposalDataTableBody>
          {BACKGROUND_ROWS(b).map((row) => (
            <tr key={row.label}>
              <td className="w-36 bg-slate-50/90 text-xs font-semibold uppercase tracking-wide text-slate-600">
                {row.label}
              </td>
              <td className="text-sm text-slate-700">{row.value}</td>
            </tr>
          ))}
        </ProposalDataTableBody>
      </ProposalDataTable>
    </ProposalChapterCard>
  );
}

export function CustomerChapterWrapper() {
  return <CustomerProjectChapter />;
}
