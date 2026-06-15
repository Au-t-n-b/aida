/**
 * SkillAgentScreen · 通用作业界面（SDUI 驱动）— 双模式
 * ─────────────────────────────────────────────────────────
 * 后端 project(SkillState) → SduiDocument → SduiNodeView 渲染。
 *
 * 运行模式自动检测（无需手动配置）：
 *   登录且 session.containerEndpoint 存在 → 容器模式：ClawManager 任务 API → payload.sdui
 *   否则（含本地已登录无容器）         → 直连模式：aida/agent :7401 SSE
 *
 * 两种模式下 SduiNodeView / HITL / 文件上传的 UI 完全一致，零代码差异。
 */
import React, { useState, useCallback, useEffect, useRef, lazy, Suspense } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { SduiNodeView } from '@/components/sdui/SduiNodeView';
import { SduiRuntimeContext, type SduiRuntime } from '@/components/sdui/SduiContext';

// 懒加载：预览组件内含 xlsx/mammoth 动态 import，懒加载使其仅在「打开预览」时才被 Vite 转译，
// 避免未安装这两个库时（如 CI / 首次拉取）解析整棵模块图失败导致白屏。
const SduiPreviewModal = lazy(() =>
  import('@/components/sdui/SduiPreviewModal').then(m => ({ default: m.SduiPreviewModal })),
);
import {
  useSduiStream,
  startRun,
  resumeRun,
  uploadBatch,
  overrideOutputArtifact,
  runPatchRun,
  resetWorkspace,
  isIdleLikeSduiDoc,
  isRunUnavailableDoc,
  fetchUiSnapshot,
  fetchRunStatus,
  runStepOutcome,
  AGENT_BASE,
  type StartReq,
} from '@/hooks/useSduiStream';
import { clearRunLog } from '@/lib/runLogStore';
import type { CommissionIntent } from '@/lib/commissionCommands';
import {
  commissionStepLabel,
  emitCommissionProgress,
  formatCommissionScope,
  isCommissionStepSettledInDoc,
  readCommissionKpi,
  readReportArtifactPath,
} from '@/lib/commissionCommands';
import type { CommissionExecuting } from '@/components/sdui/SduiContext';
import { persistSkillRunId, readSkillRunId, clearPersistedSkillRun } from '@/lib/skillRunPersist';
import { useClawTaskSdui } from '@/hooks/useClawTaskSdui';
import { useAidaSession } from '@/lib/aida-session';
import { startClawTask, resumeClawTask } from '@/lib/claw-manager-client';
import { useSkillRunStore, setSkillRun, updateSkillRun, clearSkillRun } from '@/lib/skillRunStore';
import { setSkillHitl, clearSkillHitl, getSkillHitl } from '@/lib/skillHitlStore';
import { dispatchRailSend } from '@/lib/claw-send';
// system_design 交付台专用（仅 skillId==='system_design' 路径使用）
import { resolveUploadSlotTag } from '@/lib/systemDesignUpload';
import { ensureAgentBase, staleSystemDesignUploadMessage } from '@/lib/agentBase';
import { setSkillConversation, clearSkillConversation } from '@/lib/skillConversationStore';
import { Button } from '@/components/primitives';
import type { SduiAction, SduiDocument, SduiNode } from '@/lib/sdui';

/** 与后端 delivery.is_lld_delivery_intent 对齐 */
function isLldDeliveryIntent(text: string): boolean {
  const t = text.trim().replace(/\s/g, '');
  if (!t) return false;
  if (t === '生成完整LLD设计' || t === '融合完整LLD设计') return true;
  return (/完整/i.test(t) && /LLD/i.test(t)) || (/生成/.test(t) && /LLD/i.test(t));
}

/** LLD 融合续跑：显式 from_step 避免 hitl 快照丢失时 route_to 未命中（仅 system_design 交付台） */
function resolveDeliveryResumeFromStep(text: string): string | undefined {
  const t = text.trim();
  if (isLldDeliveryIntent(text)) return 'plane_planning';
  if ([
    'confirm', '确认发布', '确认',
    'request_test_check', '检查测试用例',
    'check', 'confirm_test_check', '已检查测试用例',
  ].includes(t)) {
    return 'publish_confirm';
  }
  return undefined;
}

/**
 * ChoiceCard / IoConfirm 提交时的 from_step。
 * - system_design：优先 SDUI stepId；无 stepId 时走 NL 专用映射（LLD / publish_confirm 等）。
 * - guihua / zhgk / device_install / software_deployment：仅传 stepId，否则省略 from_step 由后端读 hitl.step。
 *   禁止把通用 value「confirm」映射成 publish_confirm，否则会破坏 guihua 等确认门。
 */
function resolveChoiceResumeFromStep(
  skillId: string,
  value: string,
  stepId?: string,
): string | undefined {
  const sid = stepId?.trim();
  if (skillId === 'system_design') {
    if (sid) return sid;
    return resolveDeliveryResumeFromStep(value);
  }
  return sid || undefined;
}

/** MacroStepRail「发布完成」(bp_publish) 是否已 done */
function isMacroPublishDone(doc: SduiDocument): boolean {
  let done = false;
  walkSduiNodes(doc.root, (node) => {
    if (node.type !== 'MacroStepRail') return;
    const st = (node.steps ?? []).find(s => s.id === 'bp_publish');
    if (st?.status === 'done') done = true;
  });
  return done;
}

function resolveSkillRunId(
  skillId: string,
  activeRunId: string | null,
  storeRun: { skillId: string; runId: string | null } | null,
): string | null {
  if (activeRunId) return activeRunId;
  const fromStore = storeRun?.skillId === skillId ? storeRun.runId : null;
  if (fromStore && fromStore !== '__starting__') return fromStore;
  const hitl = getSkillHitl();
  if (hitl?.skillId === skillId && hitl.runId) return hitl.runId;
  return null;
}

