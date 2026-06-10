/* 评测中心 · 三 tab + 本次/总体双视图 */
import { useState, useEffect, useCallback } from 'react';
import {
  API_BASE,
  buildDeviations,
  buildToolDeviations,
  type EvalReport,
  type EvalViewMode,
  type ToolsReport,
} from './shared';
import { EVALS_REFRESH_EVENT } from '@/lib/eval-refresh';
import { MOCK_SKILL_REPORT, MOCK_TOOLS, MOCK_OBS } from './mock';
import SkillTab from './skill-tab';
import ToolsTab from './tools-tab';
import ObsTab from './obs-tab';
import { MetricCommonPanel, MetricGlossaryPanel } from './metric-glossary-panel';

type View = 'skill' | 'tools' | 'obs';

const TABS: { key: View; label: string; sub: string }[] = [
  { key: 'skill', label: 'SKILL 测评', sub: '质量 · 流程 · 产物' },
  { key: 'tools', label: '工具测评', sub: '自纠率 · 调用热度' },
  { key: 'obs', label: 'Langfuse 大盘', sub: '成本 · token · 模型' },
];

const MODE_TABS: { key: EvalViewMode; label: string }[] = [
  { key: 'latest', label: '本次执行' },
  { key: 'overview', label: '总体情况' },
];

function readParams(): { view: View; mode: EvalViewMode } {
  if (typeof window === 'undefined') return { view: 'skill', mode: 'overview' };
  const q = new URLSearchParams(window.location.search);
  const v = q.get('view');
  const view: View = v === 'tools' || v === 'obs' ? v : 'skill';
  const mode: EvalViewMode = q.get('mode') === 'latest' ? 'latest' : 'overview';
  return { view, mode };
}

function syncUrl(view: View, mode: EvalViewMode) {
  const q = new URLSearchParams();
  if (view !== 'skill') q.set('view', view);
  if (mode !== 'overview') q.set('mode', mode);
  const s = q.toString();
  const url = `${window.location.pathname}${s ? `?${s}` : ''}`;
  window.history.replaceState(null, '', url);
}

