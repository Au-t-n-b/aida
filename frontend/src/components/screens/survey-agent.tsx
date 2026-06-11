/**
 * SkillAgentScreen · 通用作业界面（SDUI 驱动）— 双模式
 * ─────────────────────────────────────────────────────────
 * 后端 project(SkillState) → SduiDocument → SduiNodeView 渲染。
 *
 * 运行模式自动检测（无需手动配置）：
 *   有 ClawManager 登录态 → 容器模式：ClawManager 任务 API → payload.sdui
 *   无登录态              → 本地模式：直连 aida/agent :7401 SSE（开发/单机部署）
 *
 * 两种模式下 SduiNodeView / HITL / 文件上传的 UI 完全一致，零代码差异。
 */
import React, { useState, useCallback, useEffect, useRef, lazy, Suspense } from 'react';
import { SduiNodeView } from '@/components/sdui/SduiNodeView';
import { SduiRuntimeContext, type SduiRuntime } from '@/components/sdui/SduiContext';
import { HITL_HOLD_MS } from '@/components/sdui/hitlOptimistic';

// 懒加载：预览组件内含 xlsx/mammoth 动态 import，懒加载使其仅在「打开预览」时才被 Vite 转译，
// 避免未安装这两个库时（如 CI / 首次拉取）解析整棵模块图失败导致白屏。
const SduiPreviewModal = lazy(() =>
  import('@/components/sdui/SduiPreviewModal').then(m => ({ default: m.SduiPreviewModal })),
);
import { useSduiStream, startRun, resumeRun, uploadBatch } from '@/hooks/useSduiStream';
import { useClawTaskSdui } from '@/hooks/useClawTaskSdui';
import { useAidaSession } from '@/lib/aida-session';
import { startClawTask, resumeClawTask } from '@/lib/claw-manager-client';
import { useSkillRunStore, setSkillRun, updateSkillRun } from '@/lib/skillRunStore';
import { setSkillHitl, clearSkillHitl } from '@/lib/skillHitlStore';
import { Button } from '@/components/primitives';
import type { SduiAction, SduiDocument, SduiNode } from '@/lib/sdui';

export interface SkillAgentScreenProps {
  /** 后端 skill_id，决定 /agent/<skillId>/* 端点（如 zhgk / guihua）。 */
  skillId: string;
  /** 空状态标题（默认取模块名）。 */
  title?: string;
  /** 空状态副标题描述。 */
  description?: string;
}

// ── 空状态（尚未启动时的引导界面）────────────────────────────────────────────

