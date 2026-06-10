'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { usePathname } from '@/compat/navigation';
import {
  getSeedForPath,
  getSuggestsForPath,
  getModuleLabel,
} from '../data/claw-seeds';
import { refreshEvals } from '@/lib/eval-refresh';
import { setSkillRun, useSkillRunStore, updateSkillRun } from '@/lib/skillRunStore';
import { useSkillHitlStore } from '@/lib/skillHitlStore';
import { startRun } from '@/hooks/useSduiStream';
import { SduiNodeView } from '@/components/sdui/SduiNodeView';
import { SduiRuntimeContext } from '@/components/sdui/SduiContext';

const AGENT_BASE = import.meta.env.VITE_AGENT_BASE || 'http://127.0.0.1:7401';

// ── Types ───────────────────────────────────────────────────────────────────

interface ToolEvent {
  name: string;
  args?: Record<string, unknown>;
  result?: string;
}

interface SkillLaunch {
  skill: string;
  projectCode: string;
  scenarioRun: string;
  steps: Array<{ step: string; name: string }>;
}

interface ChoiceOption {
  label: string;
  value?: string;
}

interface ChoiceCardData {
  question: string;
  options: ChoiceOption[];
}

interface ToolApprovalInfo {
  approval_id: string;
  name: string;
  args: Record<string, unknown>;
  decided?: 'approved' | 'denied';
}

/** 解析 tool_result 字符串，识别 dry-run / 失败 */
function toolResultStatus(result: string): 'pending' | 'ok' | 'dry_run' | 'fail' {
  if (result.startsWith('Error') || result.includes("'ok': False") || result.includes('"ok": false')) {
    return 'fail';
  }
  if (result.includes('dry_run') && (result.includes('True') || result.includes('true'))) {
    return 'dry_run';
  }
  return 'ok';
}

interface Msg {
  role: 'user' | 'ai';
  body: string;
  ts: string;
  chips?: string[];
  reasoning?: Array<{ ix: string; text: string }>;
  actions?: Array<{ label: string; kind: string; icon?: string }>;
  isStreaming?: boolean;
  toolEvents?: ToolEvent[];
  skillLaunch?: SkillLaunch;
  skillRun?: { skillId: string };   // 右侧模块页启动时由 ClawRail store 监听器注入
  choiceCard?: ChoiceCardData;
  pendingApproval?: ToolApprovalInfo;
}

// ── Icons ───────────────────────────────────────────────────────────────────

const IcSparkle = () => (
  <svg width={11} height={11} viewBox="0 0 11 11" fill="none">
    <path d="M5.5 0.5 L6.4 4.6 L10.5 5.5 L6.4 6.4 L5.5 10.5 L4.6 6.4 L0.5 5.5 L4.6 4.6 Z" fill="currentColor" />
  </svg>
);
const IcChevron = () => (
  <svg width={12} height={12} viewBox="0 0 9 9" fill="none">
    <path d="M3 1 L6 4.5 L3 8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="square" fill="none" />
  </svg>
);
const IcSwap = () => (
  <svg width={13} height={13} viewBox="0 0 16 16" fill="none">
    <path d="M3 5.5 H12.5 M10 3 L12.5 5.5 L10 8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    <path d="M13 10.5 H3.5 M6 8 L3.5 10.5 L6 13" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
  </svg>
);
const IcMaximize = () => (
  <svg width={12} height={12} viewBox="0 0 12 12" fill="none">
    <path d="M2 4 L2 2 L4 2 M8 2 L10 2 L10 4 M2 8 L2 10 L4 10 M8 10 L10 10 L10 8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="square" fill="none" />
  </svg>
);
const IcMinimize = () => (
  <svg width={12} height={12} viewBox="0 0 12 12" fill="none">
    <path d="M4 2 L4 4 L2 4 M8 4 L10 4 L10 2 M4 10 L4 8 L2 8 M10 8 L8 8 L8 10" stroke="currentColor" strokeWidth="1.2" strokeLinecap="square" fill="none" />
  </svg>
);
const IcAttach = () => (
  <svg width={13} height={13} viewBox="0 0 14 14" fill="none">
    <path d="M9.5 4 L4.5 9 C3.5 10 3.5 11.5 4.5 12.5 C5.5 13.5 7 13.5 8 12.5 L13 7.5" stroke="currentColor" strokeWidth="1.1" fill="none" strokeLinecap="square" />
  </svg>
);
const IcFilter = () => (
  <svg width={12} height={12} viewBox="0 0 12 12" fill="none">
    <path d="M1 2 L11 2 L7 6 L7 10 L5 11 L5 6 Z" stroke="currentColor" strokeWidth="1" fill="none" />
  </svg>
);
const IcSend = () => (
  <svg width={10} height={10} viewBox="0 0 12 12" fill="none">
    <path d="M1 11 L11 6 L1 1 L2.5 6 Z" fill="currentColor" />
  </svg>
);
const IcDashboard = () => (
  <svg width={10} height={10} viewBox="0 0 16 16" fill="none">
    <rect x="2" y="2" width="5.5" height="7" stroke="currentColor" strokeWidth="1" fill="none" />
    <rect x="8.5" y="2" width="5.5" height="4" stroke="currentColor" strokeWidth="1" fill="none" />
    <rect x="8.5" y="7" width="5.5" height="7" stroke="currentColor" strokeWidth="1" fill="none" />
  </svg>
);
const IcEye = () => (
  <svg width={11} height={11} viewBox="0 0 12 12" fill="none">
    <path d="M1 6 C2.5 3 4 2 6 2 C8 2 9.5 3 11 6 C9.5 9 8 10 6 10 C4 10 2.5 9 1 6 Z" stroke="currentColor" strokeWidth="1" fill="none" />
    <circle cx="6" cy="6" r="1.6" stroke="currentColor" strokeWidth="1" fill="none" />
  </svg>
);
const IcSandbox = () => (
  <svg width={11} height={11} viewBox="0 0 12 12" fill="none">
    <rect x="1" y="2" width="10" height="8" stroke="currentColor" strokeWidth="1" fill="none" strokeDasharray="2 1.5" />
    <path d="M3 6 L5 6 L5.5 4.5 L7 7.5 L7.5 6 L9 6" stroke="currentColor" strokeWidth="1" fill="none" />
  </svg>
);
const IcDoc = () => (
  <svg width={11} height={11} viewBox="0 0 11 11" fill="none">
    <path d="M2 1 L7 1 L9.5 3.5 L9.5 10 L2 10 Z" stroke="currentColor" strokeWidth="0.9" fill="none" />
    <path d="M7 1 L7 3.5 L9.5 3.5" stroke="currentColor" strokeWidth="0.9" fill="none" />
  </svg>
);

