'use client';

import { useMemo, useRef, useState } from 'react';
import { ProposalChapterCard, ProposalDataTable, ProposalDataTableBody, ProposalDataTableHead } from '../primitives';
import { TEST_CASE_DETAIL_TEMPLATE, TEST_CASE_GROUPS } from '../proposal-data';

type FlatCase = { id: string; type: string; name: string };

function buildFlatCases(): FlatCase[] {
  const out: FlatCase[] = [];
  let seq = 1;
  for (const g of TEST_CASE_GROUPS) {
    for (const name of g.cases) {
      out.push({ id: `DEVM-${String(seq).padStart(4, '0')}`, type: g.type, name });
      seq += 1;
    }
  }
  return out;
}

function CaseDetail({ c }: { c: FlatCase }) {
  const d = TEST_CASE_DETAIL_TEMPLATE;
  return (
    <div className="testcase-detail" id="panel-testcase-detail">
      <table className="testcase-detail-table">
        <tbody>
          <tr>
            <th>测试编号</th>
            <td colSpan={3} className="font-mono">{c.id}</td>
          </tr>
          <tr>
            <th>测试目的</th>
            <td colSpan={3}>{c.name}：{d.purpose}</td>
          </tr>
          <tr>
            <th>测试配置及连接关系（图示）</th>
            <td colSpan={3}>
              <div className="testcase-topo">
                <span className="testcase-topo-node">{d.topology.left}</span>
                <span className="testcase-topo-link">
                  <span className="testcase-topo-port">{d.topology.leftPort}</span>
                  <span className="testcase-topo-line" />
                  <span className="testcase-topo-port">{d.topology.rightPort}</span>
                </span>
                <span className="testcase-topo-node">{d.topology.right}</span>
              </div>
            </td>
          </tr>
          <tr>
            <th>测试步骤</th>
            <td colSpan={3}>
              <ol className="testcase-list">
                {d.steps.map((s, i) => <li key={i}>{s}</li>)}
              </ol>
            </td>
          </tr>
          <tr>
            <th>预期结果</th>
            <td colSpan={3}>
              <ol className="testcase-list">
                {d.expects.map((s, i) => <li key={i}>{s}</li>)}
              </ol>
            </td>
          </tr>
          <tr>
            <th>备注</th>
            <td colSpan={3}>{d.remark}</td>
          </tr>
          <tr>
            <th>测试结果</th>
            <td colSpan={3}>{d.result}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export function TestCaseChapter() {
  const flat = useMemo(buildFlatCases, []);
  const byId = useMemo(() => new Map(flat.map((c) => [`${c.type}__${c.name}`, c])), [flat]);
  const [selected, setSelected] = useState<FlatCase | null>(null);
  const detailRef = useRef<HTMLDivElement>(null);

  const rowSpans = TEST_CASE_GROUPS.flatMap((g) =>
    g.cases.map((_, i) => (i === 0 ? g.cases.length : 0)),
  );

  const openCase = (type: string, name: string) => {
    const c = byId.get(`${type}__${name}`) ?? null;
    setSelected(c);
    setTimeout(() => {
      detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 60);
  };

  let flatIdx = -1;

  return (
    <ProposalChapterCard id="panel-testcase" title="12. 测试用例">
      <ProposalDataTable leftAlign>
        <colgroup>
          <col style={{ width: '32%' }} />
          <col style={{ width: '68%' }} />
        </colgroup>
        <ProposalDataTableHead>
          <tr>
            <th>测试类型</th>
            <th>用例名称</th>
          </tr>
        </ProposalDataTableHead>
        <ProposalDataTableBody>
          {TEST_CASE_GROUPS.map((g) =>
            g.cases.map((name, i) => {
              flatIdx += 1;
              const span = rowSpans[flatIdx] ?? 0;
              const isActive = selected?.type === g.type && selected?.name === name;
              return (
                <tr key={`${g.type}-${name}`}>
                  {span > 0 && (
                    <td rowSpan={span} className="align-middle text-xs font-semibold text-slate-900">
                      {g.type}
                    </td>
                  )}
                  <td>
                    <button
                      type="button"
                      className={`testcase-link${isActive ? ' is-active' : ''}`}
                      onClick={() => openCase(g.type, name)}
                    >
                      {name}
                    </button>
                  </td>
                </tr>
              );
            }),
          )}
        </ProposalDataTableBody>
      </ProposalDataTable>

      <div ref={detailRef}>
        {selected ? (
          <div className="mt-5">
            <div className="mb-2 flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-900">用例详情</span>
              <span className="text-xs text-slate-400">{selected.id} · {selected.name}</span>
              <button
                type="button"
                className="ml-auto text-xs text-slate-400 transition-colors hover:text-slate-700"
                onClick={() => setSelected(null)}
              >
                收起
              </button>
            </div>
            <CaseDetail c={selected} />
          </div>
        ) : (
          <p className="mt-4 text-xs text-slate-400">点击任一用例名称，查看测试编号、步骤与预期结果详情。</p>
        )}
      </div>
    </ProposalChapterCard>
  );
}