/* 注入 Idle 动画（仅一次） */
(function injectIdleStyles() {
  if (typeof document === 'undefined') return;
  if (document.getElementById('skill-idle-styles')) return;
  const s = document.createElement('style');
  s.id = 'skill-idle-styles';
  s.textContent = `
    @keyframes skillEmblemBreathe {
      0%,100% { transform:scale(1);   box-shadow:0 4px 14px rgba(15,23,42,.06),0 0 0 0 rgba(53,81,216,.18); }
      50%      { transform:scale(1.05);box-shadow:0 12px 28px rgba(15,23,42,.10),0 0 0 14px rgba(53,81,216,0); }
    }
    @keyframes skillIdleFadeUp {
      from { opacity:0; transform:translateY(10px); }
      to   { opacity:1; transform:none; }
    }
    .skill-idle-root {
      height:100%; display:flex; flex-direction:column;
      align-items:center; justify-content:center;
      padding:32px 28px 36px;
      background:radial-gradient(ellipse at 50% 30%, var(--c-brand-soft) 0%, var(--c-bg-soft) 100%);
      overflow:auto; gap:0;
      animation:skillIdleFadeUp .45s cubic-bezier(.16,1,.3,1) both;
    }
    .skill-idle-emblem {
      width:72px; height:72px; border-radius:18px;
      background:var(--c-surface); border:1px solid var(--c-border);
      box-shadow:var(--shadow-md);
      display:grid; place-items:center;
      color:var(--c-brand); margin-bottom:22px;
      animation:skillEmblemBreathe 3.2s ease-in-out infinite;
      position:relative;
    }
    .skill-idle-emblem::before {
      content:''; position:absolute; inset:-1px; border-radius:19px; padding:1px;
      background:linear-gradient(135deg,color-mix(in srgb,var(--c-brand) 30%,transparent),transparent 55%);
      -webkit-mask:linear-gradient(#fff 0 0) content-box,linear-gradient(#fff 0 0);
      mask:linear-gradient(#fff 0 0) content-box,linear-gradient(#fff 0 0);
      -webkit-mask-composite:xor; mask-composite:exclude; pointer-events:none;
    }
    .skill-idle-title {
      font-size:19px; font-weight:660; color:var(--c-text);
      letter-spacing:-.02em; text-align:center; margin-bottom:7px;
    }
    .skill-idle-desc {
      font-size:12.5px; color:var(--c-text-muted); text-align:center;
      line-height:1.6; max-width:300px; margin-bottom:28px;
    }
    /* ── 横向步骤条 ── */
    .skill-idle-steps {
      display:flex; align-items:flex-start; width:100%; max-width:420px;
      margin-bottom:22px;
    }
    .skill-idle-step { display:flex; flex-direction:column; align-items:center; flex:1; min-width:0; }
    .skill-idle-step-row { display:flex; align-items:center; width:100%; }
    .skill-idle-dot {
      width:28px; height:28px; border-radius:50%; flex-shrink:0;
      background:var(--c-surface); border:1.5px solid var(--c-border-strong);
      display:flex; align-items:center; justify-content:center;
      font-size:11px; font-weight:700; color:var(--c-text-faint);
      transition:border-color .2s;
      box-shadow:var(--shadow-sm);
    }
    .skill-idle-conn { flex:1; height:1.5px; background:var(--c-border); }
    .skill-idle-step-label {
      font-size:10px; color:var(--c-text-muted); font-weight:500;
      margin-top:7px; text-align:center; white-space:nowrap;
      max-width:56px; overflow:hidden; text-overflow:ellipsis;
    }
    .skill-idle-step-sub {
      font-size:9.5px; color:var(--c-text-faint); margin-top:2px;
      text-align:center; max-width:60px; line-height:1.35;
      display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;
    }
    /* ── 文件提示 ── */
    .skill-idle-files {
      width:100%; max-width:420px; margin-bottom:24px;
      background:var(--c-surface); border:1px solid var(--c-border); border-radius:10px;
      padding:11px 14px; display:flex; gap:10px; align-items:flex-start;
      box-shadow:var(--shadow-sm);
    }
    .skill-idle-files-ic {
      font-size:14px; flex-shrink:0; margin-top:1px; opacity:.75;
    }
    .skill-idle-files-body { flex:1; min-width:0; }
    .skill-idle-files-title {
      font-size:11px; font-weight:650; color:var(--c-text-2); margin-bottom:5px;
    }
    .skill-idle-file-row {
      display:flex; align-items:center; gap:7px; padding:4px 0;
      border-top:1px solid var(--c-divider);
    }
    .skill-idle-file-row:first-of-type { border-top:none; padding-top:0; }
    .skill-idle-file-ext {
      font-size:9px; font-weight:700; letter-spacing:.03em;
      padding:1px 5px; border-radius:4px; flex-shrink:0;
      font-family:var(--font-mono);
    }
    .skill-idle-file-ext.xlsx { background:var(--c-success-soft); color:var(--c-success-text); }
    .skill-idle-file-ext.docx { background:var(--c-info-soft);    color:var(--c-info-text); }
    .skill-idle-file-ext.md   { background:var(--c-brand-soft);   color:var(--c-brand-text); }
    .skill-idle-file-name {
      font-size:10.5px; color:var(--c-text-2); font-family:var(--font-mono);
      white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
    }
    .skill-idle-file-tag {
      font-size:9px; color:var(--c-text-faint); margin-left:auto; flex-shrink:0;
    }
    /* ── 启动按钮 ── */
    .skill-idle-btn {
      width:100%; max-width:420px;
      padding:12px 0; border-radius:10px; border:none; cursor:pointer;
      font-size:14px; font-weight:650; letter-spacing:.01em;
      background:var(--c-brand); color:#fff; font-family:var(--font-sans);
      box-shadow:var(--shadow-sm);
      transition:background .14s,box-shadow .14s,transform .1s;
      display:flex; align-items:center; justify-content:center; gap:8px;
    }
    .skill-idle-btn:hover:not(:disabled) {
      background:var(--c-brand-hover);
      box-shadow:var(--shadow-md);
      transform:translateY(-1px);
    }
    .skill-idle-btn:active:not(:disabled) { transform:translateY(0); }
    .skill-idle-btn:disabled { opacity:.6; cursor:not-allowed; }
    .skill-idle-btn-icon {
      width:16px; height:16px; background:rgba(255,255,255,.25);
      border-radius:50%; display:flex; align-items:center; justify-content:center;
      font-size:8px; flex-shrink:0;
    }
  `;
  document.head.appendChild(s);
})();