const ACTION_ICONS = { Eye: IcEye, Sandbox: IcSandbox, Doc: IcDoc } as const;

function ActionIcon({ name }: { name: string }) {
  const Ic = ACTION_ICONS[name as keyof typeof ACTION_ICONS];
  return Ic ? <Ic /> : null;
}

// ── Proposal upload panel ───────────────────────────────────────────────────

const PROPOSAL_DOCS = [
  { key: 'hld',     label: 'HLD 总体设计',  accept: '.docx,.pdf', required: true  },
  { key: 'cad',     label: 'CAD 机房底图',  accept: '.dwg,.dxf',  required: false },
  { key: 'presale', label: '售前工勘 PPT',  accept: '.pptx,.pdf', required: true  },
  { key: 'maint',   label: '维护建议书',    accept: '.docx,.pdf', required: false },
  { key: 'train',   label: '培训建议书',    accept: '.docx,.pdf', required: false },
  { key: 'service', label: '服务建议书',    accept: '.docx,.pdf', required: false },
  { key: 'rfp',     label: '提资文件',      accept: '.zip,.pdf',  required: false },
];

function ProposalUploadPanel() {
  const [uploadedDocs, setUploadedDocs] = useState<Record<string, string>>({
    hld: '1.8 MB',
    presale: '4.2 MB',
    rfp: '已上传',
  });

  const requiredDocs  = PROPOSAL_DOCS.filter(d => d.required);
  const missingRequired = requiredDocs.filter(d => !uploadedDocs[d.key]);
  const uploadedCount = Object.keys(uploadedDocs).length;

  const handleUpload = (docKey: string, label: string, file: File) => {
    const size = file.size > 1024 * 1024
      ? `${(file.size / 1024 / 1024).toFixed(1)} MB`
      : `${Math.round(file.size / 1024)} KB`;
    setUploadedDocs(prev => ({ ...prev, [docKey]: size }));
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('aida:progress', {
        detail: {
          role: 'ai',
          body: `已收到「${label}」(${size})，正在后台解析，结果将自动填入对应章节。`,
          chips: [label, '解析中'],
        },
      }));
    }
  };

  const IcCheck = () => (
    <svg className="upload-ic-check" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.2"/>
      <path d="M5 8l2.5 2.5L11 5.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
  const IcPlus = () => (
    <svg className="upload-ic-plus" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.2"/>
      <path d="M8 5v6M5 8h6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
    </svg>
  );

  return (
    <div className="claw-module-ctl">
      <div style={{ padding: '10px 14px 4px', display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 10.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#a1a1aa' }}>文件上传</span>
        <span style={{ fontSize: 11, color: missingRequired.length === 0 ? '#10b981' : '#a1a1aa' }}>
          {uploadedCount}/{PROPOSAL_DOCS.length}
          {missingRequired.length === 0 ? ' ✓' : ''}
        </span>
      </div>

      <div style={{ padding: '0 14px 8px' }}>
        {PROPOSAL_DOCS.map(d => {
          const uploaded = !!uploadedDocs[d.key];
          const inputId = `proposal-upload-${d.key}`;
          return (
            <label key={d.key} htmlFor={inputId} className="upload-list-item">
              {uploaded ? <IcCheck /> : <IcPlus />}
              <span className="upload-list-name">
                {d.label}
                {d.required && <span className="upload-req-badge">必传</span>}
              </span>
              <span className="upload-list-meta">
                {uploaded ? uploadedDocs[d.key] : '上传'}
              </span>
              <input
                id={inputId}
                type="file"
                accept={d.accept}
                style={{ display: 'none' }}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleUpload(d.key, d.label, file);
                  e.target.value = '';
                }}
              />
            </label>
          );
        })}
      </div>

      {missingRequired.length > 0 && (
        <div style={{ margin: '4px 14px 8px', padding: '7px 10px', background: 'rgba(251,191,36,0.08)', borderRadius: 6, fontSize: 11, color: '#92400e' }}>
          还缺 {missingRequired.length} 项：{missingRequired.map(d => d.label).join(' / ')}
        </div>
      )}
      {missingRequired.length === 0 && (
        <div className="claw-module-ctl-card" style={{ borderColor: 'rgba(15,157,88,0.4)', background: 'rgba(15,157,88,0.04)' }}>
          <div className="claw-mc-card-body">
            <div className="claw-mc-card-title">✓ 必传项已齐备</div>
            <div className="claw-mc-card-sub">可点击「生成预案并决策」推进流程</div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Module control panel (per-route widgets) ────────────────────────────────

function ModuleControlPanel({ pathname }: { pathname: string }) {
  const [parseProgress, setParseProgress] = useState(0);
  const [parseStage, setParseStage] = useState('等待开始');
  const [needRefresh, setNeedRefresh] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const onProgress = (e: Event) => {
      const body = ((e as CustomEvent<{ body?: string }>).detail?.body) ?? '';
      if (body.includes('开始解析')) { setParseProgress(10); setParseStage('拉取 BOQ 文件…'); setNeedRefresh(false); }
      else if (body.includes('收到 · 已挂起'))     { setParseProgress(25); setParseStage('设备类解析中…'); }
      else if (body.includes('设备类 BOQ 已解析')) { setParseProgress(55); setParseStage('检测数据冲突…'); }
      else if (body.includes('服务类 BOQ 已分到')) { setParseProgress(80); setParseStage('服务类分类中…'); }
      else if (body.includes('已把') && body.includes('冲突自动登记')) { setParseProgress(95); setParseStage('写入风险列表…'); }
      else if (body.includes('全部解析任务已完成')) { setParseProgress(100); setParseStage('解析完成'); setNeedRefresh(true); }
    };
    window.addEventListener('aida:progress', onProgress);
    return () => window.removeEventListener('aida:progress', onProgress);
  }, []);

  if (pathname.includes('/preview')) {
    return (
      <div className="claw-module-ctl">
        <div className="claw-module-ctl-head">合同解析 · 模块控件</div>
        <div className="claw-module-ctl-card">
          <div className="claw-mc-ring">
            <svg viewBox="0 0 36 36" width="48" height="48">
              <circle cx="18" cy="18" r="15.9" fill="none" stroke="var(--c-bg-soft)" strokeWidth="3" />
              <circle
                cx="18" cy="18" r="15.9" fill="none"
                stroke={parseProgress >= 100 ? 'var(--c-success)' : '#1b84ff'}
                strokeWidth="3"
                strokeLinecap="round"
                strokeDasharray={`${parseProgress} 100`}
                transform="rotate(-90 18 18)"
              />
            </svg>
            <div className="claw-mc-ring-text">{parseProgress}%</div>
          </div>
          <div className="claw-mc-card-body">
            <div className="claw-mc-card-title">当前解析的进度</div>
            <div className="claw-mc-card-sub">{parseStage}</div>
          </div>
        </div>
        <button
          type="button"
          className={`claw-module-ctl-card claw-mc-hitl${needRefresh ? ' on' : ''}`}
          onClick={() => { if (needRefresh && typeof window !== 'undefined') window.location.reload(); }}
          disabled={!needRefresh}
        >
          <div className="claw-mc-hitl-ic">{needRefresh ? '⟳' : '○'}</div>
          <div className="claw-mc-card-body">
            <div className="claw-mc-card-title">HITL 解析以完成</div>
            <div className="claw-mc-card-sub">{needRefresh ? '点击刷新页面查看' : '解析进行中…'}</div>
          </div>
        </button>
      </div>
    );
  }

  if (pathname.includes('/proposal')) {
    return <ProposalUploadPanel />;
  }

  if (pathname.includes('/create')) {
    return (
      <div className="claw-module-ctl">
        <div className="claw-module-ctl-head">文档摄取 · 进度</div>
        <div className="claw-module-ctl-card">
          <div className="claw-mc-card-body">
            <div className="claw-mc-card-title">当前已有 4 / 8 文档</div>
            <div className="claw-mc-card-sub">HLD ✓ BOQ ✓ CAD ✓ 售前 PPT ✓</div>
          </div>
        </div>
        <div className="claw-module-ctl-card warn">
          <div className="claw-mc-card-body">
            <div className="claw-mc-card-title">需要上传 4 项</div>
            <div className="claw-mc-card-sub">维护建议书 / 培训建议书 / 提资文件 / 服务建议书</div>
          </div>
        </div>
      </div>
    );
  }

  if (pathname.includes('/cockpit')) {
    return (
      <div className="claw-module-ctl">
        <div className="claw-module-ctl-head">态势监盘 · 实时</div>
        <div className="claw-module-ctl-card alert">
          <div className="claw-mc-card-body">
            <div className="claw-mc-card-title">3 项不可满足</div>
            <div className="claw-mc-card-sub">B2 配电延期 / A1-ESS / D4 断电</div>
          </div>
        </div>
        <div className="claw-module-ctl-card warn">
          <div className="claw-mc-card-body">
            <div className="claw-mc-card-title">5 项 at-risk</div>
            <div className="claw-mc-card-sub">物流 / 调试档期 / 跨境合规</div>
          </div>
        </div>
      </div>
    );
  }

  if (pathname.includes('/plan')) {
    return (
      <div className="claw-module-ctl">
        <div className="claw-module-ctl-head">计划 · 自动填充</div>
        <div className="claw-module-ctl-card">
          <div className="claw-mc-card-body">
            <div className="claw-mc-card-title">机房 14 · PoD 36 · GPU 1920</div>
            <div className="claw-mc-card-sub">已从 HLD/CAD/BOQ 自动填入</div>
          </div>
        </div>
      </div>
    );
  }

  if (pathname.includes('/design')) {
    return (
      <div className="claw-module-ctl">
        <div className="claw-module-ctl-head">LLD · 章节齐备</div>
        <div className="claw-module-ctl-card">
          <div className="claw-mc-card-body">
            <div className="claw-mc-card-title">12 / 12 章节</div>
            <div className="claw-mc-card-sub">已冻结 LLD-v1.0</div>
          </div>
        </div>
      </div>
    );
  }

  if (pathname.includes('/sandbox')) {
    return (
      <div className="claw-module-ctl">
        <div className="claw-module-ctl-head">沙箱 · 当前推演</div>
        <div className="claw-module-ctl-card">
          <div className="claw-mc-card-body">
            <div className="claw-mc-card-title">α · 命中率 78%</div>
            <div className="claw-mc-card-sub">自动应用档</div>
          </div>
        </div>
      </div>
    );
  }

  return null;
}

// ── SSE helpers ─────────────────────────────────────────────────────────────

function nowTs() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function genConvId(): string {
  return (typeof crypto !== 'undefined' && crypto.randomUUID)
    ? `conv-${crypto.randomUUID()}`
    : `conv-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

// ── Skill 运行进度卡（左侧会话 · 轻量版）────────────────────────────────────────
// 替代原 ZhgkProgressCard：不开独立 SSE，不含 HITL UI。
// 右侧 SkillAgentScreen 的 SDUI 流解析后写入 skillRunStore，此卡实时反映。
//
// autoStart=true  → 聊天侧 skill_launch 触发，卡片调 /start 写入 store（source='chat'）。
// autoStart=false → 右侧模块页启动，store 已有 runId，卡片仅读取 store 展示进度。

const SKILL_LABELS: Record<string, string> = {
  zhgk: '智慧工勘',
  guihua: '规划设计',
};

function SkillRunBanner({
  skillId,
  projectCode = '',
  scenarioRun = '',
  autoStart = false,
}: {
  skillId: string;
  projectCode?: string;
  scenarioRun?: string;
  autoStart?: boolean;
}) {
  const info     = useSkillRunStore();
  const myInfo   = info?.skillId === skillId ? info : null;
  const myRunId  = myInfo?.runId;
  const startedRef = useRef(false);
  const skillLabel = SKILL_LABELS[skillId] ?? skillId;

  // Auto-start（chat 触发）：
  // - startedRef 防止同组件重复触发（正常场景）
  // - myRunId 为真值（含 '__starting__'）防止 React StrictMode 二次挂载重复调用
  useEffect(() => {
    if (!autoStart) return;
    if (startedRef.current) return;
    if (myRunId) return;          // '__starting__' 为 truthy → StrictMode 二次挂载会跳过

    startedRef.current = true;
    void (async () => {
      try {
        setSkillRun(skillId, '__starting__', 'chat'); // 占位，阻断二次启动
        const runId = await startRun(skillId, {
          project_code: projectCode,
          scenario_run: scenarioRun || '训推一体',
        });
        setSkillRun(skillId, runId, 'chat');
        updateSkillRun({ phase: 'running' });
      } catch (err) {
        updateSkillRun({
          phase: 'error',
          errorMsg: err instanceof Error ? err.message : '启动失败',
        });
      }
    })();
  }, [autoStart, skillId, projectCode, scenarioRun, myRunId]);

  const phase    = myInfo?.phase           ?? 'starting';
  const progress = myInfo?.progress        ?? 0;
  const stepName = myInfo?.currentStepName ?? '';
  const hitlType = myInfo?.hitlType        ?? null;
  const errorMsg = myInfo?.errorMsg        ?? '';

  // HITL 交互卡（由右侧 SkillAgentScreen 抽取写入）：在左侧会话框内可交互渲染
  const hitlInfo = useSkillHitlStore();
  const myHitl   = hitlInfo?.skillId === skillId ? hitlInfo : null;

  const badgeText =
    phase === 'starting'  ? '启动中…'
    : phase === 'hitl'    ? (hitlType === 'choice' ? '⏸ 待选择' : '⏸ 待文件')
    : phase === 'running' ? `执行中 ${progress}%`
    : phase === 'done'    ? '已完成 ✓'
    : phase === 'error'   ? '出错'
    : '…';

  const badgeClass =
    phase === 'hitl'   ? 'hitl'
    : phase === 'done'  ? 'done'
    : phase === 'error' ? 'error'
    : 'running';

  return (
    <div className="zhgk-card">
      <div className="zhgk-card-head">
        <span className="zhgk-card-title">🛠 {skillLabel}</span>
        <span className={`zhgk-card-badge ${badgeClass}`}>{badgeText}</span>
      </div>

      <div className="zhgk-card-bar">
        <div
          className="zhgk-card-bar-fill"
          style={{ width: `${phase === 'done' ? 100 : progress}%` }}
        />
      </div>

      {phase !== 'hitl' && (
        <div className="zhgk-card-info">
          {phase === 'running' && stepName && (
            <span className="zhgk-card-curstep">▸ {stepName}</span>
          )}
          {phase === 'done' && (
            <span className="zhgk-card-curstep" style={{ color: 'var(--green-700)' }}>
              ✓ 全部步骤完成
            </span>
          )}
          {phase === 'starting' && (
            <span className="zhgk-card-curstep">正在启动…</span>
          )}
        </div>
      )}

      {/* HITL 交互卡：直接在左侧会话框内可操作（选择 / 上传），回调直连右侧 resume */}
      {phase === 'hitl' && myHitl && (
        <div style={{ margin: '6px 10px 10px' }}>
          <SduiRuntimeContext.Provider
            value={{
              runId: myHitl.runId,
              onAction: () => {},
              onUpload: myHitl.onUpload,
              onChoiceSubmit: myHitl.onChoiceSubmit,
            }}
          >
            <SduiNodeView node={myHitl.node} />
          </SduiRuntimeContext.Provider>
        </div>
      )}

      {/* 兜底提示：标记为 HITL 但交互卡尚未就绪（极少见，如刚切换尚未同步）*/}
      {phase === 'hitl' && !myHitl && (
        <div style={{
          margin: '6px 10px 8px',
          padding: '8px 10px',
          background: 'rgba(251,191,36,.06)',
          border: '1px solid rgba(217,119,6,.2)',
          borderRadius: 6,
          fontSize: '11px',
          color: '#92400e',
          lineHeight: 1.5,
        }}>
          <strong>{hitlType === 'choice' ? '⏸ 需要确认选项' : '⏸ 需要上传文件'}</strong>
          <br />
          请在右侧操作面板{hitlType === 'choice' ? '完成选择' : '上传所需文件'}后继续。
        </div>
      )}

      {phase === 'error' && errorMsg && (
        <div className="zhgk-card-err">{errorMsg}</div>
      )}
    </div>
  );
}

// ── 敏感工具审批卡：send_mail / send_welink 执行前 HITL ───────────────────────

function ToolApprovalCard({
  info,
  onDecide,
}: {
  info: ToolApprovalInfo;
  onDecide: (approvalId: string, approved: boolean) => void;
}) {
  const decided = info.decided;
  return (
    <div className={`tool-approval-card${decided ? ` is-${decided}` : ''}`}>
      <div className="tool-approval-head">
        <span>{decided === 'approved' ? '✓' : decided === 'denied' ? '✗' : '🔧'}</span>
        <span>
          {decided === 'approved' ? '已批准' : decided === 'denied' ? '已拒绝' : '工具调用请求'} · {info.name}
        </span>
      </div>
      {Object.keys(info.args).length > 0 && (
        <pre className="tool-approval-args">{JSON.stringify(info.args, null, 2)}</pre>
      )}
      {!decided && (
        <div className="tool-approval-actions">
          <button type="button" className="a-btn primary" onClick={() => onDecide(info.approval_id, true)}>
            批准执行
          </button>
          <button type="button" className="a-btn" onClick={() => onDecide(info.approval_id, false)}>
            拒绝
          </button>
        </div>
      )}
    </div>
  );
}

// ── 选项确认卡：present_choices 结果（发信前确认等）────────────────────────────

function ChoiceCard({ data, onSelect }: {
  data: ChoiceCardData;
  onSelect: (value: string, label: string) => void;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  return (
    <div className="choice-card">
      <div className="choice-q">{data.question}</div>
      <div className="choice-opts">
        {data.options.map((opt, i) => (
          <button
            key={i}
            type="button"
            className={`choice-opt${selected === opt.label ? ' active' : ''}`}
            disabled={!!selected}
            onClick={() => {
              if (selected) return;
              const val = opt.value ?? opt.label;
              setSelected(opt.label);
              onSelect(val, opt.label);
            }}
          >
            {opt.label}
          </button>
        ))}
      </div>
      {selected && <div className="choice-result">→ 已选择：{selected}</div>}
    </div>
  );
}

// ── Main component ───────────────────────────────────────────────────────────

export default function ClawRail({
  collapsed,
  onToggle,
  width = 360,
  onResize,
  onSwap,
}: {
  collapsed: boolean;
  onToggle: () => void;
  width?: number;
  onResize?: (w: number) => void;
  onSwap?: () => void;
}) {
  const [draft, setDraft] = useState('');
  const threadRef = useRef<HTMLDivElement>(null);
  const [maximized, setMaximized] = useState(false);
  const [savedWidth, setSavedWidth] = useState<number | null>(null);

  const pathname = usePathname() ?? '';

  // Real chat messages (user ↔ AI turns)
  const [chatMsgs, setChatMsgs] = useState<Msg[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  // 会话 id：多轮记忆的 key（§3.5）。每条路由 = 独立会话，记忆隔离。
  const [convId, setConvId] = useState<string>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('aida-conv-id');
      if (saved) return saved;
    }
    return genConvId();
  });

  useEffect(() => {
    if (convId) localStorage.setItem('aida-conv-id', convId);
  }, [convId]);

  const toggleMaximize = () => {
    if (typeof window === 'undefined') return;
    if (!maximized) {
      const target = Math.min(720, Math.floor(window.innerWidth * 0.55));
      setSavedWidth(width);
      onResize?.(target);
      setMaximized(true);
    } else {
      onResize?.(savedWidth ?? 360);
      setMaximized(false);
    }
  };

  const seedForPath = getSeedForPath(pathname) as Msg[];
  const suggestsForPath = getSuggestsForPath(pathname) as string[];
  const moduleLabel = getModuleLabel(pathname) as string;

  // External async events from other parts of the app (BOQ parse progress, etc.)
  const [appendMsgs, setAppendMsgs] = useState<Msg[]>([]);

  // ── 右侧模块页启动 run 时，自动在左侧会话注入 SkillRunBanner ─────────────────
  const skillRun = useSkillRunStore();
  // 记录已注入的 run_id，防重复注入（路由清空后由 pathname effect 重置）
  const injectedRunIds = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const onProgress = (e: Event) => {
      const msg = (e as CustomEvent<Partial<Msg>>).detail;
      if (!msg?.body) return;
      const ts = msg.ts ?? nowTs();
      setAppendMsgs(prev => [...prev, { role: msg.role ?? 'ai', body: msg.body!, ts, ...msg }]);
    };
    const onClear = () => setAppendMsgs([]);
    window.addEventListener('aida:progress', onProgress);
    window.addEventListener('aida:clear', onClear);
    return () => {
      window.removeEventListener('aida:progress', onProgress);
      window.removeEventListener('aida:clear', onClear);
    };
  }, []);

  // Clear per-route messages when navigating（新路由 = 新会话，记忆隔离）
  useEffect(() => {
    setAppendMsgs([]);
    setChatMsgs([]);
    setConvId(genConvId());
    injectedRunIds.current.clear(); // 允许新路由重新注入进度卡
  }, [pathname]);

  // cockpit: fire synthetic progress after project create/edit
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!pathname.includes('/cockpit')) return;
    let payload: { mode?: string; fields?: { name?: string } } | undefined;
    try {
      const raw = sessionStorage.getItem('aida:just-created');
      if (!raw) return;
      payload = JSON.parse(raw) as typeof payload;
      sessionStorage.removeItem('aida:just-created');
    } catch { return; }

    const isEdit = payload?.mode === 'edit';
    const name = payload?.fields?.name ?? '新项目';
    const fire = (delay: number, detail: Partial<Msg>) =>
      setTimeout(() => window.dispatchEvent(new CustomEvent('aida:progress', { detail })), delay);

    fire(200, {
      role: 'ai',
      body: isEdit
        ? `已收到「${name}」的字段修改，正在更新项目空间元数据…`
        : `已收到「${name}」的创建指令 · 开始为你拉起项目容器…`,
      reasoning: [
        { ix: '1', text: 'Resolve · PD/TD/PCM 工号校验 → OK' },
        { ix: '2', text: 'Provision · 容器镜像 aida-twin:2026.05 (~3 GB)' },
        { ix: '3', text: 'Pull · 预计 8 秒' },
      ],
    });
    fire(1700, {
      role: 'ai',
      body: '容器已就绪 · 项目孪生看板正在与你眼前同步刷新。同时我已挂起 BOQ 异步解析任务，看到这条消息时一般已在跑。',
      chips: ['容器拉起 OK', 'BOQ 异步解析'],
    });
    if (!isEdit) {
      fire(3400, {
        role: 'ai',
        body: '机会点关联检索完成 · 找到 3 份 3 月内未交付合同 + 6 份 BOQ；建议进 早期接入 → 合同 与 BOQ 复核数量。',
        chips: ['3 份合同', '6 份 BOQ'],
        actions: [{ label: '去复核', kind: 'primary', icon: 'Eye' }],
      });
    }
  }, [pathname]);

  // 注入 SkillRunBanner：仅对 source='ui'（右侧模块页启动）的 run 注入
  // source='chat' 的 run 由 skill_launch 事件直接在 chatMsgs 里渲染，不重复注入
  useEffect(() => {
    if (!skillRun || skillRun.source !== 'ui') return;
    const rid = skillRun.runId;
    if (!rid || rid === '__starting__') return;
    if (injectedRunIds.current.has(rid)) return;
    injectedRunIds.current.add(rid);
    setAppendMsgs(prev => [
      ...prev,
      { role: 'ai' as const, body: '', ts: nowTs(), skillRun: { skillId: skillRun.skillId } },
    ]);
  }, [skillRun?.runId, skillRun?.source]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (threadRef.current) {
      threadRef.current.scrollTop = threadRef.current.scrollHeight;
    }
  }, [appendMsgs.length, chatMsgs.length, pathname]);

  const allMsgs: Msg[] = [...seedForPath, ...appendMsgs, ...chatMsgs];

  // ── Send helpers ──────────────────────────────────────────────────────────

  // 核心发送逻辑，接受文本直接驱动（ChoiceCard 选择 / 正常发送均走此路径）
  const decideTool = useCallback(async (approvalId: string, approved: boolean) => {
    setChatMsgs(prev => prev.map(m => {
      if (!m.pendingApproval || m.pendingApproval.approval_id !== approvalId) return m;
      return {
        ...m,
        pendingApproval: { ...m.pendingApproval, decided: approved ? 'approved' : 'denied' },
      };
    }));
    await fetch(`${AGENT_BASE}/agent/chat/approve-tool`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approval_id: approvalId, approved }),
    });
  }, []);

  const sendText = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) return;

    setChatMsgs(prev => [...prev, { role: 'user', body: trimmed, ts: nowTs() }]);
    setIsStreaming(true);
    setChatMsgs(prev => [...prev, { role: 'ai', body: '', ts: nowTs(), isStreaming: true, toolEvents: [] }]);

    // Patch the last streaming AI message
    const patch = (fn: (m: Msg) => Msg) => {
      setChatMsgs(prev => {
        const arr = [...prev];
        const last = arr[arr.length - 1];
        if (last?.role === 'ai' && last.isStreaming) {
          arr[arr.length - 1] = fn(last);
        }
        return arr;
      });
    };

    try {
      const res = await fetch(`${AGENT_BASE}/agent/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: trimmed, conv_id: convId, context: { page: pathname } }),
      });

      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      let curEvent = '';
      let hadToolCalls = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() ?? '';

        for (const line of lines) {
          const t = line.trim();
          if (!t) { curEvent = ''; continue; }
          if (t.startsWith('event: ')) { curEvent = t.slice(7); continue; }
          if (!t.startsWith('data: ')) continue;

          let ev: Record<string, unknown>;
          try { ev = JSON.parse(t.slice(6)) as Record<string, unknown>; } catch { continue; }

          const type = curEvent || (ev.type as string);
          if (type === 'token') {
            patch(m => ({ ...m, body: m.body + ((ev.text as string | undefined) ?? '') }));
          } else if (type === 'tool_call') {
            hadToolCalls = true;
            patch(m => ({
              ...m,
              toolEvents: [
                ...(m.toolEvents ?? []),
                { name: ev.name as string, args: ev.args as Record<string, unknown> | undefined },
              ],
            }));
          } else if (type === 'tool_result') {
            patch(m => {
              const evts = [...(m.toolEvents ?? [])];
              for (let i = evts.length - 1; i >= 0; i--) {
                if (evts[i]?.name === (ev.name as string) && evts[i]!.result === undefined) {
                  evts[i] = { ...evts[i]!, result: ev.result as string };
                  break;
                }
              }
              return { ...m, toolEvents: evts };
            });
          } else if (type === 'skill_launch') {
            patch(m => ({
              ...m,
              skillLaunch: {
                skill: ev.skill as string,
                projectCode: (ev.project_code as string) ?? '',
                scenarioRun: (ev.scenario_run as string) ?? '',
                steps: (ev.steps as Array<{ step: string; name: string }>) ?? [],
              },
            }));
          } else if (type === 'choices') {
            // present_choices：模型发信/IM 前确认，展示选项卡；用户选择后以新消息续对话
            patch(m => ({
              ...m,
              choiceCard: {
                question: (ev.question as string) ?? '',
                options: (ev.options as ChoiceOption[]) ?? [],
              },
            }));
          } else if (type === 'tool_approval_required') {
            patch(m => ({
              ...m,
              pendingApproval: {
                approval_id: (ev.approval_id as string) ?? '',
                name: (ev.name as string) ?? '',
                args: (ev.args as Record<string, unknown>) ?? {},
              },
            }));
          } else if (type === 'done') {
            patch(m => ({ ...m, isStreaming: false }));
          } else if (type === 'error') {
            patch(m => ({ ...m, body: m.body || `⚠ ${ev.message as string}`, isStreaming: false }));
          }
        }
      }
      if (hadToolCalls && convId) {
        void refreshEvals({ conv_id: convId, force: true }).then(ok => {
          if (ok && typeof window !== 'undefined') {
            window.dispatchEvent(
              new CustomEvent('aida-evals-toast', {
                detail: { message: '工具评测已更新 · 打开 AI 评测 → 本次执行 → 工具测评' },
              }),
            );
          }
        });
      }
    } catch (err) {
      setChatMsgs(prev => {
        const arr = [...prev];
        const last = arr[arr.length - 1];
        if (last?.role === 'ai' && last.isStreaming) {
          arr[arr.length - 1] = {
            ...last,
            body: `连接失败：${err instanceof Error ? err.message : '未知错误'}`,
            isStreaming: false,
          };
        }
        return arr;
      });
    } finally {
      setIsStreaming(false);
    }
  }, [isStreaming, pathname, convId]);

  const sendMessage = useCallback(async () => {
    const text = draft.trim();
    if (!text || isStreaming) return;
    setDraft('');
    await sendText(text);
  }, [draft, isStreaming, sendText]);

  // ── Resize drag ───────────────────────────────────────────────────────────

  const onResizeStart = (e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = width;
    const MIN = 280, MAX = 600;
    let lastW = startW;
    const onMove = (ev: MouseEvent) => {
      const delta = startX - ev.clientX;
      lastW = Math.max(MIN, Math.min(MAX, startW + delta));
      document.documentElement.style.setProperty('--claw-w', lastW + 'px');
    };
    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
      if (onResize) onResize(lastW);
    };
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      void sendMessage();
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <aside className={`claw-rail${collapsed ? ' claw-rail--collapsed' : ''}`}>
      <div className="claw-rail-resize" onMouseDown={onResizeStart} title="拖拽调整宽度" />
      {onSwap && (
        <button onClick={onSwap} title="左右互换 · 默认放左边" className="claw-swap-btn">
          <IcSwap />
        </button>
      )}
      {onResize && (
        <button
          onClick={toggleMaximize}
          title={maximized ? '还原对话栏宽度' : '最大化对话栏（55% 视口）'}
          className="claw-maximize-btn"
        >
          {maximized ? <IcMinimize /> : <IcMaximize />}
        </button>
      )}

      {/* collapsed strip */}
      <div className="claw-mini" onClick={onToggle} title="展开 AIDA 助手">
        <div style={{ width: 28, height: 28, borderRadius: 6, background: 'var(--c-brand-soft)', display: 'grid', placeItems: 'center', color: 'var(--c-brand)' }}>
          <IcSparkle />
        </div>
        <span className="live-dot" />
        <div style={{ fontSize: 9, writingMode: 'vertical-lr', color: 'var(--c-text-muted)', letterSpacing: '.06em' }}>AIDA · ONLINE</div>
      </div>

      {/* header */}
      <div className="claw-head" onClick={onToggle} title={collapsed ? '展开 AIDA 助手' : '折叠 AIDA 助手'}>
        <div className="ch-icon"><IcSparkle /></div>
        <div style={{ flex: 1 }}>
          <div className="ch-name">AIDA 助手 · <span style={{ color: 'var(--c-text-muted)', fontWeight: 400 }}>{moduleLabel}</span></div>
        </div>
        <span className="ch-collapse"><IcChevron /></span>
      </div>

      {/* context chips */}
      <div className="claw-context">
        <span style={{ color: 'var(--c-text-faint)', letterSpacing: '0.4px' }}>CONTEXT</span>
        <span className="ctx-pill"><IcDashboard />交付态势 · 智算 Q2</span>
        <span className="ctx-pill" style={{ background: 'transparent', color: 'var(--c-text-muted)', borderColor: 'var(--c-border)' }}>
          36 PoD · 14 机房
        </span>
      </div>

      <ModuleControlPanel pathname={pathname} />

      {/* thread */}
      <div className="claw-thread" ref={threadRef}>
        {allMsgs.map((m, i) => (
          <div key={i} className={`cmsg ${m.role}`}>
            <div className="meta">
              {m.role === 'ai' ? 'AIDA · ' : '何博 · '}{m.ts}
            </div>
            <div className="body">
              {m.chips ? (
                <>
                  {m.body.split(/B2 配电延期|交付盘子.*?Q2|A1 移交里程碑|A1 关键路径|施工队 7 负载/g).reduce<React.ReactNode[]>((acc, part, idx) => {
                    acc.push(part);
                    const chip = m.chips?.[idx];
                    if (chip !== undefined) {
                      acc.push(<span key={idx} className="ref-chip">{chip}</span>);
                    }
                    return acc;
                  }, [])}
                </>
              ) : m.body}
              {/* Tool call indicators for streaming AI messages */}
              {m.toolEvents && m.toolEvents.length > 0 && (
                <div className="tool-events">
                  {m.toolEvents.map((te, j) => {
                    const st = te.result === undefined ? 'pending' : toolResultStatus(te.result);
                    // 提取 args 中最具代表性的一个值作为摘要
                    const argSummary = (() => {
                      const a = te.args;
                      if (!a || !Object.keys(a).length) return '';
                      // 优先展示 query / to / subject / url / path
                      for (const k of ['query', 'to', 'url', 'subject', 'path', 'file_path']) {
                        if (a[k] != null) {
                          const v = String(a[k]);
                          return v.length > 36 ? v.slice(0, 34) + '…' : v;
                        }
                      }
                      const firstVal = Object.values(a)[0];
                      const v = String(firstVal ?? '');
                      return v.length > 36 ? v.slice(0, 34) + '…' : v;
                    })();
                    return (
                      <div key={j} className="tool-event">
                        <span className="tool-event-name">⚙ {te.name}</span>
                        {argSummary && (
                          <span className="tool-event-args"> {argSummary}</span>
                        )}
                        {st === 'pending' && <span className="tool-event-pending"> …</span>}
                        {st === 'ok'      && <span className="tool-event-ok"> ✓</span>}
                        {st === 'dry_run' && <span className="tool-event-dry"> ⚠ 模拟</span>}
                        {st === 'fail'    && <span className="tool-event-fail"> ✗</span>}
                      </div>
                    );
                  })}
                </div>
              )}
              {/* Typing cursor while streaming and no content yet */}
              {m.isStreaming && !m.body && !(m.toolEvents?.length) && (
                <span className="streaming-cursor">▋</span>
              )}
            </div>
            {m.skillLaunch && (
              <SkillRunBanner
                skillId={m.skillLaunch.skill}
                projectCode={m.skillLaunch.projectCode}
                scenarioRun={m.skillLaunch.scenarioRun}
                autoStart={true}
              />
            )}
            {m.skillRun && (
              <SkillRunBanner
                skillId={m.skillRun.skillId}
                autoStart={false}
              />
            )}
            {m.pendingApproval && (
              <ToolApprovalCard
                info={m.pendingApproval}
                onDecide={(id, ok) => void decideTool(id, ok)}
              />
            )}
            {m.choiceCard && !m.isStreaming && (
              <ChoiceCard
                data={m.choiceCard}
                onSelect={(value) => void sendText(value)}
              />
            )}
            {m.reasoning && (
              <div className="reasoning">
                {m.reasoning.map((s, j) => (
                  <div className="step" key={j}>
                    <span className="ix">{s.ix}.</span>
                    <span>{s.text}</span>
                  </div>
                ))}
              </div>
            )}
            {m.actions && (
              <div className="actions">
                {m.actions.map((a, j) => (
                  <button key={j} className={`a-btn${a.kind === 'primary' ? ' primary' : ''}`}>
                    <ActionIcon name={a.icon ?? ''} />{a.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* suggestion chips */}
      <div className="claw-suggests">
        {suggestsForPath.map((s, i) => (
          <button key={i} className="sug-chip" onClick={() => setDraft(s)}>
            <IcSparkle />{s}
          </button>
        ))}
      </div>

      {/* input */}
      <div className="claw-input-wrap">
        <div className="claw-input">
          <textarea
            placeholder="对当前页面提问 / 下指令 · 支持引用 #PoD #机房 #项目"
            value={draft}
            onChange={e => setDraft(e.target.value)}
            onKeyDown={handleKey}
            rows={2}
          />
          <div className="ci-foot">
            <div className="ci-tools">
              <button className="tool-btn" title="附文档"><IcAttach /></button>
              <button className="tool-btn" title="引用页面对象">@</button>
              <button className="tool-btn" title="筛选范围"><IcFilter /></button>
            </div>
            <button
              className="send-btn"
              onClick={() => { void sendMessage(); }}
              disabled={isStreaming || !draft.trim()}
            >
              <IcSend />{isStreaming ? '…' : '发送'} <span className="kbd">⌘↵</span>
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
}
