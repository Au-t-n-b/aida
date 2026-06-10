'use client';

import type { ReactNode } from 'react';
import {
  ProposalChapterCard,
  ProposalChapterHeader,
  ProposalDataTable,
  ProposalDataTableBody,
  ProposalDataTableHead,
} from '../primitives';
import {
  MAINT_STRATEGY,
  SERVICE_CONFIG,
  SERVICE_CONTENT,
  SLA_REQUIREMENTS,
} from '../proposal-data';

function EllipsisCell({ value, title }: { value: ReactNode; title?: string }) {
  const hoverTitle =
    title ??
    (typeof value === 'string' || typeof value === 'number' ? String(value) : undefined);
  return (
    <td className="proposal-cell-ellipsis" title={hoverTitle}>
      {value}
    </td>
  );
}

export function ServiceDeliveryChapter() {
  return (
    <ProposalChapterCard id="sec-7-1" title="8.1 服务交付界面">
      <ProposalDataTable leftAlign>
        <ProposalDataTableHead>
          <tr>
            <th>服务大类</th>
            <th>服务细项</th>
            <th>交付界面</th>
          </tr>
        </ProposalDataTableHead>
        <ProposalDataTableBody>
          {SERVICE_CONFIG.map((s, i) => (
            <tr key={i}>
              <td>{s.major}</td>
              <td>{s.item}</td>
              <td>{s.channel}</td>
            </tr>
          ))}
        </ProposalDataTableBody>
      </ProposalDataTable>
    </ProposalChapterCard>
  );
}

export function ServiceContentChapter() {
  return (
    <ProposalChapterCard id="sec-7-2" title="8.2 服务配置">
      <ProposalDataTable leftAlign>
        <ProposalDataTableHead>
          <tr>
            <th>服务名称</th>
            <th>服务内容</th>
            <th>数量</th>
            <th>单位</th>
          </tr>
        </ProposalDataTableHead>
        <ProposalDataTableBody>
          {SERVICE_CONTENT.map((s, i) => (
            <tr key={i}>
              <td>{s.name}</td>
              <td className="text-xs">{s.content}</td>
              <td>{s.qty}</td>
              <td>{s.unit}</td>
            </tr>
          ))}
        </ProposalDataTableBody>
      </ProposalDataTable>
    </ProposalChapterCard>
  );
}

export function MaintStrategyChapter() {
  return (
    <ProposalChapterCard id="sec-7-3" title="8.3 维保策略">
      <ProposalDataTable equalCols leftAlign className="proposal-table-ellipsis">
        <ProposalDataTableHead>
          <tr>
            <th>产品型号</th>
            <th>保修策略</th>
            <th>维保策略</th>
            <th>维保类型</th>
            <th>开始时间</th>
            <th>结束时间</th>
            <th>EOS</th>
            <th>超 EOS</th>
            <th>超 EOS 审批</th>
          </tr>
        </ProposalDataTableHead>
        <ProposalDataTableBody>
          {MAINT_STRATEGY.map((m, i) => (
            <tr key={i}>
              <EllipsisCell value={m.model} />
              <EllipsisCell value={m.warranty} />
              <EllipsisCell value={m.maint} />
              <EllipsisCell
                value={<span className="status-pill blue">{m.maintType}</span>}
                title={m.maintType}
              />
              <EllipsisCell value={m.start} />
              <EllipsisCell value={m.end} />
              <EllipsisCell value={m.eos} />
              <EllipsisCell value={m.overEos} />
              <EllipsisCell value={m.approval} />
            </tr>
          ))}
        </ProposalDataTableBody>
      </ProposalDataTable>
    </ProposalChapterCard>
  );
}

export function ServiceChapterWrapper() {
  return (
    <section id="sec-7">
      <ProposalChapterHeader title="8. 服务&维保信息" />
      <ServiceDeliveryChapter />
      <ServiceContentChapter />
      <MaintStrategyChapter />
      <SlaChapter />
    </section>
  );
}

export function SlaChapter() {
  return (
    <ProposalChapterCard id="sec-7-4" title="8.4 维保SLA">
      <ProposalDataTable>
        <ProposalDataTableHead>
          <tr>
            <th>问题级别</th>
            <th>定义</th>
            <th>覆盖时段</th>
            <th>响应时间</th>
            <th>恢复时间</th>
            <th>解决时间</th>
          </tr>
        </ProposalDataTableHead>
        <ProposalDataTableBody>
          {SLA_REQUIREMENTS.map((s, i) => (
            <tr key={i}>
              <td>
                <span
                  className={`status-pill ${i === 0 ? 'red' : i === 1 ? 'amber' : i === 2 ? 'blue' : 'gray'}`}
                >
                  {s.level}
                </span>
              </td>
              <td className="text-xs">{s.def}</td>
              <td>{s.coverage}</td>
              <td className="font-mono text-xs">{s.response}</td>
              <td className="font-mono text-xs">{s.restore}</td>
              <td className="font-mono text-xs">{s.resolve}</td>
            </tr>
          ))}
        </ProposalDataTableBody>
      </ProposalDataTable>
    </ProposalChapterCard>
  );
}
