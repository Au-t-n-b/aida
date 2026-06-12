'use client';

import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { ProposalChapterCard } from '../primitives';
import { useProposalData, tcKey } from '@/hooks/useProposalData';
import type { AcceptanceTestCase } from '@/types/domain';

type KeyedCase = AcceptanceTestCase & { key: string };
const CB = 'h-4 w-4 shrink-0 cursor-pointer accent-blue-600';

/* ── 右侧详情：字段块 + 编号步骤 ── */
function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">{label}</div>
      <div className="text-[13px] leading-relaxed text-slate-700">{children}</div>
    </div>
  );
}

function StepList({ items, tone }: { items: string[]; tone: 'blue' | 'green' }) {
  if (!items.length) return <span className="text-slate-400">—</span>;
  const dot = tone === 'blue' ? 'bg-blue-100 text-blue-600' : 'bg-emerald-100 text-emerald-600';
  return (
    <ol className="space-y-1.5">
      {items.map((s, i) => (
        <li key={i} className="flex gap-2.5">
          <span className={`mt-0.5 flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full text-[10px] font-semibold ${dot}`}>
            {i + 1}
          </span>
          <span>{s}</span>
        </li>
      ))}
    </ol>
  );
}

function CaseDetail({ c, selected, onToggle }: { c: KeyedCase; selected: boolean; onToggle: () => void }) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200/80 bg-white shadow-sm">
      <div className="flex items-center gap-3 border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white px-5 py-4">
        <div className="min-w-0 flex-1 text-base font-semibold text-slate-900">{c.l3}</div>
        <label className="flex shrink-0 cursor-pointer items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-blue-300">
          <input type="checkbox" checked={selected} onChange={onToggle} className={CB} />
          纳入验收
        </label>
      </div>
      <div className="space-y-5 px-5 py-5">
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="用例编号">
            <span className="rounded bg-blue-50 px-2 py-0.5 font-mono text-[13px] font-medium text-blue-600">{c.id}</span>
          </Field>
          <Field label="测试目的">{c.purpose || '—'}</Field>
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="测试组网">{c.topology || '—'}</Field>
          <Field label="测试结果">{c.result || '—'}</Field>
        </div>
        <Field label="预置条件">{c.pre || '—'}</Field>
        <div className="grid gap-5 lg:grid-cols-2">
          <Field label="测试步骤"><StepList items={c.steps} tone="blue" /></Field>
          <Field label="预期结果"><StepList items={c.expects} tone="green" /></Field>
        </div>
        {c.remark && <Field label="备注">{c.remark}</Field>}
      </div>
    </div>
  );
}

