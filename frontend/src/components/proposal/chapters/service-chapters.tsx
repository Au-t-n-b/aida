'use client';

import { Fragment, useState, type ReactNode } from 'react';
import {
  ProposalChapterCard,
  ProposalChapterHeader,
  ProposalDataTable,
  ProposalDataTableBody,
  ProposalDataTableHead,
} from '../primitives';
import { MAINT_STRATEGY, SERVICE_CONFIG } from '../proposal-data';

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

/* ── 8.1 服务交付界面（交付界面可选 华为/客户）── */
const DELIVERY_OPTIONS = ['华为', '客户'];

export function ServiceDeliveryChapter() {
  const [channels, setChannels] = useState<string[]>(
    () => SERVICE_CONFIG.map((s) => (s.channel === '客户' ? '客户' : '华为')),
  );
  const setChannel = (i: number, v: string) =>
    setChannels((cs) => cs.map((c, idx) => (idx === i ? v : c)));

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
              <td className="px-2 py-1">
                <select
                  value={channels[i] ?? '华为'}
                  onChange={(e) => setChannel(i, e.target.value)}
                  title="选择交付界面"
                  className="cursor-pointer rounded border border-transparent bg-transparent px-2 py-1 text-sm text-slate-700 transition-colors hover:border-slate-200 focus:border-blue-400 focus:bg-white focus:outline-none"
                >
                  {DELIVERY_OPTIONS.map((o) => (
                    <option key={o} value={o}>{o}</option>
                  ))}
                </select>
              </td>
            </tr>
          ))}
        </ProposalDataTableBody>
      </ProposalDataTable>
    </ProposalChapterCard>
  );
}

/* ── 8.2 服务配置（分组树，默认折叠）── */
interface ServiceGroup {
  id: number;
  name: string;
  qty: number;
  children: { name: string; qty: number }[];
}
const SERVICE_TREE: ServiceGroup[] = [
  {
    id: 1, name: '标准-固定网络集成服务(目录价)-中国(CE9860-4C-EI-A)', qty: 2,
    children: [
      { name: '中国区-网络-数据中心交换机框架式单板(新建)-硬件督导-/单板', qty: 4 },
      { name: '中国区-网络-数据中心交换机框架式单板(新建)-软件督导-/单板', qty: 4 },
      { name: '中国区-网络-数据中心交换机部署(新建)-硬件督导-/单板', qty: 4 },
      { name: '中国区-网络-数据中心交换机部署(新建)-软件督导-/单板', qty: 4 },
      { name: 'RUI平台部署验证(新建)-项目经理', qty: 2 },
      { name: 'RUI平台部署验证(新建)-技术经理', qty: 2 },
    ],
  },
  {
    id: 2, name: '购买+部署的(Catalogue CHN)', qty: 8,
    children: [
      { name: '中国区-<IP网络>-台架安装-物理安装', qty: 16 },
      { name: '中国区-网络-台架安装-标签制作-A级', qty: 2 },
      { name: '中国区-<IP网络>台架安装(新建)-标签制作-A级', qty: 16 },
      { name: '中国区-网络-光纤熔接-C级', qty: 2 },
      { name: '中国区-<IP网络>光纤熔接(新建)-光纤熔接-C级', qty: 16 },
      { name: '中国区-<IP网络>工程督导(新建)-项目经理', qty: 16 },
      { name: '中国区-<IP网络>工程督导(新建)-技术经理', qty: 16 },
      { name: '中国区-<IP网络>工程督导(新建)-文档督导', qty: 16 },
    ],
  },
  {
    id: 3, name: '安装服务-部署服务(目录价)-中国(OceanStor Pacific 9540)', qty: 3,
    children: [
      { name: '中国区-存储-光口台架安装部署a(新建)-硬件督导-/单板', qty: 3 },
      { name: '中国区-存储-台架安装部署a(新建)-软件督导-/单板', qty: 3 },
    ],
  },
];