const SKILL_META: Record<string, {
  steps: Array<{ key: string; name: string; sub: string }>;
  files: Array<{ name: string; ext: 'xlsx' | 'docx' | 'md'; optional?: boolean }>;
  icon: React.ReactNode;
}> = {
  zhgk: {
    icon: (
      <svg width={34} height={34} viewBox="0 0 34 34" fill="none">
        <rect x="6" y="4" width="16" height="20" rx="2" stroke="currentColor" strokeWidth="1.6" />
        <path d="M10 10h8M10 14h8M10 18h5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        <circle cx="24" cy="24" r="6" stroke="currentColor" strokeWidth="1.6" />
        <path d="M27.5 27.5L30 30" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    ),
    steps: [
      { key: 'intent_select',    name: '意图选择',   sub: '4 种工作流' },
      { key: 'determine_gen',    name: '代际识别',   sub: 'A2·A3·A5·制冷' },
      { key: 'wait_survey',      name: '现场工勘',   sub: '条目建表·上传' },
      { key: 'assess',           name: 'AI 五值评估', sub: '满足·不满足·…' },
      { key: 'report_gen_run',   name: '报告与分发', sub: '报告·审批·邮件' },
    ],
    files: [
      { name: 'BOQ.xlsx',                   ext: 'xlsx' },
      { name: '入场评估标准表.xlsx',         ext: 'xlsx' },
      { name: '新版项目工勘报告模板.docx',   ext: 'docx', optional: true },
    ],
  },
  guihua: {
    icon: (
      <svg width={34} height={34} viewBox="0 0 34 34" fill="none">
        <rect x="7" y="4" width="20" height="26" rx="2" stroke="currentColor" strokeWidth="1.6" />
        <path d="M11 9h12M11 14h12M11 19h12M11 24h7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        <circle cx="20" cy="24" r="1.4" fill="currentColor" />
      </svg>
    ),
    steps: [
      { key: 'adapt_build',  name: '设备适配',   sub: '型号·板卡匹配' },
      { key: 'data_confirm', name: '数据确认',   sub: '核对适配表' },
      { key: 'combo_create', name: '创建超节点', sub: '平铺 9 个 POD' },
      { key: 'cabinet_move', name: '机柜落位',   sub: '162 柜落位' },
      { key: 'handoff',      name: '移交安装',   sub: '交设备安装' },
    ],
    files: [
      { name: '建模仿真设备信息表.md', ext: 'md' },
    ],
  },
};

