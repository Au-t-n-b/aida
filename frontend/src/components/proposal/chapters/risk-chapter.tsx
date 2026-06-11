'use client';

import {
  ProposalChapterCard,
  ProposalChapterHeader,
  ProposalDataTable,
  ProposalDataTableBody,
  ProposalDataTableHead,
} from '../primitives';
import { PROPOSAL_ASSUMPTIONS, PROPOSAL_RISKS } from '../proposal-data';

export function RiskListChapter() {
  return (
    <ProposalChapterCard
      id="sec-9-1"
      title="13.1 风险列表"
      headerExtra={
        <button type="button" className="btn sm ghost">
          + 手工补录风险
        </button>
      }
    >
      <ProposalDataTable wrapClassName="mb-0" leftAlign>
        <ProposalDataTableHead>
          <tr>
            <th>编号</th>
            <th>风险点</th>
            <th>描述</th>
            <th>影响</th>
            <th>类型</th>
            <th>等级</th>
            <th>来源</th>
            <th>识别时间</th>
            <th>关闭时间</th>
            <th>操作</th>
          </tr>
        </ProposalDataTableHead>
        <ProposalDataTableBody>
          {PROPOSAL_RISKS.map((r, i) => (
            <tr key={i}>
              <td className="font-mono text-xs">{r.id}</td>
              <td>{r.riskPoint}</td>
              <td className="text-xs">{r.desc}</td>
              <td className="text-xs">{r.impact}</td>
              <td>{r.type}</td>
              <td>{r.level}</td>
              <td className="text-xs">{r.source}</td>
              <td className="text-xs">{r.identifiedAt}</td>
              <td className="text-xs">{r.closedAt || '—'}</td>
              <td>
                <button type="button" className="btn-link text-xs">
                  编辑
                </button>
              </td>
            </tr>
          ))}
        </ProposalDataTableBody>
      </ProposalDataTable>
    </ProposalChapterCard>
  );
}

export function AssumptionChapter() {
  return (
    <ProposalChapterCard id="sec-9-2" title="13.2 假设">
      <ProposalDataTable leftAlign>
        <ProposalDataTableHead>
          <tr>
            <th>序号</th>
            <th>假设项内容</th>
            <th>来源</th>
            <th>责任人</th>
            <th>闭环时间</th>
            <th>超期状态</th>
          </tr>
        </ProposalDataTableHead>
        <ProposalDataTableBody>
          {PROPOSAL_ASSUMPTIONS.map((a) => {
            const isClosed = a.closed === '已闭环';
            return (
              <tr key={a.seq}>
                <td>{a.seq}</td>
                <td>{a.item}</td>
                <td>{a.source}</td>
                <td>{a.owner}</td>
                <td className="text-xs">{a.closed}</td>
                <td>
                  <span className={`status-pill ${isClosed ? 'green' : 'amber'}`}>
                    {isClosed ? '已闭环' : '待跟进'}
                  </span>
                </td>
              </tr>
            );
          })}
        </ProposalDataTableBody>
      </ProposalDataTable>
    </ProposalChapterCard>
  );
}

export function RiskChapterWrapper() {
  return (
    <section id="sec-9">
      <ProposalChapterHeader title="13. 风险&假设信息" />
      <RiskListChapter />
      <AssumptionChapter />
    </section>
  );
}