export function ServiceContentChapter() {
  const [open, setOpen] = useState<Set<number>>(() => new Set());
  const toggle = (id: number) =>
    setOpen((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  return (
    <ProposalChapterCard id="sec-7-2" title="8.2 服务配置">
      <div className="overflow-hidden rounded-md border border-slate-100">
        <table className="w-full border-collapse text-sm">
          <colgroup>
            <col />
            <col style={{ width: 90 }} />
          </colgroup>
          <thead>
            <tr className="bg-slate-50/90 text-left text-sm text-slate-700">
              <th className="px-3 py-2.5 font-semibold">服务内容</th>
              <th className="px-3 py-2.5 font-semibold">数量</th>
            </tr>
          </thead>
          <tbody>
            {SERVICE_TREE.map((g) => (
              <Fragment key={g.id}>
                <tr
                  className="cursor-pointer border-t border-slate-100 bg-slate-50/40 hover:bg-slate-100/60"
                  onClick={() => toggle(g.id)}
                >
                  <td className="px-3 py-2.5 font-medium text-slate-700">
                    <span
                      className="mr-1.5 inline-block text-slate-400"
                      style={{ transform: open.has(g.id) ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform .15s' }}
                    >
                      ▼
                    </span>
                    {g.name}
                  </td>
                  <td className="px-3 py-2.5">{g.qty}</td>
                </tr>
                {open.has(g.id) &&
                  g.children.map((ch, ci) => (
                    <tr key={ci} className="border-t border-slate-100">
                      <td className="py-2 pl-9 pr-3 text-slate-600">{ch.name}</td>
                      <td className="px-3 py-2">{ch.qty}</td>
                    </tr>
                  ))}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </ProposalChapterCard>
  );
}

/* ── 8.3 维保策略（去掉「维保类型」列，列名对齐图五）── */
export function MaintStrategyChapter() {
  return (
    <ProposalChapterCard id="sec-7-3" title="8.3 维保策略">
      <ProposalDataTable equalCols leftAlign className="proposal-table-ellipsis">
        <ProposalDataTableHead>
          <tr>
            <th>产品型号</th>
            <th>保修策略</th>
            <th>维保策略</th>
            <th>开始时间</th>
            <th>结束时间</th>
            <th>EOS时间</th>
            <th>是否超EOS服务</th>
            <th>超EOS审批结论</th>
          </tr>
        </ProposalDataTableHead>
        <ProposalDataTableBody>
          {MAINT_STRATEGY.map((m, i) => (
            <tr key={i}>
              <EllipsisCell value={m.model} />
              <EllipsisCell value={m.warranty} />
              <EllipsisCell value={`金牌服务，${m.maint}`} />
              <EllipsisCell value={m.start} />
              <EllipsisCell value={m.end} />
              <EllipsisCell value={m.eos} />
              <EllipsisCell value={m.overEos} />
              <EllipsisCell value={m.approval === '—' ? '' : m.approval} />
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

interface SlaGroup {
  content: string;
  rows: { level: string; period: string; response: string }[];
}
const SLA_GROUPS: SlaGroup[] = [
  {
    content: '远程问题处理（单域）',
    rows: [
      { level: '紧急问题', period: '7×24', response: '1 小时' },
      { level: '重要问题', period: '5×8', response: '2 小时' },
      { level: '一般问题', period: '5×8', response: '4 小时' },
      { level: '技术咨询', period: '5×8', response: '8 小时' },
    ],
  },
  {
    content: '现场问题处理',
    rows: [
      { level: '紧急问题', period: '7×10', response: 'NBD 人员到达' },
      { level: '重要问题', period: '5×8', response: 'NBD 人员到达' },
      { level: '一般问题', period: '5×8', response: 'NBD 人员到达' },
    ],
  },
  {
    content: '备件先行',
    rows: [
      { level: '紧急问题', period: '7×10', response: 'NBD 备件送达' },
      { level: '重要问题', period: '5×8', response: 'NBD 备件送达' },
      { level: '一般问题', period: '5×8', response: 'NBD 备件送达' },
    ],
  },
  {
    content: '现场硬件更换',
    rows: [
      { level: '紧急问题', period: '7×10', response: 'NBD 完成更换' },
      { level: '重要问题', period: '5×8', response: 'NBD 完成更换' },
      { level: '一般问题', period: '5×8', response: 'NBD 完成更换' },
    ],
  },
];

export function SlaChapter() {
  return (
    <ProposalChapterCard id="sec-7-4" title="8.4 维保SLA">
      <ProposalDataTable leftAlign equalCols className="min-w-[960px] proposal-table-aligned">
        <ProposalDataTableHead>
          <tr>
            <th>服务内容</th>
            <th>问题级别</th>
            <th>服务时段</th>
            <th>响应时间</th>
            <th>恢复时间</th>
            <th>解决时间</th>
          </tr>
        </ProposalDataTableHead>
        <ProposalDataTableBody>
          {SLA_GROUPS.flatMap((g) =>
            g.rows.map((r, ri) => (
              <tr key={`${g.content}-${ri}`}>
                {ri === 0 && (
                  <td
                    rowSpan={g.rows.length}
                    className="whitespace-nowrap align-middle font-medium text-slate-700"
                  >
                    {g.content}
                  </td>
                )}
                <td>{r.level}</td>
                <td>{r.period}</td>
                <td>{r.response}</td>
                <td>NA</td>
                <td>NA</td>
              </tr>
            )),
          )}
        </ProposalDataTableBody>
      </ProposalDataTable>
    </ProposalChapterCard>
  );
}