export function TestCaseChapter() {
  const { testCases, selectedTcKeys, setSelectedTc, loading, cardScale } = useProposalData();

  const cases = useMemo<KeyedCase[]>(
    () => testCases.map((c, i) => ({ ...c, key: tcKey(c, i) })),
    [testCases],
  );

  const selected = selectedTcKeys;

  const groups = useMemo(() => {
    const m = new Map<string, Map<string, KeyedCase[]>>();
    for (const c of cases) {
      if (!m.has(c.l1)) m.set(c.l1, new Map());
      const l2m = m.get(c.l1)!;
      if (!l2m.has(c.l2)) l2m.set(c.l2, []);
      l2m.get(c.l2)!.push(c);
    }
    return [...m.entries()].map(([l1, l2m]) => ({
      l1,
      keys: [...l2m.values()].flat().map((c) => c.key),
      l2s: [...l2m.entries()].map(([l2, list]) => ({ l2, cases: list })),
    }));
  }, [cases]);

  const [openL1, setOpenL1] = useState<Set<string>>(() => new Set());
  // 默认：一级展开、二级全部折叠（三级隐藏）——用户单击二级三角再展开其用例
  const [openL2, setOpenL2] = useState<Set<string>>(() => new Set());
  const [active, setActive] = useState<string>('');
  const [query, setQuery] = useState('');

  useEffect(() => {
    if (cases.length && !active) setActive(cases[0]?.key ?? '');
    setOpenL1((s) => {
      if (s.size > 0) return s;
      return new Set(groups.map((g) => g.l1));
    });
  }, [cases, groups, active]);

  const q = query.trim();
  const hit = (c: KeyedCase) => !q || c.id.includes(q) || c.l3.includes(q) || c.purpose.includes(q);

  const toggleSel = (k: string) => {
    const n = new Set(selected);
    if (n.has(k)) n.delete(k); else n.add(k);
    setSelectedTc(n);
  };
  const setMany = (keys: string[], on: boolean) => {
    const n = new Set(selected);
    keys.forEach((k) => (on ? n.add(k) : n.delete(k)));
    setSelectedTc(n);
  };
  const toggleL1 = (l1: string) =>
    setOpenL1((s) => { const n = new Set(s); if (n.has(l1)) n.delete(l1); else n.add(l1); return n; });
  const toggleL2 = (key: string) =>
    setOpenL2((s) => { const n = new Set(s); if (n.has(key)) n.delete(key); else n.add(key); return n; });

  const activeCase = cases.find((c) => c.key === active) ?? null;

  if (!loading && cases.length === 0) {
    return (
      <ProposalChapterCard id="panel-testcase" title="12. 测试用例">
        <div className="flex h-32 items-center justify-center rounded-xl border border-dashed border-slate-200 text-sm text-slate-400">
          暂无测试用例（解析失败或未上传测试用例文件）
        </div>
      </ProposalChapterCard>
    );
  }

  return (
    <ProposalChapterCard id="panel-testcase" title="12. 测试用例">
      {loading && <p className="mb-2 text-xs text-slate-400">正在加载测试用例…</p>}
      {!loading && cardScale > 0 && (
        <p className="mb-2 text-xs text-slate-400">
          已按项目卡规模 {cardScale} 卡筛选集合通信 / 训练性能类用例
        </p>
      )}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        {/* 左：用例树 */}
        <div className="lg:w-[340px] lg:shrink-0">
          <div className="relative mb-2">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">⌕</span>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索用例编号 / 名称…"
              className="w-full rounded-lg border border-slate-200 py-1.5 pl-8 pr-3 text-sm text-slate-700 transition-colors placeholder:text-slate-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
            />
          </div>
          <div className="max-h-[520px] overflow-y-auto rounded-lg border border-slate-200/80 bg-white">
            {groups.map((g) => {
              const visKeys = g.l2s.flatMap((s) => s.cases).filter(hit).map((c) => c.key);
              if (q && visKeys.length === 0) return null;
              const gSel = g.keys.filter((k) => selected.has(k)).length;
              const allSel = gSel === g.keys.length;
              const open = openL1.has(g.l1) || !!q;
              return (
                <div key={g.l1} className="border-b border-slate-100 last:border-b-0">
                  <div className="flex items-center gap-2 bg-slate-50/80 px-2.5 py-2">
                    <input
                      type="checkbox"
                      checked={allSel}
                      ref={(el) => { if (el) el.indeterminate = gSel > 0 && !allSel; }}
                      onChange={(e) => setMany(g.keys, e.target.checked)}
                      className={CB}
                      title="全选 / 取消该子系统"
                    />
                    <button type="button" onClick={() => toggleL1(g.l1)} className="flex min-w-0 flex-1 items-center gap-1.5 text-left">
                      <span className="text-[10px] text-slate-400" style={{ transform: open ? 'rotate(0deg)' : 'rotate(-90deg)' }}>▼</span>
                      <span className="truncate text-[13px] font-semibold text-slate-700">{g.l1}</span>
                      <span className="text-[11px] text-slate-400">{g.keys.length}</span>
                    </button>
                  </div>
                  {open && g.l2s.map(({ l2, cases: list }) => {
                    const cs = list.filter(hit);
                    if (!cs.length) return null;
                    const l2Keys = list.map((c) => c.key);
                    const l2Sel = l2Keys.filter((k) => selected.has(k)).length;
                    const l2All = l2Sel === l2Keys.length;
                    const l2key = `${g.l1}::${l2}`;
                    const l2Open = openL2.has(l2key) || !!q;
                    return (
                      <div key={l2}>
                        <div className="flex items-center gap-2 px-2.5 py-1 pl-6">
                          <input
                            type="checkbox"
                            checked={l2All}
                            ref={(el) => { if (el) el.indeterminate = l2Sel > 0 && !l2All; }}
                            onChange={(e) => setMany(l2Keys, e.target.checked)}
                            className={CB}
                            title="全选 / 取消该类"
                          />
                          <button type="button" onClick={() => toggleL2(l2key)} className="flex min-w-0 flex-1 items-center gap-1.5 text-left">
                            <span className="text-[9px] text-slate-400" style={{ transform: l2Open ? 'rotate(0deg)' : 'rotate(-90deg)' }}>▼</span>
                            <span className="truncate text-[12.5px] font-medium text-slate-700">{l2}</span>
                            <span className="text-[11px] text-slate-300">{list.length}</span>
                          </button>
                        </div>
                        {l2Open && cs.map((c) => {
                          const isActive = c.key === active;
                          return (
                            <button
                              key={c.key}
                              type="button"
                              onClick={() => setActive(c.key)}
                              className={`flex w-full items-center gap-2 py-1.5 pl-7 pr-2 text-left transition-colors ${isActive ? 'bg-blue-50' : 'hover:bg-slate-50'}`}
                            >
                              <input
                                type="checkbox"
                                checked={selected.has(c.key)}
                                onChange={(e) => { e.stopPropagation(); toggleSel(c.key); }}
                                onClick={(e) => e.stopPropagation()}
                                className={CB}
                              />
                              <span className={`shrink-0 font-mono text-[11px] ${isActive ? 'font-semibold text-blue-600' : 'text-slate-400'}`}>{c.id}</span>
                              <span className={`truncate text-[12px] ${isActive ? 'font-medium text-blue-700' : 'text-slate-600'}`}>{c.l3}</span>
                            </button>
                          );
                        })}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>

        {/* 右：详情 */}
        <div className="min-w-0 flex-1">
          {activeCase ? (
            <CaseDetail c={activeCase} selected={selected.has(activeCase.key)} onToggle={() => toggleSel(activeCase.key)} />
          ) : (
            <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-slate-200 text-sm text-slate-400">
              从左侧选择一个用例查看详情
            </div>
          )}
        </div>
      </div>
    </ProposalChapterCard>
  );
}