export interface SkillAgentScreenProps {
  /** 后端 skill_id，决定 /agent/<skillId>/* 端点（如 zhgk / guihua）。 */
  skillId: string;
  /** 空状态标题（默认取模块名）。 */
  title?: string;
  /** 空状态副标题描述。 */
  description?: string;
  /** 模块衔接：完成后可一键进入下一模块（如建模仿真 → 进入系统设计并 autostart）。 */
  nextModule?: { label: string; to: string };
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
      background:radial-gradient(ellipse at 50% 30%, #f0f4fd 0%, #e8edf6 100%);
      overflow:auto; gap:0;
      animation:skillIdleFadeUp .45s cubic-bezier(.16,1,.3,1) both;
    }
    .skill-idle-emblem {
      width:72px; height:72px; border-radius:18px;
      background:#fff; border:1px solid #dde3ef;
      box-shadow:0 4px 14px rgba(15,23,42,.06);
      display:grid; place-items:center;
      color:#3551d8; margin-bottom:22px;
      animation:skillEmblemBreathe 3.2s ease-in-out infinite;
      position:relative;
    }
    .skill-idle-emblem::before {
      content:''; position:absolute; inset:-1px; border-radius:19px; padding:1px;
      background:linear-gradient(135deg,rgba(53,81,216,.3),transparent 55%);
      -webkit-mask:linear-gradient(#fff 0 0) content-box,linear-gradient(#fff 0 0);
      mask:linear-gradient(#fff 0 0) content-box,linear-gradient(#fff 0 0);
      -webkit-mask-composite:xor; mask-composite:exclude; pointer-events:none;
    }
    .skill-idle-title {
      font-size:19px; font-weight:660; color:#0f172a;
      letter-spacing:-.02em; text-align:center; margin-bottom:7px;
    }
    .skill-idle-desc {
      font-size:12.5px; color:#64748b; text-align:center;
      line-height:1.6; max-width:300px; margin-bottom:28px;
    }
    /* ── 横向步骤条（网格：圆点与标题同列居中） ── */
    .skill-idle-steps {
      display:grid;
      width:100%; max-width:420px;
      margin-bottom:22px;
      position:relative;
      gap:0;
    }
    .skill-idle-track {
      position:absolute;
      top:14px;
      left:calc(50% / var(--step-count, 5));
      right:calc(50% / var(--step-count, 5));
      height:1.5px;
      background:#dde3ef;
      z-index:0;
      pointer-events:none;
    }
    .skill-idle-step {
      display:flex; flex-direction:column; align-items:center;
      position:relative; z-index:1; min-width:0;
    }
    .skill-idle-dot {
      width:28px; height:28px; border-radius:50%; flex-shrink:0;
      background:#fff; border:1.5px solid #c8d1e6;
      display:flex; align-items:center; justify-content:center;
      font-size:11px; font-weight:700; color:#94a3b8;
      transition:border-color .2s;
      box-shadow:0 1px 3px rgba(15,23,42,.06);
    }
    .skill-idle-step-label {
      width:100%;
      font-size:10px; color:#64748b; font-weight:500;
      margin-top:7px; text-align:center;
      line-height:1.35;
      padding:0 2px;
    }
    .skill-idle-step-sub {
      width:100%;
      font-size:9.5px; color:#94a3b8; margin-top:2px;
      text-align:center; line-height:1.35;
      padding:0 2px;
    }
    .skill-idle-root[data-wide] .skill-idle-steps,
    .skill-idle-root[data-wide] .skill-idle-files,
    .skill-idle-root[data-wide] .skill-idle-btn {
      max-width:640px;
    }
    .skill-idle-root[data-wide] .skill-idle-step-label {
      font-size:10px;
    }
    .skill-idle-root[data-wide] .skill-idle-step-sub {
      font-size:9.5px;
    }
    /* ── 文件提示 ── */
    .skill-idle-files {
      width:100%; max-width:420px; margin-bottom:24px;
      background:#fff; border:1px solid #dde3ef; border-radius:10px;
      padding:11px 14px; display:flex; gap:10px; align-items:flex-start;
      box-shadow:0 1px 3px rgba(15,23,42,.04);
    }
    .skill-idle-files-ic {
      font-size:14px; flex-shrink:0; margin-top:1px; opacity:.75;
    }
    .skill-idle-files-body { flex:1; min-width:0; }
    .skill-idle-files-title {
      font-size:11px; font-weight:650; color:#334155; margin-bottom:5px;
    }
    .skill-idle-file-row {
      display:flex; align-items:center; gap:7px; padding:4px 0;
      border-top:1px solid #f0f4fa;
    }
    .skill-idle-file-row:first-of-type { border-top:none; padding-top:0; }
    .skill-idle-file-ext {
      font-size:9px; font-weight:700; letter-spacing:.03em;
      padding:1px 5px; border-radius:4px; flex-shrink:0;
      font-family:var(--font-mono);
    }
    .skill-idle-file-ext.xlsx { background:#e6f4ea; color:#0a7d46; }
    .skill-idle-file-ext.docx { background:#e8effc; color:#1747b8; }
    .skill-idle-file-name {
      font-size:10.5px; color:#475569; font-family:var(--font-mono);
      white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
    }
    .skill-idle-file-tag {
      font-size:9px; color:#94a3b8; margin-left:auto; flex-shrink:0;
    }
    /* ── 启动按钮 ── */
    .skill-idle-btn {
      width:100%; max-width:420px;
      padding:12px 0; border-radius:10px; border:none; cursor:pointer;
      font-size:14px; font-weight:650; letter-spacing:.01em;
      background:#3551d8; color:#fff; font-family:var(--font-sans);
      box-shadow:0 1px 2px rgba(53,81,216,.25),0 4px 14px rgba(53,81,216,.14);
      transition:background .14s,box-shadow .14s,transform .1s;
      display:flex; align-items:center; justify-content:center; gap:8px;
    }
    .skill-idle-btn:hover:not(:disabled) {
      background:#2a44c2;
      box-shadow:0 2px 4px rgba(53,81,216,.3),0 8px 20px rgba(53,81,216,.18);
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
  filesHint?: string;
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
  device_install: {
    icon: (
      <svg width={34} height={34} viewBox="0 0 34 34" fill="none">
        <rect x="7" y="5" width="18" height="22" rx="2.5" stroke="currentColor" strokeWidth="1.6" />
        <path d="M12 11h10M12 15h10M12 19h6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        <circle cx="23" cy="11" r="5" stroke="currentColor" strokeWidth="1.5" />
        <path d="M23 9v4M21 11h4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
    ),
    steps: [
      { key: 'preflight',      name: '环境预检',     sub: '校验输入文件' },
      { key: 'principal_fill', name: '生成责任矩阵', sub: '在线编辑信息' },
      { key: 'tasks_generate', name: '生成实施计划', sub: '在线编辑计划' },
      { key: 'task_dispatch',  name: '计划下发',     sub: '勾选计划下发' },
      { key: 'sn_generate',    name: 'SN扫码表',     sub: '按单元生成' },
      { key: 'esn_fill',       name: 'ESN填写',      sub: '完工清单' },
    ],
    files: [
      { name: '交付计划表.xlsx', ext: 'xlsx' },
      { name: '{批次}_{机房}_{设备型号}到货表_{日期}.xlsx', ext: 'xlsx' },
      { name: '建模仿真输出文档004-设备位置表.xlsx', ext: 'xlsx' },
    ],
    filesHint: '启动前确认文件 · ProjectData/Input/',
  },
};

function IdleScreen({ skillId, title, description, onStart, onCommissionStart, loading }: {
  skillId: string; title: string; description: string;
  onStart: () => void;
  onCommissionStart?: () => void;
  loading: boolean;
}) {
  const meta = SKILL_META[skillId];
  const steps = meta?.steps ?? [];
  const files = meta?.files ?? [];
  const filesHint = meta?.filesHint ?? '启动前确认文件 · ProjectData/Template/ · Input/';
  const isWide = steps.length >= 6;

  return (
    <div className="skill-idle-root" {...(isWide ? { 'data-wide': '' } : {})}>

      {/* ── 动画徽章 ── */}
      <div className="skill-idle-emblem">
        {meta?.icon ?? <span style={{ fontSize: 28 }}>⚙️</span>}
      </div>

      {/* ── 标题 ── */}
      <div className="skill-idle-title">{title}</div>
      <div className="skill-idle-desc">{description}</div>

      {/* ── 横向步骤条 ── */}
      {steps.length > 0 && (
        <div
          className="skill-idle-steps"
          style={{
            gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))`,
            ['--step-count' as string]: String(steps.length),
          }}
        >
          <div className="skill-idle-track" aria-hidden="true" />
          {steps.map((s, i) => (
            <div key={s.key} className="skill-idle-step">
              <div className="skill-idle-dot">{i + 1}</div>
              <div className="skill-idle-step-label">{s.name}</div>
              <div className="skill-idle-step-sub">{s.sub}</div>
            </div>
          ))}
        </div>
      )}

      {/* ── 所需文件 ── */}
      {files.length > 0 && (
        <div className="skill-idle-files">
          <div className="skill-idle-files-ic">📂</div>
          <div className="skill-idle-files-body">
            <div className="skill-idle-files-title">{filesHint}</div>
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
      {onCommissionStart && (
        <button
          type="button"
          className="skill-idle-btn"
          style={{ marginTop: 10, background: '#0f766e', boxShadow: '0 1px 2px rgba(15,118,110,.25),0 4px 14px rgba(15,118,110,.14)' }}
          onClick={onCommissionStart}
          disabled={loading}
        >
          <span className="skill-idle-btn-icon">⚡</span>
          {loading ? '进入中…' : '前置已满足 · 直接进入命令调测'}
        </button>
      )}
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

/** 统计 SDUI 中 InputSlotList 已就绪槽位数（上传后对比 SSE 是否追上）。 */
function countReadyInputSlots(doc: SduiDocument | null): number {
  if (!doc?.root) return 0;
  let n = 0;
  walkSduiNodes(doc.root, (node) => {
    if (node.type !== 'InputSlotList') return;
    for (const s of node.slots ?? []) {
      if (s.ready) n++;
    }
  });
  return n;
}

/** 统计 ArtifactGrid 产物数（判断 output/ 扫描是否已反映到 UI）。 */
function countOutputArtifacts(doc: SduiDocument | null): number {
  if (!doc?.root) return 0;
  let n = 0;
  walkSduiNodes(doc.root, (node) => {
    if (node.type === 'ArtifactGrid') n += (node.artifacts ?? []).length;
  });
  return n;
}

/** 按 id 查找节点（用于定位 hitl-card）。*/
function findNodeById(root: SduiNode, id: string): SduiNode | null {
  let found: SduiNode | null = null;
  walkSduiNodes(root, (n) => {
    if (!found && (n as { id?: string }).id === id) found = n;
  });
  return found;
}

/** need_edit 在线编辑 HITL 的 step key（如 tasks_generate / task_dispatch）。*/
function findEditableHitlStepKey(doc: SduiDocument | null): string | null {
  if (!doc) return null;
  let key: string | null = null;
  walkSduiNodes(doc.root, (node) => {
    if (key) return;
    if (node.type !== 'DataTable' || !(node as { editable?: boolean }).editable) return;
    const stepId = (node as { stepId?: string }).stepId;
    if (stepId) {
      key = stepId;
      return;
    }
    const id = (node as { id?: string }).id ?? '';
    if (id.startsWith('edit-')) key = id.slice(5);
  });
  return key;
}

/** Stepper 已完成步数（设备安装主建设流水线推进检测）。*/
function stepperDoneCount(doc: SduiDocument | null): number {
  if (!doc) return 0;
  let best = 0;
  walkSduiNodes(doc.root, (node) => {
    if (node.type === 'Stepper' && Array.isArray(node.steps)) {
      const n = node.steps.filter(s => s.status === 'done').length;
      if (n > best) best = n;
    }
  });
  return best;
}

/** 从 Stepper 提取步骤 id 顺序（与后端 DI_STEP_ORDER 一致）。*/
function getStepperStepIds(doc: SduiDocument | null): string[] {
  if (!doc) return [];
  let ids: string[] = [];
  walkSduiNodes(doc.root, (node) => {
    if (node.type === 'Stepper' && Array.isArray(node.steps) && node.steps.length > ids.length) {
      ids = node.steps.map(s => s.id);
    }
  });
  return ids;
}

function stepOrderIndex(order: string[], key: string | null): number {
  if (!key) return -1;
  return order.indexOf(key);
}

/** 设备安装完工态（ESN 提交后任务进展 / 完成横幅）。*/
function hasDiCompletionSurface(doc: SduiDocument): boolean {
  let found = false;
  walkSduiNodes(doc.root, (node) => {
    const id = (node as { id?: string }).id ?? '';
    if (id === 'di-completion-alert' || id === 'task-table-dt') found = true;
  });
  return found;
}

/** 冻结基准 vs 最新快照：仅前向推进才解冻（拒绝 full_restart 重放中间态）。*/
function hasWorkbenchAdvanced(frozen: SduiDocument, live: SduiDocument): boolean {
  if (isIdleLikeSduiDoc(live)) return false;

  const frozenDone = stepperDoneCount(frozen);
  const liveDone = stepperDoneCount(live);
  // full_restart 重放时步骤条 done 数会短暂回落，不算推进
  if (liveDone < frozenDone) return false;

  const order = getStepperStepIds(frozen).length ? getStepperStepIds(frozen) : getStepperStepIds(live);
  const frozenEdit = findEditableHitlStepKey(frozen);
  const liveEdit = findEditableHitlStepKey(live);

  // 在线编辑完成：编辑区消失 + 步骤条未回退（或出现完工视图）
  if (frozenEdit && !liveEdit) {
    return liveDone > frozenDone || hasDiCompletionSurface(live);
  }

  // 在线编辑步切换：仅接受流水线前向（如 tasks_generate → task_dispatch）
  if (frozenEdit && liveEdit && liveEdit !== frozenEdit) {
    const fi = stepOrderIndex(order, frozenEdit);
    const li = stepOrderIndex(order, liveEdit);
    return fi >= 0 && li > fi;
  }

  if (liveDone > frozenDone) return true;
  if (hasDiCompletionSurface(live) && frozenEdit) return true;
  return false;
}

/** 设备安装 · HITL 提交后的过渡视图（仅 device_install）。
 *  提交「保存并继续 / 确认并生成」后、后端 full_restart 重放尚未推进到下一步时，
 *  剥离编辑表 / HITL 卡，保留步骤条并把当前 HITL 步置为 running（黄色转圈），
 *  避免界面与步骤条停留在「待填表」假象（看起来像卡死）。
 *  meta.phase=running 让 extractProgressFromSdui 直接判定为运行态。 */
function buildDiSubmittingDoc(frozen: SduiDocument, stepKey: string | null): SduiDocument {
  const transform = (node: SduiNode): SduiNode | null => {
    const id = (node as { id?: string }).id ?? '';
    if (id === 'hitl-card' || id.startsWith('edit-card-')) return null;
    let next = node;
    if (node.type === 'Stepper' && Array.isArray((node as { steps?: unknown[] }).steps)) {
      const steps = (node as unknown as { steps: { id: string; status: string }[] }).steps.map((s) =>
        stepKey && s.id === stepKey && s.status !== 'done' ? { ...s, status: 'running' } : s,
      );
      next = { ...next, steps } as SduiNode;
    }
    const children = (next as { children?: SduiNode[] }).children;
    if (Array.isArray(children)) {
      const mapped = children.map(transform).filter((c): c is SduiNode => c != null);
      next = { ...next, children: mapped } as SduiNode;
    }
    return next;
  };
  const root = transform(frozen.root) ?? frozen.root;
  return { ...frozen, root, meta: { ...(frozen.meta ?? {}), phase: 'running' } };
}

/** HITL 已移到左侧会话框后，右侧用这张只读指引卡占位。*/
const HITL_POINTER: SduiNode = {
  type: 'Alert', id: 'hitl-pointer', tone: 'warning',
  title: '需要你确认',
  message: '交互卡片已移至左侧会话框，请在左侧完成选择 / 上传后继续。',
} as SduiNode;

/** 把 root 下的 hitl-card 替换为只读指引（交互卡渲染到左侧会话，避免左右双份）。
 *  hitl-card 是 root Stack 的直接子节点（见 zhgk/sdui.py），浅层替换即可。
 *  editToChat=true（meta.route_hitl_edit === 'chat'）时连 hitl-edit-card 一并移交；
 *  默认 false：在线编辑 HITL 留在右侧作业大盘（route_hitl_edit 契约 · SDUI.md §HITL-Edit）。*/
function routeHitlToChat(root: SduiNode, editToChat = false): SduiNode {
  const children = (root as { children?: SduiNode[] }).children;
  if (!Array.isArray(children)) return root;
  let changed = false;
  const next = children.map(c => {
    const id = (c as { id?: string }).id;
    if (id === 'hitl-card') { changed = true; return HITL_POINTER; }
    if (editToChat && id === 'hitl-edit-card') {
      changed = true;
      return { ...HITL_POINTER, id: 'hitl-edit-pointer' } as SduiNode;
    }
    return c;
  });
  return changed ? ({ ...root, children: next } as SduiNode) : root;
}

/** 工作台布局策略注册表（meta.workbench_class → 容器样式覆盖）。
 *  如设备安装 'di'：密排布局（顶部横向 Stepper + 全宽表格，压缩容器留白）。
 *  未注册的 class 走默认布局；新增 class 在此登记，不要散落条件分支。*/
const WORKBENCH_LAYOUTS: Record<string, React.CSSProperties> = {
  di: { padding: 'var(--sp-3, 12px)' },
};

/** SDUI 是否处于「左侧会话框 HITL」态（root 含 hitl-card）。*/
function hasLeftRailHitl(doc: SduiDocument): boolean {
  return !!findNodeById(doc.root, 'hitl-card');
}

/** 移除 root 下的 hitl-card（交互卡已路由到左侧会话框，避免左右双份）。
 *  hitl-card 是 root Stack 的直接子节点（见各 skill/sdui.py），浅层移除即可；
 *  右侧仅剥 hitl-card，其余 SDUI 正常渲染；交互在左侧 ClawRail。*/
function stripHitlCard(root: SduiNode): SduiNode {
  const children = (root as { children?: SduiNode[] }).children;
  if (!Array.isArray(children)) return root;
  const next = children.filter(c => (c as { id?: string }).id !== 'hitl-card');
  if (next.length === children.length) return root;
  return { ...root, children: next } as SduiNode;
}

/** guihua：从 root Stack 剥离应路由到左侧 ClawRail 的卡（hitl-card / completion-card），
 *  右侧只保留仿真工作台，避免左右双份。均为 root Stack 的直接子节点（见 guihua/sdui.py），浅层移除即可。*/
const SIDE_ROUTED_CARD_IDS = new Set(['hitl-card', 'completion-card']);
function stripSideRoutedCards(root: SduiNode): SduiNode {
  const children = (root as { children?: SduiNode[] }).children;
  if (!Array.isArray(children)) return root;
  const next = children.filter(c => !SIDE_ROUTED_CARD_IDS.has((c as { id?: string }).id ?? ''));
  if (next.length === children.length) return root;
  return { ...root, children: next } as SduiNode;
}

/** SDUI 根节点是否含 3D 机房总览块（决定是否启用 overview ↔ work 两态）。*/
function hasMachineRoom3d(root: SduiNode): boolean {
  const children = (root as { children?: SduiNode[] }).children;
  return Array.isArray(children) && children.some(c => (c as { id?: string }).id === 'machine-room-3d');
}

/** 两态导航（总览 ↔ 作业）：按 viewMode 隐藏 root 顶层互斥块，根治滚动过载。
 *  overview 态：3D 总览；work 态：作业区 + room-contextbar。
 *  有 3D 驾驶舱时去掉 header，避免与智算 Q3 顶栏重复。
 *  若机房总览不存在（如某些 run）则不切换。*/
function applyViewMode(root: SduiNode, mode: 'overview' | 'work'): SduiNode {
  const children = (root as { children?: SduiNode[] }).children;
  if (!Array.isArray(children)) return root;
  if (!hasMachineRoom3d(root)) return root;   // 无总览块 → 不做两态裁剪，原样渲染
  const hide = mode === 'overview'
    ? new Set(['header', 'dashboard-row', 'room-contextbar'])
    : new Set(['header', 'machine-room-3d']);
  const next = children.filter(c => !hide.has((c as { id?: string }).id ?? ''));
  return { ...root, children: next } as SduiNode;
}

// ── system_design 交付台专用（仅 skillId==='system_design' 走这些）────────────────
/** 使用「左栏会话 + 右栏面板」交付台布局的 skill（系统设计完整交付流）。 */
const DELIVERY_WORKBENCH_SKILLS = new Set(['system_design']);

function conversationHasDangerBubble(conv: SduiNode): boolean {
  let found = false;
  walkSduiNodes(conv, (n) => {
    if (n.type !== 'Card') return;
    const id = (n as { id?: string }).id;
    const tone = (n as { tone?: string }).tone;
    if (id === 'cv-bubble-error' || (id === 'cv-bubble' && tone === 'danger') || tone === 'danger') {
      found = true;
    }
  });
  return found;
}

/** step_retry 完成后左栏应出现「输入件检查完成」气泡（id=cv-input-done）。 */
function sduiHasInputCheckDone(doc: SduiDocument): boolean {
  const conv = findNodeById(doc.root, 'sd-conversation');
  if (!conv) return false;
  let found = false;
  walkSduiNodes(conv, (n) => {
    if ((n as { id?: string }).id === 'cv-input-done') found = true;
  });
  return found;
}

function isSoftSkipError(raw: string): boolean {
  const s = String(raw || '').trim();
  if (!s) return false;
  if (s.includes('007 缺少对应 sheet')) return true;
  if (s.includes('007 中无') && s.includes('跳过')) return true;
  if (s.includes('已跳过') && (s.includes('007') || s.toLowerCase().includes('sheet'))) return true;
  return false;
}

function sanitizeErrorText(raw: string): string {
  const lines = raw.split('\n').filter((line) => {
    const l = line.toLowerCase();
    return !(l.includes('userwarning') || l.includes('openpyxl') || l.includes('stylesheet.py'));
  });
  return (lines.join('\n').trim() || raw.trim());
}

function ensureConversationErrorBubble(conv: SduiNode, doc: SduiDocument): SduiNode {
  const err = sanitizeErrorText(String(doc.meta?.error ?? '').trim());
  if (!err || isSoftSkipError(err) || conversationHasDangerBubble(conv)) return conv;
  const logHint = String(doc.meta?.exec_log_path ?? '').trim();
  let body = err;
  if (logHint && !body.includes(logHint)) body += `\n\n详细日志：${logHint}`;
  const bubble: SduiNode = {
    type: 'Card',
    id: 'cv-bubble-error',
    density: 'compact',
    tone: 'danger',
    children: [
      { type: 'Text', content: '执行失败', variant: 'heading' },
      { type: 'Text', content: body, variant: 'body' },
    ],
  } as SduiNode;
  if (conv.type !== 'Stack') return conv;
  const children = [...((conv as { children?: SduiNode[] }).children ?? []), bubble];
  return { ...conv, children } as SduiNode;
}

function dropConversationFromPanel(root: SduiNode): SduiNode {
  const children = (root as { children?: SduiNode[] }).children;
  if (!Array.isArray(children)) return root;
  const next = children.filter(c => (c as { id?: string }).id !== 'sd-conversation');
  if (next.length === children.length) return root;
  return { ...root, children: next } as SduiNode;
}

function dropHitlFromPanel(root: SduiNode): SduiNode {
  const children = (root as { children?: SduiNode[] }).children;
  if (!Array.isArray(children)) return root;
  const next = children.filter(c => {
    const id = (c as { id?: string }).id;
    return id !== 'hitl-card' && id !== 'hitl-pointer';
  });
  if (next.length === children.length) return root;
  return { ...root, children: next } as SduiNode;
}

/** 从 SDUI 文档提取运行阶段信息（供 updateSkillRun 写入）*/
function extractProgressFromSdui(doc: SduiDocument): {
  phase?: 'running' | 'hitl' | 'done' | 'error';
  progress?: number;
  currentStepName?: string;
  hitlType?: 'file' | 'choice' | 'edit' | null;
  errorMsg?: string;
} {
  const r: {
    phase?: 'running' | 'hitl' | 'done' | 'error';
    progress?: number;
    currentStepName?: string;
    hitlType?: 'file' | 'choice' | 'edit' | null;
    errorMsg?: string;
  } = {};

  const meta = (doc.meta ?? {}) as Record<string, unknown>;
  const metaPhase = meta.phase;
  if (metaPhase === 'running' || metaPhase === 'hitl' || metaPhase === 'done' || metaPhase === 'error') {
    r.phase = metaPhase;
  }
  if (typeof meta.progress === 'number' && !isNaN(meta.progress)) {
    r.progress = Math.max(0, Math.min(100, meta.progress));
  }
  if (typeof meta.error === 'string' && meta.error.trim()) {
    const errText = meta.error.trim();
    if (!isSoftSkipError(errText)) {
      r.phase = 'error';
      r.errorMsg = errText;
    }
  }

  walkSduiNodes(doc.root, (node) => {
    const nodeId = (node as { id?: string }).id ?? '';
    // DonutChart 中心值 → 整体进度百分比
    if (node.type === 'DonutChart' && node.centerValue) {
      const p = parseInt(node.centerValue);
      if (!isNaN(p)) r.progress = p;
    }
    if (node.type === 'TaskTimelineStrip' && typeof node.progressPct === 'number') {
      r.progress = node.progressPct;
    }
    if (node.type === 'StatisticRow') {
      const total = node.items.find(i => i.title === '总进度');
      if (total) {
        const p = parseInt(String(total.value));
        if (!isNaN(p)) r.progress = p;
      }
    }
    if (node.type === 'ProgressBar' && typeof node.value === 'number') {
      r.progress = node.value;
    }
    // Stepper → 当前步骤名 + 阶段
    if (node.type === 'Stepper' && r.phase !== 'hitl') {
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
    if (node.type === 'MacroStepRail' && r.phase !== 'hitl' && r.phase !== 'done') {
      const steps = node.steps ?? [];
      const allDone = steps.length > 0 && steps.every(s => s.status === 'done');
      const runStep = steps.find(s => s.status === 'running');
      if (allDone) {
        r.phase = 'done';
        r.progress = 100;
        r.currentStepName = '';
      } else if (runStep) {
        r.phase = 'running';
        r.currentStepName = runStep.title;
      } else if (node.currentId) {
        const cur = steps.find(s => s.id === node.currentId);
        if (cur) {
          r.phase = 'running';
          r.currentStepName = cur.title;
        }
      }
    }
    if (node.type === 'FlowSteps' && r.phase !== 'hitl') {
      const steps = node.steps ?? [];
      const current = steps.find(s => s.status === 'current');
      const allDone = steps.length > 0 && steps.every(s => s.status === 'done');
      if (allDone) {
        r.phase = 'done';
        r.progress = 100;
        r.currentStepName = '';
      } else if (current) {
        r.phase = 'running';
        r.currentStepName = current.title;
      }
    }
    // HITL 节点优先级最高（覆盖 Stepper / FlowSteps 的阶段判断）
    if (node.type === 'ChoiceCard') { r.phase = 'hitl'; r.hitlType = 'choice'; }
    if (node.type === 'FilePicker') { r.phase = 'hitl'; r.hitlType = 'file';   }
    // 在线编辑型 HITL：editable DataTable 且提交走 resume（run-patch 表非 HITL，不算）
    if (node.type === 'DataTable' && node.editable && (node.submitMode ?? 'resume') === 'resume') {
      r.phase = 'hitl'; r.hitlType = 'edit';
    }
    // 侧边路由式 HITL：hitl-card（guihua Button 交互 / system_design）、hitl-edit-card（在线编辑）
    // → 待操作；completion-card（guihua 询问是否输出文件）→ 已完成。nodeId 见函数顶部声明。
    if (nodeId === 'hitl-card' || nodeId === 'hitl-edit-card') {
      r.phase = 'hitl';
      if (!r.hitlType) r.hitlType = 'choice';
    }
    if (nodeId === 'completion-card') { r.phase = 'done'; r.progress = 100; }
  });

  if (r.phase !== 'hitl' && r.phase !== 'error') {
    walkSduiNodes(doc.root, (node) => {
      if (node.type !== 'StatisticRow') return;
      const report = node.items.find(i => i.title === '调测报告');
      if (report && String(report.value).includes('已生成')) {
        r.phase = 'done';
        r.progress = 100;
        r.currentStepName = '调测完成';
      }
    });
  }

  if (findNodeById(doc.root, 'hitl-card') || findNodeById(doc.root, 'hitl-edit-card')) {
    r.phase = 'hitl';
    if (!r.hitlType) r.hitlType = 'choice';
  }

  return r;
}

// ── 主界面 ────────────────────────────────────────────────────────────────────

export default function SkillAgentScreen({
  skillId,
  title = '作业模块',
  description = 'AI 驱动的作业全流程',
  nextModule,
}: SkillAgentScreenProps) {
  // ── 模式检测：仅当 Manager 分配了容器 endpoint 时走任务 API；本地登录无容器仍直连 Agent
  const { session } = useAidaSession();
  const useClawMode = !!session?.containerEndpoint;
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // ── 状态（两种模式都需要）──────────────────────────────────────────────────
  const [taskId, setTaskId] = useState<string | null>(null);   // 容器模式
  const [runId, setRunId] = useState<string | null>(null);     // 本地模式
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // SSE 重订阅令牌：HITL resume 后自增，强制 useSduiStream 对准后端新建的队列（见 hook 注释）
  const [streamEpoch, setStreamEpoch] = useState(0);
  // 产物预览：open_preview action 触发，存待预览的相对路径（null = 关闭）
  const [previewPath, setPreviewPath] = useState<string | null>(null);
  const [bootDoc, setBootDoc] = useState<SduiDocument | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [commissionExecuting, setCommissionExecuting] = useState<CommissionExecuting | null>(null);
  const [commissionPollDoc, setCommissionPollDoc] = useState<SduiDocument | null>(null);
  const commissionExecStartedAt = useRef(0);
  const commissionPollGenRef = useRef(0);
  // 两态导航（总览 ↔ 作业）：默认总览（3D 机房入口盘）；点意图入口 → 作业；返回总览 → /overview
  const [viewMode, setViewMode] = useState<'overview' | 'work'>('overview');
  // system_design 交付台：SSE + 冻结窗口（进度/HITL 丝滑）；磁盘真值由后端 project() 投影前 sync
  const usesDeliveryWorkbench = DELIVERY_WORKBENCH_SKILLS.has(skillId);
  const [postUploadDoc, setPostUploadDoc] = useState<SduiDocument | null>(null);
  const postUploadEpochRef = useRef(0);
  /** 非交付台 skill：定时拉 /ui 对齐 output/ 磁盘 */
  const [diskPollDoc, setDiskPollDoc] = useState<SduiDocument | null>(null);
  const diskPollGenRef = useRef(0);

  // ── 左右同步：聊天侧 ZhgkProgressCard 启动 run 后自动接入（本地模式）────────
  // store 里有匹配的 skillId + runId 且本地尚未启动 → 直接接入，跳过 IdleScreen
  const storeRun = useSkillRunStore();
  // savedRunStale：持久化 run 过期时置 true，触发 re-render 让 auto-start effect 重新检测
  const [savedRunStale, setSavedRunStale] = useState(false);
  useEffect(() => {
    if (useClawMode) return;
    if (runId) return;
    if (storeRun?.skillId === skillId && storeRun.runId) {
      setRunId(storeRun.runId);
      return;
    }
    const saved = readSkillRunId(skillId);
    if (!saved) return;
    void fetchUiSnapshot(skillId, saved).then(snap => {
      if (snap) {
        setBootDoc(snap);
        setRunId(saved);
        setSkillRun(skillId, saved, 'ui');
      } else {
        clearPersistedSkillRun(skillId);
        setSavedRunStale(true);   // 让 auto-start effect 重新评估
      }
    });
  }, [storeRun, skillId, useClawMode, runId]);

  // ── SDUI 订阅（按模式选择数据源，另一侧传 null 不订阅）──────────────────
  const clawTask = useClawTaskSdui(useClawMode ? taskId : null, session?.accessToken ?? '');
  const directDoc = useSduiStream(skillId, useClawMode ? null : runId, streamEpoch);
  const sduiDoc = useClawMode ? clawTask.doc : directDoc;
  // 重连间隙后端可能短暂投影 idle 空树；显示层忽略，继续用 bootDoc 兜底
  const liveSduiDoc = sduiDoc && !isIdleLikeSduiDoc(sduiDoc) ? sduiDoc : null;

  useEffect(() => {
    if (liveSduiDoc) {
      setBootDoc(null);
      setLoadError(null);
    }
  }, [liveSduiDoc]);

  useEffect(() => {
    if (useClawMode || !isRunUnavailableDoc(sduiDoc)) return;
    clearPersistedSkillRun(skillId);
    clearSkillRun(skillId);
    clearSkillHitl(skillId);
    clearSkillConversation(skillId);
    setSavedRunStale(true);
  }, [sduiDoc, useClawMode, skillId, runId]);

  useEffect(() => {
    if (!runId || liveSduiDoc || bootDoc || starting) return;
    const timer = window.setTimeout(() => {
      setLoadError('工作台加载超时，请重新启动或刷新页面。');
    }, 12000);
    return () => window.clearTimeout(timer);
  }, [runId, liveSduiDoc, bootDoc, starting]);
  // 容器模式：用容器内 aida/agent 的 run_id 做文件上传（clawTask.runId 由 payload 携带）
  const activeRunId = useClawMode ? (clawTask.runId ?? null) : runId;

  // ── resume 冻结窗口：与后端 display_state 双保险，防 full_restart 闪回 idle ───
  const sduiDocRef = useRef<SduiDocument | null>(null);
  useEffect(() => { sduiDocRef.current = sduiDoc; }, [sduiDoc]);
  const frozenSnapshotRef = useRef<SduiDocument | null>(null);
  const [frozenDoc, setFrozenDoc] = useState<SduiDocument | null>(null);
  const frozenProgressRef = useRef(0);
  const progressFloorRef = useRef(0);
  // 设备安装 · HITL 提交后的过渡文档（剥离编辑表 + 当前步 running）；仅 frozenDoc 存在期间生效。
  const diSubmitDocRef = useRef<SduiDocument | null>(null);
  useEffect(() => {
    frozenSnapshotRef.current = null;
    setFrozenDoc(null);
    diSubmitDocRef.current = null;
    progressFloorRef.current = 0;
    frozenProgressRef.current = 0;
  }, [runId, taskId]);
  useEffect(() => {
    if (!frozenDoc && !frozenSnapshotRef.current) return;
    if (!sduiDoc) return;
    // doResume 刚设置冻结时，sduiDoc 与 frozenSnapshotRef 是同一引用，尚无新数据 → 不解冻。
    if (sduiDoc === frozenSnapshotRef.current) return;
    const patch = extractProgressFromSdui(sduiDoc);
    const { progress = 0 } = patch;
    const frozenTarget = frozenProgressRef.current;
    const hasHitl = !!findNodeById(sduiDoc.root, 'hitl-card');
    const frozenDocSnap = frozenSnapshotRef.current ?? frozenDoc;
    const hadHitl = frozenDocSnap ? !!findNodeById(frozenDocSnap.root, 'hitl-card') : false;
    const hitlResolved = hadHitl && !hasHitl;
    const publishDone = usesDeliveryWorkbench && isMacroPublishDone(sduiDoc);
    // HITL 出现/消解即解冻：仅对有进度指标（zhgk / system_design）或交付台 skill 生效。
    // 不加 idle 守卫 —— system_design 的对话框流程依赖该即时解冻语义；
    // guihua（frozenTarget===0 且非交付台）不在此列，仍走下方「只前向推进才解冻」护栏。
    const hitlUnfreeze =
      (frozenTarget > 0 || usesDeliveryWorkbench)
      && (hasHitl || hitlResolved);
    // 有进度指标的 skill（zhgk / system_design）：进度追上冻结水位且已脱离 idle；
    // HITL 消解 / 失败 / 完成 / 发布蓝图步 done → 解冻（error 态 progress 常为 0）。
    if (
      (frozenTarget > 0 && progress >= frozenTarget && !isIdleLikeSduiDoc(sduiDoc))
      || hitlUnfreeze
      || patch.phase === 'error'
      || patch.phase === 'done'
      || publishDone
    ) {
      frozenSnapshotRef.current = null;
      setFrozenDoc(null);
      return;
    }
    // 无进度指标的 skill（guihua / device_install 在线编辑表，frozenTarget===0）：
    // 仅前向推进才解冻（拒绝 full_restart 重放中间态导致步骤条回退）。
    if (frozenTarget === 0) {
      if (frozenDocSnap && hasWorkbenchAdvanced(frozenDocSnap, sduiDoc)) {
        frozenSnapshotRef.current = null;
        setFrozenDoc(null);
        return;
      }
      let hasInteraction = false;
      walkSduiNodes(sduiDoc.root, (node) => {
        const id = (node as { id?: string }).id ?? '';
        if (id === 'hitl-card' || id === 'completion-card') hasInteraction = true;
      });
      if (hasInteraction) {
        frozenSnapshotRef.current = null;
        setFrozenDoc(null);
      }
    }
  }, [sduiDoc, frozenDoc, usesDeliveryWorkbench]);
  // 交付台（system_design）：对齐已跑通的参照版，仅「冻结快照 ?? 实时 SSE」两层。
  // 不再叠加 frozenSnapshotRef.current / postUploadDoc 覆盖层 —— 这两层在 LLD 生成 /
  // 上传 / 完成后不会及时清空，会把已更新的实时 sduiDoc 永久挡住，导致「输出件不刷新、
  // 对话框无后续弹框」。frozenDoc（state）仍由 doResume 设置、unfreeze 副作用清除，
  // 防 full_restart 闪回的能力不变。其它 skill 分支保持原样（不受影响）。
  // 设备安装 · 提交 HITL 后：过渡文档优先（步骤条当前步 running），盖住冻结的编辑表快照。
  const diSubmitOverride =
    !usesDeliveryWorkbench && skillId === 'device_install' && frozenDoc
      ? diSubmitDocRef.current
      : null;
  const displayDoc = usesDeliveryWorkbench
    ? (frozenDoc ?? liveSduiDoc ?? bootDoc)
    : (diSubmitOverride ?? commissionPollDoc ?? postUploadDoc ?? diskPollDoc ?? frozenSnapshotRef.current ?? frozenDoc ?? liveSduiDoc ?? bootDoc);
  const displayDocRef = useRef<SduiDocument | null>(null);
  useEffect(() => { displayDocRef.current = displayDoc; }, [displayDoc]);
  useEffect(() => {
    if (!sduiDoc || postUploadEpochRef.current === 0) return;
    const post = postUploadDoc;
    if (!post) return;
    const postReady = countReadyInputSlots(post);
    const liveReady = countReadyInputSlots(sduiDoc);
    if (liveReady >= postReady && postReady > 0) {
      postUploadEpochRef.current = 0;
      setPostUploadDoc(null);
    }
  }, [sduiDoc, postUploadDoc]);
  useEffect(() => {
    if (usesDeliveryWorkbench) return;
    if (!sduiDoc || !diskPollDoc) return;
    if (countOutputArtifacts(sduiDoc) >= countOutputArtifacts(diskPollDoc)) {
      setDiskPollDoc(null);
    }
  }, [sduiDoc, diskPollDoc, usesDeliveryWorkbench]);
  useEffect(() => {
    if (usesDeliveryWorkbench || useClawMode) return;
    const rid = resolveSkillRunId(skillId, activeRunId, storeRun);
    if (!rid) return;
    let cancelled = false;
    const tick = async () => {
      if (cancelled) return;
      const snap = await fetchUiSnapshot(skillId, rid);
      if (!snap || cancelled) return;
      const outs = countOutputArtifacts(snap);
      if (outs > 0) {
        frozenSnapshotRef.current = null;
        setFrozenDoc(null);
        diskPollGenRef.current += 1;
        setDiskPollDoc(snap);
      }
    };
    void tick();
    const timer = window.setInterval(() => { void tick(); }, 8000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [usesDeliveryWorkbench, useClawMode, skillId, activeRunId, storeRun]);
  useEffect(() => {
    diskPollGenRef.current = 0;
    setDiskPollDoc(null);
    postUploadEpochRef.current = 0;
    setPostUploadDoc(null);
  }, [runId, taskId]);
  useEffect(() => {
    if (usesDeliveryWorkbench) void ensureAgentBase(skillId);
  }, [usesDeliveryWorkbench, skillId]);

  // ── meta 工作台路由协议（SDUI.md §HITL-Edit）────────────────────────────────
  // route_hitl_edit：在线编辑 HITL 卡归属 —— 'workbench'（默认 · 留在右侧大盘）/ 'chat'（移交左栏）。
  // workbench_class：工作台布局策略键，查 WORKBENCH_LAYOUTS 注册表得容器样式覆盖。
  const docMeta = (displayDoc?.meta ?? {}) as Record<string, unknown>;
  const routeHitlEdit: 'workbench' | 'chat' = docMeta.route_hitl_edit === 'chat' ? 'chat' : 'workbench';
  const workbenchClass = typeof docMeta.workbench_class === 'string' ? docMeta.workbench_class : '';

  // Sync SDUI doc → skillRunStore（进度单调递增 · full_restart 重放期间不回退）
  useEffect(() => {
    if (!displayDoc || !activeRunId) return;
    const patch = extractProgressFromSdui(displayDoc);
    // 有实质内容但无进度指标（如 guihua 三页签工作台）：至少标记 running，防止停留在 starting
    if (!patch.phase && !isIdleLikeSduiDoc(displayDoc)) patch.phase = 'running';
    // 进度单调递增（full_restart 重放期间不回退）；冻结期间取冻结水位 / 历史地板的较大值
    let progress = patch.progress ?? 0;
    const frozen = frozenDoc || frozenSnapshotRef.current;
    if (frozen) {
      progress = Math.max(progress, frozenProgressRef.current, progressFloorRef.current);
    } else {
      progress = Math.max(progress, progressFloorRef.current);
    }
    if (patch.phase === 'done') {
      progress = 100;
      progressFloorRef.current = 100;
    } else {
      progressFloorRef.current = progress;
    }
    updateSkillRun({ ...patch, progress });
  }, [displayDoc, activeRunId, frozenDoc]);

  // ── 启动 ──────────────────────────────────────────────────────────────────
  const handleStart = useCallback(async (req: StartReq = {}) => {
    if (!req.intent) setViewMode('overview');
    setStarting(true);
    setError(null);
    try {
      if (useClawMode && session) {
        const resp = await startClawTask({
          accessToken: session.accessToken,
          sessionId: session.sessionId,
          kind: skillId,
          params: { ...req },
        });
        setTaskId(resp.task_id);
      } else {
        const id = await startRun(skillId, req);
        setRunId(id);
        setSkillRun(skillId, id, 'ui');
        persistSkillRunId(skillId, id);
        const snap = await fetchUiSnapshot(skillId, id);
        if (snap) setBootDoc(snap);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '启动失败');
    } finally {
      setStarting(false);
    }
  }, [skillId, useClawMode, session]);

  // 建模仿真（guihua）：进入模块即自动开跑（adapt_build 仅载入适配表，秒级完成 →
  // 「BOQ 数据已解析完毕」），无需用户先点「启动」。仅本地模式、仅一次。
  // 注意：storeRun 重连 effect 和本 effect 在同一渲染周期都能看到 runId===null，
  // 需同步检查 storeRun / readSkillRunId，避免与重连竞争产生第二条 run。
  const autoStartedRef = useRef(false);
  useEffect(() => {
    if (skillId !== 'guihua' || useClawMode) return;
    if (autoStartedRef.current || runId || starting) return;
    // 已有持久化 run 或 store 里有匹配 run → 等重连 effect 处理，不另开新 run
    if (!savedRunStale && readSkillRunId(skillId)) return;
    if (storeRun?.skillId === skillId && storeRun?.runId) return;
    autoStartedRef.current = true;
    void handleStart();
  }, [skillId, useClawMode, runId, starting, handleStart, storeRun, savedRunStale]);

  // ── autostart：从上一模块「进入系统设计」跳转而来时（?autostart=1）自动开跑 ──
  const autostartedRef = useRef(false);
  useEffect(() => {
    if (autostartedRef.current) return;
    if (searchParams.get('autostart') !== '1') return;
    const isIdleNow = useClawMode ? !taskId : !runId;
    if (!isIdleNow || starting) return;
    autostartedRef.current = true;
    void handleStart();
    const next = new URLSearchParams(searchParams);
    next.delete('autostart');
    setSearchParams(next, { replace: true });
  }, [searchParams, useClawMode, taskId, runId, starting, handleStart, setSearchParams]);

  const handleNextModule = useCallback(() => {
    if (!nextModule) return;
    clearSkillRun(skillId);
    clearSkillHitl(skillId);
    clearSkillConversation(skillId);
    navigate(nextModule.to);
  }, [nextModule, skillId, navigate]);

  // ── resume（两种模式统一入口）────────────────────────────────────────────
  const doResume = useCallback(async (payload: Record<string, unknown>, fromStep?: string) => {
    if (useClawMode && session && taskId) {
      await resumeClawTask({
        accessToken: session.accessToken,
        sessionId: session.sessionId,
        taskId,
        payload: { ...payload, ...(fromStep ? { from_step: fromStep } : {}) },
      });
      return;
    }
    const rid = resolveSkillRunId(skillId, activeRunId, storeRun);
    if (!rid) {
      console.warn('[SDUI] resume skipped: no active run_id');
      return;
    }
    // 冻结当前 SDUI 快照，避免 full_restart 重放期间闪回 0% 预检状态
    const curDoc = displayDocRef.current ?? sduiDocRef.current;
    if (curDoc) {
      const curProgress = extractProgressFromSdui(curDoc).progress ?? 0;
      frozenProgressRef.current = Math.max(curProgress, progressFloorRef.current);
      progressFloorRef.current = frozenProgressRef.current;
      frozenSnapshotRef.current = curDoc;
      setFrozenDoc(curDoc);
      // 设备安装：提交后后端 full_restart 重放期间，过渡文档（剥离编辑表 + 当前步 running）顶上，
      // 让步骤条当前节点保持黄色转圈，而不是停留在「待填表」编辑界面假象（看起来卡死）。
      if (skillId === 'device_install') {
        const submittingStep = findEditableHitlStepKey(curDoc);
        const transitional = buildDiSubmittingDoc(curDoc, submittingStep);
        diSubmitDocRef.current = transitional;
        updateSkillRun({ ...extractProgressFromSdui(transitional), phase: 'running', hitlType: null });
      } else if (frozenProgressRef.current > 0) {
        // 有进度指标（zhgk / system_design）：立即切 running 隐藏 HITL 卡；
        // frozenProgress===0（guihua 无进度指标）：不改 phase，保持 'hitl' 让 completion-card / hitl-card 继续显示。
        updateSkillRun({ ...extractProgressFromSdui(curDoc), phase: 'running', hitlType: null });
      }
    }
    await resumeRun(skillId, rid, payload, fromStep);
    // 强制重订阅 SSE：full_restart 会新建队列，旧 EventSource 追不上（见 useSduiStream epoch 注释）
    setStreamEpoch(e => e + 1);
    // device_install：full_restart 耗时较长，SSE 可能晚于冻结层；轮询 /ui 推进界面
    if (skillId === 'device_install' && curDoc) {
      const baseline = curDoc;
      void (async () => {
        for (let i = 0; i < 24; i++) {
          await new Promise(r => setTimeout(r, 500));
          const snap = await fetchUiSnapshot(skillId, rid);
          if (!snap || isIdleLikeSduiDoc(snap)) continue;
          if (!hasWorkbenchAdvanced(baseline, snap)) continue;
          frozenSnapshotRef.current = null;
          setFrozenDoc(null);
          setBootDoc(snap);
          setStreamEpoch(e => e + 1);
          return;
        }
      })();
    }
  }, [useClawMode, session, taskId, activeRunId, skillId, storeRun]);

  const resolveCommissionScope = useCallback((explicit?: string): string => {
    if (explicit?.trim()) return explicit.trim().toLowerCase();
    const meta = displayDoc?.meta?.commission_scope;
    if (typeof meta === 'string' && meta.trim()) return meta.trim().toLowerCase();
    return 'all';
  }, [displayDoc]);

  const finishCommissionExec = useCallback((
    stepKey: string,
    label: string,
    doc: SduiDocument | null,
    isError: boolean,
  ) => {
    setCommissionExecuting(null);
    setCommissionPollDoc(null);
    const kpi = doc ? readCommissionKpi(doc) : null;
    if (isError) {
      emitCommissionProgress(`「${label}」执行失败，请查看右侧红色错误条。`);
      updateSkillRun({ phase: 'error', errorMsg: `${label} 失败` });
      return;
    }
    const kpiHint = kpi ? `命令调测 ${kpi}。` : '';
    if (stepKey === 'commission_report') {
      const rel = doc ? readReportArtifactPath(doc) : null;
      const dlHint = rel ? '请在右侧调度区「下载 · 调测报告」保存 xlsx。' : '报告已生成，请在右侧查看。';
      emitCommissionProgress(`调测报告已生成。${dlHint}`);
      updateSkillRun({
        phase: 'done',
        progress: 100,
        currentStepName: '调测完成',
        hitlType: null,
        errorMsg: '',
      });
      return;
    }
    const allDone = kpi === '4/4';
    emitCommissionProgress(
      `「${label}」已完成。${kpiHint}${allDone ? '四条命令均已执行，可点「生成调测报告」。' : '对应按钮应显示「重新执行」。'}`,
    );
    updateSkillRun({
      phase: allDone ? 'done' : 'running',
      progress: allDone ? 100 : undefined,
      currentStepName: allDone ? '待生成报告' : label,
      hitlType: null,
      errorMsg: '',
    });
  }, []);

  const pollCommissionUntilSettled = useCallback(async (
    rid: string,
    stepKey: string,
    label: string,
    gen: number,
  ) => {
    const deadline = Date.now() + 20 * 60 * 1000;
    while (Date.now() < deadline) {
      if (commissionPollGenRef.current !== gen) return;
      await new Promise<void>(resolve => { window.setTimeout(resolve, 2500); });
      const [st, snap] = await Promise.all([
        fetchRunStatus(skillId, rid),
        fetchUiSnapshot(skillId, rid),
      ]);
      if (commissionPollGenRef.current !== gen) return;
      if (snap) setCommissionPollDoc(snap);
      const outcome = runStepOutcome(st, stepKey);
      const settled = snap ? isCommissionStepSettledInDoc(snap, stepKey) : false;
      if (settled || outcome === 'done' || outcome === 'error') {
        finishCommissionExec(stepKey, label, snap, Boolean(st?.error || outcome === 'error'));
        return;
      }
    }
    if (commissionPollGenRef.current !== gen) return;
    setCommissionExecuting(null);
    emitCommissionProgress(
      `「${label}」等待超过 20 分钟仍未返回；可能仍在 Toolkit 执行，请查右侧日志或稍后刷新。`,
    );
  }, [skillId, finishCommissionExec]);

  const executeCommissionStep = useCallback(async (
    stepKey: string,
    opts?: { rerun?: boolean; scope?: string },
  ) => {
    const scope = resolveCommissionScope(opts?.scope);
    const label = commissionStepLabel(stepKey);
    setLoadError(null);
    const pollGen = commissionPollGenRef.current + 1;
    commissionPollGenRef.current = pollGen;
    setCommissionPollDoc(null);
    setCommissionExecuting({ stepKey, label, scope });
    commissionExecStartedAt.current = Date.now();
    emitCommissionProgress(`正在执行 · ${label}（范围：${formatCommissionScope(scope)}）…`);
    updateSkillRun({ phase: 'running', currentStepName: label, hitlType: null });

    try {
      if (useClawMode && session && taskId) {
        await resumeClawTask({
          accessToken: session.accessToken,
          sessionId: session.sessionId,
          taskId,
          payload: {
            choice: 'confirm',
            rerun: !!opts?.rerun,
            ...(scope !== 'all' ? { scope } : {}),
            from_step: stepKey,
          },
        });
      } else {
        let rid = activeRunId;
        if (!rid) {
          rid = await startRun(skillId, { entry_mode: 'commission' });
          setRunId(rid);
          setSkillRun(skillId, rid, 'ui');
          persistSkillRunId(skillId, rid);
        }
        if (!rid) throw new Error('无法启动调测 run');
        await resumeRun(
          skillId,
          rid,
          { choice: 'confirm', rerun: !!opts?.rerun, ...(scope !== 'all' ? { scope } : {}) },
          stepKey,
        );
        setStreamEpoch(e => e + 1);
        void pollCommissionUntilSettled(rid, stepKey, label, pollGen);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : '执行失败';
      setCommissionExecuting(null);
      emitCommissionProgress(`「${label}」执行失败：${msg}`);
      setLoadError(msg);
    }
  }, [
    resolveCommissionScope,
    useClawMode,
    session,
    taskId,
    activeRunId,
    handleStart,
    skillId,
    pollCommissionUntilSettled,
  ]);

  const runCommissionStep = useCallback(async (
    stepKey: string,
    rerun: boolean,
    scope?: string,
  ) => {
    await executeCommissionStep(stepKey, { rerun, scope });
  }, [executeCommissionStep]);

  const handleCommissionIntent = useCallback(async (intent: CommissionIntent) => {
    if (intent.kind === 'start_commission') {
      await handleStart({ entry_mode: 'commission' });
      return;
    }
    await executeCommissionStep(intent.step, {
      rerun: intent.rerun,
      scope: intent.scope,
    });
  }, [handleStart, executeCommissionStep]);

  // SSE 推新 SDUI 且步骤已落地时结束「执行中」（running 中间态不会误停）
  useEffect(() => {
    if (!commissionExecuting || !sduiDoc) return;
    if (Date.now() - commissionExecStartedAt.current < 400) return;
    if (!isCommissionStepSettledInDoc(sduiDoc, commissionExecuting.stepKey)) return;
    const { stepKey, label } = commissionExecuting;
    const hasErr = Boolean(findNodeById(sduiDoc.root, 'sd-error-banner'));
    commissionPollGenRef.current += 1;
    finishCommissionExec(stepKey, label, sduiDoc, hasErr);
  }, [sduiDoc, commissionExecuting, finishCommissionExec]);

  // 刷新后若 UI 已落地但 executing 状态残留，自动解锁调度按钮
  useEffect(() => {
    if (!commissionExecuting || !displayDoc) return;
    if (!isCommissionStepSettledInDoc(displayDoc, commissionExecuting.stepKey)) return;
    commissionPollGenRef.current += 1;
    finishCommissionExec(
      commissionExecuting.stepKey,
      commissionExecuting.label,
      displayDoc,
      Boolean(findNodeById(displayDoc.root, 'sd-error-banner')),
    );
  }, [displayDoc, commissionExecuting, finishCommissionExec]);

  useEffect(() => {
    if (skillId !== 'software_deployment') return;
    const onCommission = (e: Event) => {
      const intent = (e as CustomEvent<CommissionIntent>).detail;
      if (!intent) return;
      void handleCommissionIntent(intent);
    };
    window.addEventListener('aida:commission', onCommission);
    return () => window.removeEventListener('aida:commission', onCommission);
  }, [skillId, handleCommissionIntent]);


  // 3D 机房入口「下钻→意图」：在意图 HITL 处用所选意图续跑同一 run；否则以该意图启动 run
  const handleIntent = useCallback(async (intent: string) => {
    const card = sduiDocRef.current ? findNodeById(sduiDocRef.current.root, 'hitl-card') : null;
    const atIntentHitl = !!card && JSON.stringify(card).includes(`"${intent}"`);
    setViewMode('work');
    if (activeRunId && atIntentHitl) {
      await doResume({ choice: intent });
    } else if (activeRunId) {
      // 已在跑且非意图 HITL：只切作业台，避免误触发新开 run
    } else {
      await handleStart({ intent });
    }
  }, [activeRunId, doResume, handleStart]);

  // ── 重置会话 → 清空工作区产物 + 对话上下文，回到 idle 启动页 ─────────────────
  const handleResetSession = useCallback(async () => {
    if (activeRunId) clearRunLog(activeRunId);
    try {
      await resetWorkspace(skillId);
    } catch (e) {
      console.error('[SDUI] reset-workspace error:', e);
    }
    clearSkillRun(skillId);
    clearPersistedSkillRun(skillId);
    clearSkillHitl(skillId);
    setBootDoc(null);
    setLoadError(null);
    setCommissionExecuting(null);
    setCommissionPollDoc(null);
    setRunId(null);
    setTaskId(null);
    frozenSnapshotRef.current = null;
    setFrozenDoc(null);
    setStreamEpoch(0);
    setPreviewPath(null);
    setError(null);
    setStarting(false);
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('aida:clear'));
    }
  }, [skillId, activeRunId]);

  // ── 动作处理 ──────────────────────────────────────────────────────────────
  const handleAction = useCallback(async (action: SduiAction) => {
    if (action.kind === 'post_user_message') {
      const text = action.text;
      const runStep = text.match(/^\/run_step_([\w_]+?)(_rerun)?$/);
      if (runStep) {
        await runCommissionStep(runStep[1]!, !!runStep[2]);
        return;
      }
      if (text.startsWith('/download_')) {
        const rel = text.slice('/download_'.length).replace(/^\//, '');
        if (rel) {
          const url = `${AGENT_BASE}/agent/${skillId}/artifact?path=${encodeURIComponent(rel)}`;
          window.open(url, '_blank', 'noopener,noreferrer');
        }
        return;
      }
      if (text.startsWith('__activate_tab__:')) {
        // 客户端页签切换约定（不走后端 resume）：如「查看详细数据」切到设备数据页。
        const tabId = text.slice('__activate_tab__:'.length);
        window.dispatchEvent(new CustomEvent('sdui:activate-tab', { detail: { tabId } }));
      } else if (text.startsWith('/start_') || text.startsWith('/retry_')) {
        await handleStart();
      } else if (text.startsWith('/resume_')) {
        await doResume({});
      } else if (text.startsWith('/view_')) {
        // TODO: 打开报告预览
      } else if (text.startsWith('/intent ')) {
        await handleIntent(text.slice('/intent '.length).trim());
      } else if (text === '/work') {
        setViewMode('work');
      } else if (text === '/overview') {
        setViewMode('overview');
      } else if (usesDeliveryWorkbench) {
        // system_design：根据当前态路由自由文本（启动 / 重试 / HITL 续跑 / full_restart 携带指令）
        const liveDoc = sduiDocRef.current ?? displayDocRef.current;
        const doc = liveDoc;
        const isIdleNow = useClawMode ? !taskId : !resolveSkillRunId(skillId, activeRunId, storeRun);
        const prog = doc ? extractProgressFromSdui(doc) : {};
        const hasHitl = doc ? !!findNodeById(doc.root, 'hitl-card') : false;
        if (isIdleNow) {
          await handleStart();
        } else if (prog.phase === 'error') {
          await doResume({ text, choice: text }, resolveDeliveryResumeFromStep(text));
        } else if (hasHitl) {
          await doResume({ choice: text, text }, resolveDeliveryResumeFromStep(text));
        } else {
          // input_check 完成后无 HITL 卡（step_retry 仅重跑检查步）· 仍须 full_restart 携带用户指令
          await doResume({ text, choice: text }, resolveDeliveryResumeFromStep(text));
          const rid = resolveSkillRunId(skillId, activeRunId, storeRun);
          if (rid) {
            void (async () => {
              for (let i = 0; i < 12; i++) {
                await new Promise(r => setTimeout(r, i === 0 ? 300 : 450));
                const snap = await fetchUiSnapshot(skillId, rid);
                if (!snap) continue;
                const hitl = findNodeById(snap.root, 'hitl-card');
                const conv = findNodeById(snap.root, 'sd-conversation');
                const hasExecConfirm = !!hitl && String((hitl as { title?: string }).title || '').includes('确认执行');
                let hasUnderstood = false;
                if (conv) walkSduiNodes(conv, n => {
                  if ((n as { id?: string }).id === 'cv-understood') hasUnderstood = true;
                });
                if (hasExecConfirm || hasUnderstood) {
                  postUploadEpochRef.current = Date.now();
                  setPostUploadDoc(snap);
                  break;
                }
              }
            })();
          }
        }
      } else {
        dispatchRailSend(text);
      }
    } else if (action.kind === 'open_preview') {
      setPreviewPath(action.path);
    } else if (action.kind === 'reset_session') {
      void handleResetSession();
    }
  }, [handleStart, doResume, handleResetSession, handleIntent, runCommissionStep, skillId, usesDeliveryWorkbench, useClawMode, taskId, runId, activeRunId, storeRun]);

  // ── 在线编辑型 HITL 提交（resume · rows 由 skill.apply_resume_payload 写回 project）──
  const handleRowsSubmit = useCallback(async (rows: Record<string, unknown>[], _stepId?: string) => {
    await doResume({ rows });
  }, [doResume]);

  // ── run-patch 轻量补丁（任务进展保存 / 返回上一步等 · 不重跑 LangGraph）──────────
  const handleRunPatch = useCallback(async (payload: Record<string, unknown>) => {
    if (!activeRunId) return;
    await runPatchRun(skillId, activeRunId, payload);
  }, [activeRunId, skillId]);

  const handleUpload = useCallback(async (
    files: FileList,
    purpose?: string,
    _stepId?: string,
    slotTag?: string,
    slotLabel?: string,
  ) => {
    const arr = Array.from(files);
    // system_design 输出件覆盖：写入 output/ 原 path · 不 resume · 不走 upload/batch
    if (skillId === 'system_design' && purpose?.startsWith('override:')) {
      const targetPath = purpose.slice('override:'.length);
      const rid = resolveSkillRunId(skillId, activeRunId, storeRun);
      if (!rid) {
        throw new Error('尚未启动作业 run，请先从左侧启动系统设计后再上传');
      }
      if (!arr.length) {
        throw new Error('未选择文件');
      }
      try {
        const result = await overrideOutputArtifact(skillId, arr[0]!, targetPath, rid);
        if (result.ok === false) {
          throw new Error(String(result.error || '覆盖上传失败'));
        }
        frozenSnapshotRef.current = null;
        setFrozenDoc(null);
        const snap = await fetchUiSnapshot(skillId, rid);
        if (snap) {
          postUploadEpochRef.current = Date.now();
          setPostUploadDoc(snap);
        }
        setError(null);
      } catch (e) {
        const msg = e instanceof Error ? e.message : '覆盖上传失败，请检查文件格式或网络连接';
        console.error('[SDUI] override upload error:', e);
        setError(msg);
        throw e instanceof Error ? e : new Error(msg);
      }
      return;
    }
    // 非 system_design（zhgk/guihua/device_install/software_deployment）：通用上传 + 续跑
    if (!usesDeliveryWorkbench) {
      try {
        await uploadBatch(skillId, arr);
      } catch (e) {
        console.error('[SDUI] upload error:', e);
        throw e instanceof Error ? e : new Error('上传失败，请检查文件格式或网络连接');
      }
      await doResume({ uploaded: arr.map(f => f.name) });
      return;
    }
    // system_design 交付台：按槽位标签上传 → sync_inputs → 拉快照；仅「输入件准备」HITL 内续跑
    const kinds = arr.map(f => resolveUploadSlotTag(slotTag, slotLabel, f.name));
    const labels = arr.map(() => (slotLabel?.trim() ? slotLabel.trim() : ''));
    if (kinds.some(k => !k)) {
      throw new Error('无法识别输入件类型，请从对应槽位（如「项目信息收集表」）点击「上传」');
    }
    const rid = resolveSkillRunId(skillId, activeRunId, storeRun);
    if (!rid) {
      throw new Error('尚未启动作业 run，请先从左侧启动系统设计后再上传');
    }
    try {
      const result = await uploadBatch(skillId, arr, [], kinds, rid, labels);
      const staleMsg = staleSystemDesignUploadMessage(result);
      if (staleMsg) throw new Error(staleMsg);
      const failed = (result.uploaded ?? []).filter(u => u.ok === false);
      if (failed.length) {
        const msg = failed.map(f => String(f.error || f.filename || '未知文件')).join('；');
        throw new Error(`上传失败：${msg}`);
      }
      const saved = (result.uploaded ?? []).filter(u => u.ok !== false && u.path);
      if (!saved.length && (result.uploaded ?? []).length) {
        throw new Error('上传未落盘，请确认 Agent 已重启并加载最新 system_design 配置');
      }
      if (rid) {
        try {
          await runPatchRun(skillId, rid, { action: 'sync_inputs' });
        } catch {
          // upload/batch 可能已 sync；忽略
        }
        frozenSnapshotRef.current = null;
        setFrozenDoc(null);
        const snap = await fetchUiSnapshot(skillId, rid);
        if (snap) {
          postUploadEpochRef.current = Date.now();
          setPostUploadDoc(snap);
        }
        // 强制重订阅 SSE：sync_inputs 只改磁盘/状态、不推 SSE，而 system_design 左栏弹框/HITL
        // 读实时 sduiDoc、右栏读 displayDoc→liveSduiDoc（均不含 postUploadDoc 兜底）；
        // 不重订阅则上传后界面停在旧态（无后续弹框 / 状态不更新）。
        setStreamEpoch(e => e + 1);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : '上传失败，请检查文件格式或网络连接';
      console.error('[SDUI] upload error:', e);
      setError(msg);
      throw e instanceof Error ? e : new Error(msg);
    }
    setError(null);
    // 仅「输入件准备」HITL 卡内上传后自动重试 input_check；输入件页签上传只 sync 不续跑
    const doc = sduiDocRef.current;
    const hitlCard = doc ? findNodeById(doc.root, 'hitl-card') : null;
    const isInputPrepareHitl = !!hitlCard && String((hitlCard as { title?: string }).title || '') === '输入件准备';
    if (isInputPrepareHitl && rid) {
      void (async () => {
        await doResume({ uploaded: arr.map(f => f.name) });
        for (let i = 0; i < 10; i++) {
          await new Promise(r => setTimeout(r, i === 0 ? 250 : 400));
          const snap = await fetchUiSnapshot(skillId, rid);
          if (snap && sduiHasInputCheckDone(snap)) {
            postUploadEpochRef.current = Date.now();
            setPostUploadDoc(snap);
            break;
          }
        }
      })();
    }
  }, [skillId, doResume, usesDeliveryWorkbench, activeRunId, storeRun]);

  const handleChoiceSubmit = useCallback(async (value: string, stepId?: string) => {
    await doResume(
      { choice: value },
      resolveChoiceResumeFromStep(skillId, value, stepId),
    );
  }, [doResume, skillId]);

  // 左栏 store 与右栏 Context 共用：ref 保证首击即最新闭包（避免 useEffect 同步滞后一帧）
  const handleActionRef = useRef(handleAction);
  const handleUploadRef = useRef(handleUpload);
  const handleChoiceSubmitRef = useRef(handleChoiceSubmit);
  handleActionRef.current = handleAction;
  handleUploadRef.current = handleUpload;
  handleChoiceSubmitRef.current = handleChoiceSubmit;

  const railRuntimeCallbacks = useRef({
    onAction: (action: SduiAction) => { void handleActionRef.current(action); },
    onUpload: (
      files: FileList,
      purpose?: string,
      stepId?: string,
      slotTag?: string,
      slotLabel?: string,
    ) => handleUploadRef.current(files, purpose, stepId, slotTag, slotLabel),
    onChoiceSubmit: (value: string, stepId?: string) => {
      void handleChoiceSubmitRef.current(value, stepId);
    },
  }).current;

  // ── HITL 提升到左侧会话框 ─────────────────────────────────────────────────
  // sduiDoc 出现 hitl-card → 连同 resume 回调写入 skillHitlStore；
  // 左侧 SkillRunBanner 据此渲染可交互卡。无 HITL / 卸载时清除。
  // 在线编辑卡（hitl-edit-card）默认留在右侧大盘，仅 meta.route_hitl_edit==='chat' 才移交。
  // HITL / 左栏弹框始终读 SSE 实时态（reconcile 后的 /ui 快照会清掉 stage_select HITL）
  useEffect(() => {
    const rid = resolveSkillRunId(skillId, activeRunId, storeRun);
    const hitlDoc = usesDeliveryWorkbench ? sduiDoc : displayDoc;
    if (!hitlDoc || !rid) { clearSkillHitl(skillId); return; }
    const card = findNodeById(hitlDoc.root, 'hitl-card')
      ?? findNodeById(hitlDoc.root, 'completion-card')
      ?? (routeHitlEdit === 'chat' ? findNodeById(hitlDoc.root, 'hitl-edit-card') : null);
    if (card) {
      setSkillHitl({
        skillId, runId: rid, node: card,
        onChoiceSubmit: railRuntimeCallbacks.onChoiceSubmit,
        onUpload: railRuntimeCallbacks.onUpload,
        onAction: railRuntimeCallbacks.onAction,
      });
    } else {
      clearSkillHitl(skillId);
    }
  }, [usesDeliveryWorkbench, sduiDoc, displayDoc, activeRunId, storeRun, skillId, routeHitlEdit, railRuntimeCallbacks]);

  useEffect(() => () => clearSkillHitl(skillId), [skillId]);  // 卸载清理
  useEffect(() => () => clearSkillRun(skillId), [skillId]);  // 卸载清理，避免左栏残留上一模块进度

  // ── 会话流（AIDA 助手）提升到左侧会话框（仅 system_design 交付台）────────────
  useEffect(() => {
    if (!usesDeliveryWorkbench) { clearSkillConversation(skillId); return; }
    const rid = resolveSkillRunId(skillId, activeRunId, storeRun);
    const convDoc = sduiDoc ?? displayDoc;
    if (!convDoc || !rid) { clearSkillConversation(skillId); return; }
    const conv = findNodeById(convDoc.root, 'sd-conversation');
    if (conv) {
      setSkillConversation({
        skillId, runId: rid,
        node: ensureConversationErrorBubble(conv, convDoc),
        runtime: {
          runId: rid,
          skillId,
          onAction: railRuntimeCallbacks.onAction,
          onUpload: railRuntimeCallbacks.onUpload,
          onChoiceSubmit: railRuntimeCallbacks.onChoiceSubmit,
        },
      });
    } else {
      clearSkillConversation(skillId);
    }
  }, [usesDeliveryWorkbench, sduiDoc, displayDoc, activeRunId, storeRun, skillId, railRuntimeCallbacks]);

  useEffect(() => () => clearSkillConversation(skillId), [skillId]);

  // ── SDUI 运行时 ──────────────────────────────────────────────────────────
  const runtime: SduiRuntime = {
    runId: activeRunId,
    skillId,
    onAction: railRuntimeCallbacks.onAction,
    onUpload: railRuntimeCallbacks.onUpload,
    onChoiceSubmit: railRuntimeCallbacks.onChoiceSubmit,
    onRowsSubmit: (rows, stepId) => { void handleRowsSubmit(rows, stepId); },
    onRunPatch: handleRunPatch,
    streamEpoch,
    commissionExecuting,
  };

  // ── 渲染 ────────────────────────────────────────────────────────────────
  const isIdle = useClawMode ? !taskId : !runId;
  if (isIdle && !starting) {
    return (
      <div style={{ height: '100%', overflow: 'auto' }}>
        <IdleScreen
          skillId={skillId}
          title={title}
          description={description}
          onStart={() => { void handleStart(); }}
          onCommissionStart={skillId === 'software_deployment' ? () => { void handleStart({ entry_mode: 'commission' }); } : undefined}
          loading={starting}
        />
        {nextModule && (
          <NextModuleButton label={nextModule.label} onClick={handleNextModule} />
        )}
        {error && (
          <div style={{ margin: '0 auto', maxWidth: 320, padding: 12, background: 'var(--red-50)', borderRadius: 'var(--radius-md)', color: 'var(--red-700)', fontSize: 'var(--text-sm)', textAlign: 'center' }}>
            {error}
          </div>
        )}
      </div>
    );
  }

  const leftRailHitl = displayDoc ? hasLeftRailHitl(displayDoc) : false;
  // 交付台 skill（system_design）不走 3D 两态；其它 skill 保留总览 ↔ 作业切换
  const showOverviewBar = !usesDeliveryWorkbench && viewMode === 'overview' && !!displayDoc && hasMachineRoom3d(displayDoc.root);
  const displayRoot = displayDoc
    ? (usesDeliveryWorkbench
        // 交付台：右栏面板剥离左栏会话与 HITL 卡（它们已提升到左侧 ClawRail）
        ? dropConversationFromPanel(dropHitlFromPanel(displayDoc.root))
        // guihua：HITL 路由左侧会话框，右侧剥离 hitl-card + completion-card 两张导引卡
        : skillId === 'guihua'
          ? applyViewMode(stripSideRoutedCards(displayDoc.root), viewMode)
          // 其它 skill：HITL 路由到左栏 + 两态视图裁剪
          : applyViewMode(
              leftRailHitl
                ? stripHitlCard(displayDoc.root)
                : routeHitlToChat(displayDoc.root, routeHitlEdit === 'chat'),
              viewMode,
            ))
    : null;

  return (
    <SduiRuntimeContext.Provider value={runtime}>
      <div
        data-workbench={workbenchClass || undefined}
        style={{
          height: '100%', overflow: 'auto', padding: 'var(--pad-panel)',
          ...(WORKBENCH_LAYOUTS[workbenchClass] ?? {}),
        }}
      >
        {commissionExecuting ? (
          <div style={{
            marginBottom: 12, padding: '10px 14px', borderRadius: 8,
            background: '#eef1fc', border: '1px solid #c7d2fe',
            fontSize: 13, color: '#1e34a8', display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <i style={{
              width: 14, height: 14, borderRadius: '50%',
              border: '2px solid #3551d8', borderTopColor: 'transparent',
              display: 'inline-block', flexShrink: 0, animation: 'spin .8s linear infinite',
            }} />
            正在执行 · {commissionExecuting.label}（范围：{formatCommissionScope(commissionExecuting.scope)}）
          </div>
        ) : null}
        {loadError ? (
          <div style={{ padding: 24, textAlign: 'center', color: 'var(--red-700)', fontSize: 'var(--text-sm)', marginBottom: 12 }}>
            {loadError}
            <div style={{ marginTop: 12 }}>
              <Button variant="secondary" size="sm" onClick={() => { clearPersistedSkillRun(skillId); setRunId(null); setLoadError(null); setBootDoc(null); }}>
                返回启动页
              </Button>
            </div>
          </div>
        ) : null}
        {showOverviewBar && (
          <div
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
              marginBottom: 12, padding: '10px 14px',
              background: 'var(--c-surface, #fff)', border: '1px solid var(--c-border, #e2e8f0)',
              borderRadius: 'var(--r-lg, 8px)',
            }}
          >
            <span style={{ fontSize: 'var(--fs-14, 14px)', fontWeight: 600, color: 'var(--c-text-1, #0f172a)' }}>
              机房总览
            </span>
            <button
              type="button"
              onClick={() => setViewMode('work')}
              style={{
                padding: '5px 12px', fontFamily: 'var(--font-sans)', fontSize: '12.5px', fontWeight: 600,
                border: '1px solid var(--c-brand, #3551d8)', borderRadius: 'var(--r-sm, 6px)',
                background: 'var(--c-brand, #3551d8)', color: '#fff', cursor: 'pointer',
              }}
            >
              进入作业台 →
            </button>
          </div>
        )}
        {displayRoot ? (
          <SduiNodeView node={displayRoot} />
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
      {nextModule && (
        <NextModuleButton label={nextModule.label} onClick={handleNextModule} />
      )}
    </SduiRuntimeContext.Provider>
  );
}

function NextModuleButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        position: 'fixed', right: 28, bottom: 28, zIndex: 40,
        display: 'inline-flex', alignItems: 'center', gap: 8,
        padding: '11px 20px', borderRadius: 999, border: 'none', cursor: 'pointer',
        color: '#fff', fontSize: 14, fontWeight: 600, letterSpacing: '.01em',
        background: 'linear-gradient(118deg, #3551d8 0%, #5b3ce0 52%, #7c3aed 100%)',
        boxShadow: '0 14px 34px -12px rgba(53,81,216,.6)',
      }}
    >
      {label}
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M5 12h14M13 6l6 6-6 6" />
      </svg>
    </button>
  );
}