export default function EvalsScreen() {
  const [view, setView] = useState<View>('skill');
  const [mode, setMode] = useState<EvalViewMode>('overview');
  const [report, setReport] = useState<EvalReport>(MOCK_SKILL_REPORT);
  const [toolsReport, setToolsReport] = useState<ToolsReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    const { view: v, mode: m } = readParams();
    setView(v);
    setMode(m);
  }, []);

  const setViewMode = useCallback((v: View, m: EvalViewMode) => {
    setView(v);
    setMode(m);
    syncUrl(v, m);
  }, []);

  const flash = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2200);
  }, []);

  const fetchSkill = useCallback(async (m: EvalViewMode) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/agent/evals/report?skill=zhgk&limit=30&mode=${m}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: EvalReport = await res.json();
      if (data.total > 0 || data.run) {
        const runs = data.runs?.length ? data.runs : data.run ? [data.run] : [];
        setReport({ ...data, runs, source: 'live' });
      } else {
        setReport(MOCK_SKILL_REPORT);
      }
    } catch {
      setReport(MOCK_SKILL_REPORT);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchTools = useCallback(async (m: EvalViewMode) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/agent/evals/tools/report?mode=${m}&limit=30`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: ToolsReport = await res.json();
      const hasLive =
        (data.source && data.source !== 'empty' && data.source !== 'mock')
        || (data.records?.length ?? 0) > 0
        || (data.tools?.length ?? 0) > 0
        || (data.total ?? 0) > 0;
      if (hasLive) {
        setToolsReport({ ...data, source: data.source === 'empty' ? 'live' : (data.source || 'live') });
      } else {
        setToolsReport({
          total: 0,
          source: 'mock',
          summary: {},
          tools: MOCK_TOOLS,
          records: [],
        });
      }
    } catch {
      setToolsReport({ total: 0, source: 'mock', summary: {}, tools: MOCK_TOOLS, records: [] });
    } finally {
      setLoading(false);
    }
  }, []);

  const runEvalRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const q = new URLSearchParams({ live: '1' });
      const cid = typeof window !== 'undefined' ? localStorage.getItem('aida-conv-id') : null;
      if (cid) q.set('conv_id', cid);
      const res = await fetch(`${API_BASE}/agent/evals/refresh?${q}`, { method: 'POST' });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`);
      const z = (body as { zhgk?: { ok?: boolean } }).zhgk;
      const t = (body as { tools?: { ok?: boolean } }).tools;
      if (!z?.ok || !t?.ok) {
        flash(`⚠ 评测部分失败 · zhgk=${z?.ok ? 'ok' : 'fail'} tools=${t?.ok ? 'ok' : 'fail'}`);
      } else {
        flash(mode === 'latest' ? '✓ 本次评测已更新' : '✓ 评测已更新');
      }
      await Promise.all([fetchSkill(mode), fetchTools(mode)]);
    } catch (e) {
      flash(`⚠ 无法连接 Agent（7401）：${e instanceof Error ? e.message : String(e)}`);
      await Promise.all([fetchSkill(mode), fetchTools(mode)]);
    } finally {
      setRefreshing(false);
    }
  }, [fetchSkill, fetchTools, flash, mode]);

  useEffect(() => {
    void fetchSkill(mode);
    void fetchTools(mode);
  }, [mode, fetchSkill, fetchTools]);

  useEffect(() => {
    const onRefreshed = () => {
      void fetchSkill(mode);
      void fetchTools(mode);
      flash('✓ 检测到新评测结果，已刷新');
    };
    window.addEventListener(EVALS_REFRESH_EVENT, onRefreshed);
    return () => window.removeEventListener(EVALS_REFRESH_EVENT, onRefreshed);
  }, [mode, fetchSkill, fetchTools, flash]);

  const copyJson = useCallback((obj: object, label: string) => {
    const json = JSON.stringify(obj, null, 2);
    const ok = () => flash(`✓ ${label}已复制 · 粘贴给 CC / Cursor`);
    const fail = () => {
      console.log(`[evals] ${label}:\n${json}`);
      flash('⚠ 剪贴板不可用，已打印到控制台');
    };
    try {
      const p = navigator.clipboard?.writeText(json);
      if (p) p.then(ok, fail);
      else fail();
    } catch {
      fail();
    }
  }, [flash]);

  const exportSkill = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/agent/evals/deviations/skill?skill=zhgk`);
      if (res.ok) copyJson(await res.json(), 'SKILL 偏离 JSON');
      else copyJson(buildDeviations(report.runs), 'SKILL 偏离 JSON');
    } catch {
      copyJson(buildDeviations(report.runs), 'SKILL 偏离 JSON');
    }
  }, [copyJson, report]);

  const tools = toolsReport?.tools ?? MOCK_TOOLS;

  const exportTools = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/agent/evals/deviations/tools`);
      if (res.ok) copyJson(await res.json(), '待优化工具 JSON');
      else copyJson(buildToolDeviations(tools), '待优化工具 JSON');
    } catch {
      copyJson(buildToolDeviations(tools), '待优化工具 JSON');
    }
  }, [copyJson, tools]);

  const live =
    view === 'skill'
      ? report.source === 'live'
      : view === 'tools'
        ? toolsReport?.source !== 'mock' && toolsReport?.source !== 'empty'
        : false;

  return (
    <div className="jn-wrap" style={{ flex: 1, overflow: 'auto' }}>
      <div className="main-inner">
        <div className="page-head">
          <div>
            <h1>AI 评测中心</h1>
            <div className="sub">Skill / 工具 / 可观测三维 · 本次执行 vs 总体趋势</div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                padding: '2px 9px',
                fontSize: 11,
                fontWeight: 600,
                borderRadius: 'var(--r-pill)',
                background: live ? 'var(--c-success-soft)' : 'var(--c-bg-soft)',
                color: live ? 'var(--c-success-text)' : 'var(--c-text-muted)',
                border: `1px solid ${live ? 'var(--c-success)' : 'var(--c-border)'}`,
              }}
            >
              {live ? '● 实时数据' : '○ 演示数据'}
            </span>
            <button
              onClick={() =>
                view === 'tools'
                  ? void fetchTools(mode)
                  : view === 'skill'
                    ? void fetchSkill(mode)
                    : undefined
              }
              disabled={loading || view === 'obs'}
              style={{
                padding: '4px 12px',
                fontSize: 12,
                fontWeight: 600,
                border: '1px solid var(--c-border)',
                borderRadius: 'var(--r-md)',
                background: 'var(--c-surface)',
                color: 'var(--c-text-muted)',
                cursor: loading ? 'wait' : 'pointer',
              }}
            >
              {loading ? '加载中…' : '刷新'}
            </button>
            <button
              onClick={() => void runEvalRefresh()}
              disabled={refreshing}
              title="调用 Agent 跑 eval_zhgk + eval_tools，再刷新图表"
              style={{
                padding: '4px 12px',
                fontSize: 12,
                fontWeight: 600,
                border: '1px solid var(--c-brand)',
                borderRadius: 'var(--r-md)',
                background: 'var(--c-brand-soft)',
                color: 'var(--c-brand)',
                cursor: refreshing ? 'wait' : 'pointer',
              }}
            >
              {refreshing ? '评测中…' : '跑评测'}
            </button>
          </div>
        </div>

        <div className="snap-tabs" style={{ marginBottom: 10 }}>
          {MODE_TABS.map(t => (
            <button
              key={t.key}
              className={`snap-tab${mode === t.key ? ' active' : ''}`}
              onClick={() => setViewMode(view, t.key)}
            >
              <span>{t.label}</span>
            </button>
          ))}
        </div>

        <div className="snap-tabs">
          {TABS.map(t => (
            <button
              key={t.key}
              className={`snap-tab${view === t.key ? ' active' : ''}`}
              onClick={() => setViewMode(t.key, mode)}
            >
              <span>{t.label}</span>
              <span className="v-label">· {t.sub}</span>
            </button>
          ))}
        </div>

        <MetricCommonPanel />

        <MetricGlossaryPanel
          view={view === 'skill' ? 'skill' : view === 'tools' ? 'tools' : 'obs'}
        />

        {toast && (
          <div
            style={{
              padding: '6px 12px',
              background: 'var(--c-success-soft)',
              color: 'var(--c-success-text)',
              borderRadius: 6,
              fontSize: 12,
              marginBottom: 14,
              marginTop: 14,
            }}
          >
            {toast}
          </div>
        )}

        {view === 'skill' && (
          <SkillTab report={report} mode={mode} onExport={() => void exportSkill()} />
        )}
        {view === 'tools' && (
          <ToolsTab
            tools={tools}
            toolsReport={toolsReport}
            mode={mode}
            onExport={() => void exportTools()}
            live={toolsReport?.source !== 'mock' && toolsReport?.source !== 'empty'}
          />
        )}
        {view === 'obs' && <ObsTab obs={MOCK_OBS} />}
      </div>
    </div>
  );
}