function IdleScreen({ skillId, title, description, onStart, loading }: {
  skillId: string; title: string; description: string; onStart: () => void; loading: boolean;
}) {
  const meta = SKILL_META[skillId];
  const steps = meta?.steps ?? [];
  const files = meta?.files ?? [];

  return (
    <div className="skill-idle-root">

      {/* ── 动画徽章 ── */}
      <div className="skill-idle-emblem">
        {meta?.icon ?? <span style={{ fontSize: 28 }}>⚙️</span>}
      </div>

      {/* ── 标题 ── */}
      <div className="skill-idle-title">{title}</div>
      <div className="skill-idle-desc">{description}</div>

      {/* ── 横向步骤条 ── */}
      {steps.length > 0 && (
        <div className="skill-idle-steps">
          {steps.map((s, i) => (
            <React.Fragment key={s.key}>
              <div className="skill-idle-step">
                <div className="skill-idle-step-row">
                  {i > 0 && <div className="skill-idle-conn" />}
                  <div className="skill-idle-dot">{i + 1}</div>
                  {i < steps.length - 1 && <div className="skill-idle-conn" />}
                </div>
                <div className="skill-idle-step-label">{s.name}</div>
                <div className="skill-idle-step-sub">{s.sub}</div>
              </div>
            </React.Fragment>
          ))}
        </div>
      )}

      {/* ── 所需文件 ── */}
      {files.length > 0 && (
        <div className="skill-idle-files">
          <div className="skill-idle-files-ic">📂</div>
          <div className="skill-idle-files-body">
            <div className="skill-idle-files-title">启动前确认文件 · ProjectData/Template/ · Input/</div>
            {files.map(f => (
              <div key={f.name} className="skill-idle-file-row">
                <span className={`skill-idle-file-ext ${f.ext}`}>{f.ext.toUpperCase()}</span>
                <span className="skill-idle-file-name">{f.name}</span>
                {f.optional && <span className="skill-idle-file-tag">可选</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── 启动按钮 ── */}
      <button
        type="button"
        className="skill-idle-btn"
        onClick={onStart}
        disabled={loading}
      >
        <span className="skill-idle-btn-icon">▶</span>
        {loading ? '启动中…' : `启动${title}`}
      </button>
    </div>
  );
}

// ── SDUI → skillRunStore 进度同步 ─────────────────────────────────────────────
// survey-agent.tsx 是唯一持有完整 SDUI 文档的组件，负责解析后写入 store。
// 左侧 SkillRunBanner 只读 store，不开第二个 EventSource。

/** 递归遍历 SDUI 节点树（仅下钻含 children 的容器节点）*/
function walkSduiNodes(node: SduiNode, visit: (n: SduiNode) => void): void {
  visit(node);
  const c = (node as { children?: SduiNode[] }).children;
  if (Array.isArray(c)) c.forEach(child => walkSduiNodes(child, visit));
}

/** 按 id 查找节点（用于定位 hitl-card）。*/
function findNodeById(root: SduiNode, id: string): SduiNode | null {
  let found: SduiNode | null = null;
  walkSduiNodes(root, (n) => {
    if (!found && (n as { id?: string }).id === id) found = n;
  });
  return found;
}

/** 移除 root 下的 hitl-card（交互卡已路由到左侧会话框，避免左右双份）。
 *  hitl-card 是 root Stack 的直接子节点（见 zhgk/sdui.py），浅层移除即可。
 *  右侧此刻由 P4「你的回合」接管态承载（见主渲染）。*/
function stripHitlCard(root: SduiNode): SduiNode {
  const children = (root as { children?: SduiNode[] }).children;
  if (!Array.isArray(children)) return root;
  const next = children.filter(c => (c as { id?: string }).id !== 'hitl-card');
  if (next.length === children.length) return root;
  return { ...root, children: next } as SduiNode;
}

/** P4 · 你的回合（HITL 接管态）：等待用户操作时，把「该你了」抬成主角，
 *  下方遥测整体退后降饱和。交互卡片在左侧会话框，这里是右侧的肯定式引导。*/
function HitlTakeover() {
  return (
    <div style={{
      border: '1px solid var(--c-warning)', borderRadius: 'var(--r-lg)',
      background: 'linear-gradient(180deg, var(--c-warning-soft) 0%, var(--c-surface) 64%)',
      boxShadow: 'var(--shadow-md)', overflow: 'hidden', marginBottom: 'var(--sp-4)',
      animation: 'sdui-node-in .3s cubic-bezier(.2,.65,.4,1) both',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px var(--sp-5) 0' }}>
        <span style={{
          width: 9, height: 9, borderRadius: '50%', background: 'var(--c-warning)',
          boxShadow: '0 0 0 4px var(--c-warning-soft)', flexShrink: 0,
        }} />
        <span style={{
          fontSize: 'var(--fs-11)', fontWeight: 700, letterSpacing: '.08em',
          textTransform: 'uppercase', color: 'var(--c-warning-text)',
        }}>你的回合 · 需要你的操作</span>
      </div>
      <div style={{ padding: '4px var(--sp-5) var(--sp-5)' }}>
        <div style={{ fontSize: 'var(--fs-16)', fontWeight: 600, letterSpacing: '-.01em', margin: '4px 0 6px' }}>
          ← 请在左侧会话框完成确认
        </div>
        <div style={{ fontSize: 'var(--fs-13)', color: 'var(--c-text-muted)' }}>
          下方运行面板已暂时退后。交互卡片就在左侧会话框，完成选择 / 上传后将自动继续。
        </div>
      </div>
    </div>
  );
}

/** 从 SDUI 文档提取运行阶段信息（供 updateSkillRun 写入）*/
function extractProgressFromSdui(doc: SduiDocument): {
  phase?: 'running' | 'hitl' | 'done' | 'error';
  progress?: number;
  currentStepName?: string;
  hitlType?: 'file' | 'choice' | null;
  errorMsg?: string;
} {
  const r: {
    phase?: 'running' | 'hitl' | 'done' | 'error';
    progress?: number;
    currentStepName?: string;
    hitlType?: 'file' | 'choice' | null;
    errorMsg?: string;
  } = {};

  walkSduiNodes(doc.root, (node) => {
    // DonutChart 中心值 → 整体进度百分比
    if (node.type === 'DonutChart' && node.centerValue) {
      const p = parseInt(node.centerValue);
      if (!isNaN(p)) r.progress = p;
    }
    // Stepper → 当前步骤名 + 阶段
    if (node.type === 'Stepper' && !r.phase) {
      const errStep  = node.steps.find(s => s.status === 'error');
      const runStep  = node.steps.find(s => s.status === 'running');
      const allDone  = node.steps.length > 0 && node.steps.every(s => s.status === 'done');
      if (errStep) {
        r.phase = 'error';
        r.errorMsg = `「${errStep.title}」执行失败`;
      } else if (allDone) {
        r.phase = 'done';
        r.progress = 100;
        r.currentStepName = '';
      } else if (runStep) {
        r.phase = 'running';
        r.currentStepName = runStep.title;
      }
    }
    // HITL 节点优先级最高（覆盖 Stepper 的阶段判断）
    if (node.type === 'ChoiceCard') { r.phase = 'hitl'; r.hitlType = 'choice'; }
    if (node.type === 'FilePicker') { r.phase = 'hitl'; r.hitlType = 'file';   }
  });

  return r;
}

// ── 主界面 ────────────────────────────────────────────────────────────────────

export default function SkillAgentScreen({
  skillId,
  title = '作业模块',
  description = 'AI 驱动的作业全流程',
}: SkillAgentScreenProps) {
  // ── 模式检测：有 ClawManager 登录态 → 容器模式 ────────────────────────────
  const { session } = useAidaSession();
  const useClawMode = !!session;

  // ── 状态（两种模式都需要）──────────────────────────────────────────────────
  const [taskId, setTaskId] = useState<string | null>(null);   // 容器模式
  const [runId, setRunId] = useState<string | null>(null);     // 本地模式
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // SSE 重订阅令牌：HITL resume 后自增，强制 useSduiStream 对准后端新建的队列（见 hook 注释）
  const [streamEpoch, setStreamEpoch] = useState(0);
  // 产物预览：open_preview action 触发，存待预览的相对路径（null = 关闭）
  const [previewPath, setPreviewPath] = useState<string | null>(null);

  // ── 左右同步：聊天侧 ZhgkProgressCard 启动 run 后自动接入（本地模式）────────
  // store 里有匹配的 skillId + runId 且本地尚未启动 → 直接接入，跳过 IdleScreen
  const storeRun = useSkillRunStore();
  useEffect(() => {
    if (useClawMode) return;               // 容器模式自有 taskId，不走 store
    if (runId) return;                     // 本地已有 run，无需覆盖
    if (storeRun?.skillId === skillId && storeRun.runId) {
      setRunId(storeRun.runId);
    }
  }, [storeRun, skillId, useClawMode, runId]);

  // ── SDUI 订阅（按模式选择数据源，另一侧传 null 不订阅）──────────────────
  const clawTask = useClawTaskSdui(useClawMode ? taskId : null, session?.accessToken ?? '');
  const directDoc = useSduiStream(skillId, useClawMode ? null : runId, streamEpoch);
  const sduiDoc = useClawMode ? clawTask.doc : directDoc;
  // 容器模式：用容器内 aida/agent 的 run_id 做文件上传（clawTask.runId 由 payload 携带）
  const activeRunId = useClawMode ? (clawTask.runId ?? null) : runId;

  // ── resume 冻结窗口：防止 full_restart 短暂闪回 0% 初始状态 ────────────────────
  // full_restart 模式下每次 resume 都新建一个 run 从 step-1 回放；后端立即推一条
  // steps=[] 的快照（0% 空白状态），前端会短暂闪回预检画面。
  // 解法：resume 发起时把当前 SDUI 快照冻结展示，等新流进度追上冻结水位
  // （或出现新 HITL 卡）时再解冻，切换回实时文档。
  // 整个修改限定在本组件内部，不触碰 useSduiStream / 后端 / 其他模块。
  const sduiDocRef = useRef<SduiDocument | null>(null);
  useEffect(() => { sduiDocRef.current = sduiDoc; }, [sduiDoc]);
  const [frozenDoc, setFrozenDoc] = useState<SduiDocument | null>(null);
  const frozenProgressRef = useRef(0);
  useEffect(() => {
    if (!frozenDoc || !sduiDoc) return;
    const { progress = 0 } = extractProgressFromSdui(sduiDoc);
    const hasHitl = !!findNodeById(sduiDoc.root, 'hitl-card');
    // 进度追上冻结水位 → 后端重放完毕；出现新 HITL → 流水线推进到下一交互门
    if (progress >= frozenProgressRef.current || hasHitl) setFrozenDoc(null);
  }, [sduiDoc, frozenDoc]);
  // resume 期间展示冻结快照，其余时间展示实时文档
  const displayDoc = frozenDoc ?? sduiDoc;

  // Sync SDUI doc → skillRunStore（左侧 SkillRunBanner 从 store 读取进度展示）
  useEffect(() => {
    if (!sduiDoc || !activeRunId) return;
    const patch = extractProgressFromSdui(sduiDoc);
    updateSkillRun(patch);
  }, [sduiDoc, activeRunId]);

  // ── 启动 ──────────────────────────────────────────────────────────────────
  const handleStart = useCallback(async () => {
    setStarting(true);
    setError(null);
    try {
      if (useClawMode && session) {
        const resp = await startClawTask({
          accessToken: session.accessToken,
          sessionId: session.sessionId,
          kind: skillId,
          params: {},
        });
        setTaskId(resp.task_id);
      } else {
        const id = await startRun(skillId);
        setRunId(id);
        // 通知聊天侧：source='ui' → ClawRail 检测到后自动注入 SkillRunBanner 消息
        setSkillRun(skillId, id, 'ui');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '启动失败');
    } finally {
      setStarting(false);
    }
  }, [skillId, useClawMode, session]);

  // ── resume（两种模式统一入口）────────────────────────────────────────────
  const doResume = useCallback(async (payload: Record<string, unknown>) => {
    if (useClawMode && session && taskId) {
      await resumeClawTask({
        accessToken: session.accessToken,
        sessionId: session.sessionId,
        taskId,
        payload,
      });
    } else if (activeRunId) {
      // 冻结当前 SDUI 快照，避免 full_restart 重放期间闪回 0% 预检状态
      const curDoc = sduiDocRef.current;
      if (curDoc) {
        frozenProgressRef.current = extractProgressFromSdui(curDoc).progress ?? 0;
        setFrozenDoc(curDoc);
      }
      await resumeRun(skillId, activeRunId, payload);
      // 立即给左侧 SkillRunBanner 反馈：HITL 已提交，恢复 running
      updateSkillRun({ phase: 'running', hitlType: null });
      // 强制重订阅 SSE：full_restart 会新建队列，旧 EventSource 追不上（见 useSduiStream epoch 注释）
      setStreamEpoch(e => e + 1);
    }
  }, [useClawMode, session, taskId, activeRunId, skillId]);

  // ── 动作处理 ──────────────────────────────────────────────────────────────
  const handleAction = useCallback(async (action: SduiAction) => {
    if (action.kind === 'post_user_message') {
      const text = action.text;
      if (text.startsWith('/start_') || text.startsWith('/retry_')) {
        await handleStart();
      } else if (text.startsWith('/resume_')) {
        await doResume({});
      } else if (text.startsWith('/view_')) {
        // TODO: 打开报告预览
      }
    } else if (action.kind === 'open_preview') {
      setPreviewPath(action.path);
    } else if (action.kind === 'reset_session') {
      // 「重置会话」：重启一条新 run（initial_project 会清运行态）
      await handleStart();
    }
  }, [handleStart, doResume]);

  const handleUpload = useCallback(async (files: FileList) => {
    const arr = Array.from(files);
    try {
      await uploadBatch(skillId, arr);
    } catch (e) {
      console.error('[SDUI] upload error:', e);
      throw e instanceof Error ? e : new Error('上传失败，请检查文件格式或网络连接');
    }
    // 上传已完成 → 立即 resolve（组件随即显示「已上传」确认态）；推进延后 HOLD，
    // 让确认态稳定可见一段时间，再触发 full_restart 重放。
    setTimeout(() => { void doResume({ uploaded: arr.map(f => f.name) }); }, HITL_HOLD_MS);
  }, [skillId, doResume]);

  const handleChoiceSubmit = useCallback(async (value: string) => {
    // 组件已显示「已提交」确认态 → 先 hold 再推进，保证确认态可见一段时间
    await new Promise(r => setTimeout(r, HITL_HOLD_MS));
    await doResume({ choice: value });
  }, [doResume]);

  // 可编辑 DataTable（计划下发勾选 / ESN 填写）提交：编辑后的行回传 /resume
  const handleRowsSubmit = useCallback(async (rows: Record<string, unknown>[]) => {
    await new Promise(r => setTimeout(r, HITL_HOLD_MS));
    await doResume({ rows });
  }, [doResume]);

  // ── HITL 提升到左侧会话框 ─────────────────────────────────────────────────
  // sduiDoc 出现 hitl-card → 连同 resume 回调写入 skillHitlStore；
  // 左侧 SkillRunBanner 据此渲染可交互卡。无 HITL / 卸载时清除。
  useEffect(() => {
    if (!sduiDoc || !activeRunId) { clearSkillHitl(skillId); return; }
    const card = findNodeById(sduiDoc.root, 'hitl-card');
    if (card) {
      setSkillHitl({
        skillId, runId: activeRunId, node: card,
        onChoiceSubmit: handleChoiceSubmit, onUpload: handleUpload,
      });
    } else {
      clearSkillHitl(skillId);
    }
  }, [sduiDoc, activeRunId, skillId, handleChoiceSubmit, handleUpload]);

  useEffect(() => () => clearSkillHitl(skillId), [skillId]);  // 卸载清理

  // ── SDUI 运行时 ──────────────────────────────────────────────────────────
  const runtime: SduiRuntime = {
    runId: activeRunId,
    onAction: (action) => { void handleAction(action); },
    onUpload: (files) => { void handleUpload(files); },
    onChoiceSubmit: (value) => { void handleChoiceSubmit(value); },
    onRowsSubmit: (rows) => { void handleRowsSubmit(rows); },
  };

  // ── 渲染 ────────────────────────────────────────────────────────────────
  const isIdle = useClawMode ? !taskId : !runId;
  if (isIdle && !starting) {
    return (
      <div style={{ height: '100%', overflow: 'auto' }}>
        <IdleScreen skillId={skillId} title={title} description={description} onStart={() => { void handleStart(); }} loading={starting} />
        {error && (
          <div style={{ margin: '0 auto', maxWidth: 320, padding: 12, background: 'var(--c-danger-soft)', borderRadius: 'var(--r-md)', color: 'var(--c-danger-text)', fontSize: 'var(--fs-13)', textAlign: 'center' }}>
            {error}
          </div>
        )}
      </div>
    );
  }

  // P4：待用户操作时（root 含 hitl-card），右侧进入「你的回合」接管态
  const hasHitl = !!(displayDoc && findNodeById(displayDoc.root, 'hitl-card'));

  return (
    <SduiRuntimeContext.Provider value={runtime}>
      <div style={{ height: '100%', overflow: 'auto', padding: 'var(--pad-panel)' }}>
        {displayDoc ? (
          hasHitl ? (
            /* P4 接管态：「你的回合」抬为主角 + 下方遥测退后降饱和（交互卡在左侧会话框）*/
            <>
              <HitlTakeover />
              <div style={{ filter: 'saturate(.5) opacity(.62)', pointerEvents: 'none', transition: 'filter .35s' }}>
                <SduiNodeView node={stripHitlCard(displayDoc.root)} />
              </div>
            </>
          ) : (
            <SduiNodeView node={displayDoc.root} />
          )
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {/* 骨架屏：正在连接 SSE / 等待第一个 sdui 事件 */}
            <div style={{ height: 52, borderRadius: 'var(--radius-lg)', background: 'var(--zinc-100)' }} />
            <div style={{ height: 80, borderRadius: 'var(--radius-lg)', background: 'var(--zinc-100)' }} />
            <div style={{ height: 120, borderRadius: 'var(--radius-lg)', background: 'var(--zinc-100)' }} />
          </div>
        )}
      </div>
      {/* 产物/上传文件在线预览（xlsx/docx/pdf/图片）· 懒加载，仅打开时才拉取组件+库 */}
      {previewPath && (
        <Suspense fallback={null}>
          <SduiPreviewModal skillId={skillId} path={previewPath} onClose={() => setPreviewPath(null)} />
        </Suspense>
      )}
    </SduiRuntimeContext.Provider>
  );
}
