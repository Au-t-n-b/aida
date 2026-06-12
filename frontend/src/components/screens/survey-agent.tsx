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
import { useSduiStream, startRun, resumeRun, uploadBatch, runPatchRun, resetWorkspace, isIdleLikeSduiDoc, fetchUiSnapshot, type StartReq } from '@/hooks/useSduiStream';
import { resolveUploadSlotTag } from '@/lib/systemDesignUpload';
import { ensureAgentBase, staleSystemDesignUploadMessage } from '@/lib/agentBase';
import { clearRunLog } from '@/lib/runLogStore';
import { useClawTaskSdui } from '@/hooks/useClawTaskSdui';
import { useAidaSession } from '@/lib/aida-session';
import { startClawTask, resumeClawTask } from '@/lib/claw-manager-client';
import { useSkillRunStore, setSkillRun, updateSkillRun, clearSkillRun } from '@/lib/skillRunStore';
import { setSkillHitl, clearSkillHitl } from '@/lib/skillHitlStore';
import { dispatchRailSend } from '@/lib/claw-send';
import { setSkillConversation, clearSkillConversation } from '@/lib/skillConversationStore';
import { Button } from '@/components/primitives';
import type { SduiAction, SduiDocument, SduiNode } from '@/lib/sdui';

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

/** HITL 提交后保留「已提交」确认态的最短可见时长（ms），随后再推进 resume。 */
const HITL_HOLD_MS = 650;

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
    /* ── 横向步骤条 ── */
    .skill-idle-steps {
      display:flex; align-items:flex-start; width:100%; max-width:420px;
      margin-bottom:22px;
    }
    .skill-idle-step { display:flex; flex-direction:column; align-items:center; flex:1; min-width:0; }
    .skill-idle-step-row { display:flex; align-items:center; width:100%; }
    .skill-idle-dot {
      width:28px; height:28px; border-radius:50%; flex-shrink:0;
      background:#fff; border:1.5px solid #c8d1e6;
      display:flex; align-items:center; justify-content:center;
      font-size:11px; font-weight:700; color:#94a3b8;
      transition:border-color .2s;
      box-shadow:0 1px 3px rgba(15,23,42,.06);
    }
    .skill-idle-conn { flex:1; height:1.5px; background:#dde3ef; }
    .skill-idle-step-label {
      font-size:10px; color:#64748b; font-weight:500;
      margin-top:7px; text-align:center; white-space:nowrap;
      max-width:56px; overflow:hidden; text-overflow:ellipsis;
    }
    .skill-idle-step-sub {
      font-size:9.5px; color:#94a3b8; margin-top:2px;
      text-align:center; max-width:60px; line-height:1.35;
      display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;
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
  files: Array<{ name: string; ext: string; optional?: boolean }>;
  icon: React.ReactNode;
  filesHint?: string;
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
        <rect x="7" y="5" width="15" height="22" rx="2" stroke="currentColor" strokeWidth="1.6" />
        <path d="M10.5 10h8M10.5 14h8M10.5 18h8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
        <circle cx="25" cy="16" r="5.5" stroke="currentColor" strokeWidth="1.6" />
        <path d="M25 13.5v5M22.5 16h5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
    ),
    filesHint: 'ProjectData/Input/',
    steps: [
      { key: 'plan_receive',  name: '接收实施计划', sub: '上游双 Sheet' },
      { key: 'task_dispatch', name: '计划下发',     sub: '勾选·下发' },
      { key: 'sn_generate',   name: 'SN扫码表',     sub: '按单元生成' },
      { key: 'esn_fill',      name: 'ESN填写',      sub: '完工清单' },
    ],
    files: [
      { name: '设备安装实施计划.xlsx', ext: 'xlsx' },
    ],
  },
  xtsj: {
    icon: (
      <svg width={34} height={34} viewBox="0 0 34 34" fill="none">
        <circle cx="17" cy="17" r="11" stroke="currentColor" strokeWidth="1.6" />
        <path d="M11 17h12M17 11v12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    ),
    filesHint: 'ProjectData/Input/',
    steps: [
      { key: 'input_check',  name: '输入件检查', sub: '001/004/007' },
      { key: 'address_plan', name: '地址批规划', sub: 'CSM/CC-GLM/…' },
    ],
    files: [
      { name: '建模仿真输出文档001-设备信息表.xlsx', ext: 'xlsx' },
      { name: '建模仿真输出文档004-设备位置表.xlsx', ext: 'xlsx' },
      { name: '建模仿真输出文档007-端口连线表.xlsx', ext: 'xlsx' },
    ],
  },
  system_design: {
    icon: (
      <svg width={34} height={34} viewBox="0 0 34 34" fill="none">
        <rect x="6" y="6" width="22" height="22" rx="3" stroke="currentColor" strokeWidth="1.6" />
        <path d="M11 12h12M11 17h8M11 22h10" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
    ),
    filesHint: 'ProjectData/Input/',
    steps: [
      { key: 'intent_recognition', name: '意图识别',   sub: 'NL → 标准命令' },
      { key: 'input_check',        name: '输入件检查', sub: '4 件必需' },
      { key: 'plane_planning',     name: '平面规划',   sub: '地址/互联' },
      { key: 'lld_integrate',      name: 'LLD 融合',   sub: '去重合并' },
      { key: 'publish',            name: '发布完成',   sub: '产物汇总' },
    ],
    files: [
      { name: '项目信息收集表.xlsx', ext: 'xlsx' },
      { name: '建模仿真输出文档001-设备信息表.xlsx', ext: 'xlsx' },
      { name: '建模仿真输出文档004-设备位置表.xlsx', ext: 'xlsx' },
      { name: '建模仿真输出文档007-端口连线表.xlsx', ext: 'xlsx' },
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

function sanitizeErrorText(raw: string): string {
  const lines = raw.split('\n').filter((line) => {
    const l = line.toLowerCase();
    return !(l.includes('userwarning') || l.includes('openpyxl') || l.includes('stylesheet.py'));
  });
  return (lines.join('\n').trim() || raw.trim());
}

function ensureConversationErrorBubble(conv: SduiNode, doc: SduiDocument): SduiNode {
  const err = sanitizeErrorText(String(doc.meta?.error ?? '').trim());
  if (!err || conversationHasDangerBubble(conv)) return conv;
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

/** 自动执行、无需左栏 HITL 提示的流水线步骤 */
const AUTO_PIPELINE_STEP_IDS = new Set(['preflight', 'plan_receive', 'sn_generate']);

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

  if (doc.meta?.phase === 'error' || doc.meta?.error) {
    r.phase = 'error';
    r.errorMsg = String(doc.meta.error ?? '执行失败');
    return r;
  }

  walkSduiNodes(doc.root, (node) => {
    // DonutChart 中心值 → 整体进度百分比
    if (node.type === 'DonutChart' && node.centerValue) {
      const p = parseInt(node.centerValue);
      if (!isNaN(p)) r.progress = p;
    }
    if (node.type === 'TaskTimelineStrip' && typeof node.progressPct === 'number' && r.progress == null) {
      r.progress = Math.max(0, Math.min(100, Math.round(node.progressPct)));
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
    if (node.type === 'MacroStepRail' && !r.phase) {
      const steps = node.steps ?? [];
      const runStep = steps.find(s => s.status === 'running');
      const allDone = steps.length > 0 && steps.every(s => (s.status ?? 'pending') === 'done');
      if (allDone) {
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
    // system_design 专用 HITL 节点类型
    if (node.type === 'IoConfirmPanel') { r.phase = 'hitl'; r.hitlType = 'choice'; }
    if (node.type === 'InputSlotList') { r.phase = 'hitl'; r.hitlType = 'file'; }
    if (node.type === 'Card' && (node as { id?: string }).id === 'hitl-card') {
      r.phase = 'hitl';
      if (!r.hitlType) r.hitlType = 'file';
    }
    // 在线编辑型 HITL：editable DataTable 且提交走 resume（run-patch 表非 HITL，不算）
    if (node.type === 'DataTable' && node.editable && (node.submitMode ?? 'resume') === 'resume') {
      r.phase = 'hitl'; r.hitlType = 'edit';
    }
  });

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
  // 两态导航（总览 ↔ 作业）：默认总览（3D 机房入口盘）；点意图入口 → 作业；返回总览 → /overview
  const [viewMode, setViewMode] = useState<'overview' | 'work'>('overview');
  /** 上传成功后主动拉 /ui 快照，避免 SSE 未及时推送时槽位仍显示「缺失」 */
  const [postUploadDoc, setPostUploadDoc] = useState<SduiDocument | null>(null);
  const postUploadEpochRef = useRef(0);

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
  const effectiveSduiDoc = postUploadDoc ?? sduiDoc;
  useEffect(() => {
    if (!sduiDoc || postUploadEpochRef.current === 0) return;
    postUploadEpochRef.current = 0;
    setPostUploadDoc(null);
  }, [sduiDoc]);
  // 容器模式：用容器内 aida/agent 的 run_id 做文件上传（clawTask.runId 由 payload 携带）
  const activeRunId = useClawMode ? (clawTask.runId ?? null) : runId;
  const usesDeliveryWorkbench = DELIVERY_WORKBENCH_SKILLS.has(skillId);

  // ── resume 冻结窗口：与后端 display_state 双保险，防 full_restart 闪回 idle ───
  const sduiDocRef = useRef<SduiDocument | null>(null);
  useEffect(() => { sduiDocRef.current = effectiveSduiDoc; }, [effectiveSduiDoc]);
  const frozenSnapshotRef = useRef<SduiDocument | null>(null);
  const [frozenDoc, setFrozenDoc] = useState<SduiDocument | null>(null);
  const frozenProgressRef = useRef(0);
  useEffect(() => {
    frozenSnapshotRef.current = null;
    setFrozenDoc(null);
  }, [runId, taskId]);
  useEffect(() => {
    if (!frozenDoc && !frozenSnapshotRef.current) return;
    if (!sduiDoc) return;
    const { progress = 0 } = extractProgressFromSdui(sduiDoc);
    // 实时进度追上冻结水位且已脱离 idle 引导态 → 解冻
    if (progress >= frozenProgressRef.current && progress > 0 && !isIdleLikeSduiDoc(sduiDoc)) {
      frozenSnapshotRef.current = null;
      setFrozenDoc(null);
    }
  }, [sduiDoc, frozenDoc]);
  // resume 期间展示冻结快照（frozenSnapshotRef/frozenDoc），其余时间展示实时文档
  const displayDoc = frozenSnapshotRef.current ?? frozenDoc ?? effectiveSduiDoc;

  // ── meta 工作台路由协议（SDUI.md §HITL-Edit）────────────────────────────────
  // route_hitl_edit：在线编辑 HITL 卡归属 —— 'workbench'（默认 · 留在右侧大盘）/ 'chat'（移交左栏）。
  // workbench_class：工作台布局策略键，查 WORKBENCH_LAYOUTS 注册表得容器样式覆盖。
  const docMeta = (displayDoc?.meta ?? {}) as Record<string, unknown>;
  const routeHitlEdit: 'workbench' | 'chat' = docMeta.route_hitl_edit === 'chat' ? 'chat' : 'workbench';
  const workbenchClass = typeof docMeta.workbench_class === 'string' ? docMeta.workbench_class : '';

  // Sync SDUI doc → skillRunStore（与 displayDoc 同步，冻结期间左侧进度不闪回 0%）
  useEffect(() => {
    if (!displayDoc || !activeRunId) return;
    updateSkillRun(extractProgressFromSdui(displayDoc));
  }, [displayDoc, activeRunId]);

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
        // 通知聊天侧：source='ui' → ClawRail 检测到后自动注入 SkillRunBanner 消息
        setSkillRun(skillId, id, 'ui');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '启动失败');
    } finally {
      setStarting(false);
    }
  }, [skillId, useClawMode, session]);

  // ── autostart：从上一模块「进入系统设计」跳转而来时（?autostart=1）自动开始 ──
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

  // ── resume（两种模式统一入口）────────────────────────────────────────────
  const doResume = useCallback(async (payload: Record<string, unknown>) => {
    const rid = activeRunId ?? (storeRun?.skillId === skillId ? storeRun.runId : null);
    const isUploadResume = Array.isArray(payload.uploaded) && payload.uploaded.length > 0;
    if (useClawMode && session && taskId) {
      await resumeClawTask({
        accessToken: session.accessToken,
        sessionId: session.sessionId,
        taskId,
        payload,
      });
    } else if (rid) {
      // 上传后 step_retry 不重放全流程，无需冻结快照（冻结会挡住 sync_inputs 的即时刷新）
      const curDoc = sduiDocRef.current;
      if (curDoc && !isUploadResume) {
        frozenProgressRef.current = extractProgressFromSdui(curDoc).progress ?? 0;
        frozenSnapshotRef.current = curDoc;
        setFrozenDoc(curDoc);
        updateSkillRun({ ...extractProgressFromSdui(curDoc), phase: 'running', hitlType: null });
      }
      await resumeRun(skillId, rid, payload);
      // 立即给左侧 SkillRunBanner 反馈：HITL 已提交，恢复 running
      updateSkillRun({ phase: 'running', hitlType: null });
      // 上传 step_retry 走同 run 队列切换，后端 SSE 可无缝续订；勿 bump epoch 以免错过 sdui 推送
      // 其余 full_restart 会新建队列，旧 EventSource 追不上 → bump epoch 强制重订阅
      if (!isUploadResume) {
        setStreamEpoch(e => e + 1);
      }
    } else {
      throw new Error('无活动 run，无法提交');
    }
  }, [useClawMode, session, taskId, activeRunId, skillId, storeRun]);

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
    clearSkillHitl(skillId);
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
    try {
      if (action.kind === 'post_user_message') {
        const text = action.text;
        if (text.startsWith('/start_') || text.startsWith('/retry_')) {
          await handleStart();
        } else if (text.startsWith('/resume_')) {
          await doResume({});
        } else if (text.startsWith('/view_')) {
          // TODO: 打开报告预览
        } else if (text.startsWith('/intent ')) {
          // zhgk：3D 机房下钻预选意图
          await handleIntent(text.slice('/intent '.length).trim());
        } else if (text === '/work') {
          setViewMode('work');
        } else if (text === '/overview') {
          setViewMode('overview');
        } else if (skillId === 'system_design') {
          // system_design：根据当前态路由自由文本（启动 / 重试 / HITL 续跑 / full_restart 携带指令）
          const isIdleNow = useClawMode ? !taskId : !runId;
          const prog = sduiDocRef.current ? extractProgressFromSdui(sduiDocRef.current) : {};
          const hasHitl = sduiDocRef.current ? !!findNodeById(sduiDocRef.current.root, 'hitl-card') : false;
          if (isIdleNow) {
            await handleStart();
          } else if (prog.phase === 'error') {
            await doResume({ text, choice: text });
          } else if (hasHitl) {
            await doResume({ choice: text, text });
          } else {
            // input_check 完成后无 HITL 卡（step_retry 仅重跑检查步）· 仍须 full_restart 携带用户指令
            await doResume({ text, choice: text });
            const rid = activeRunId ?? (storeRun?.skillId === skillId ? storeRun.runId : null);
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
          // zhgk / guihua / device_install：非命令的自由文本交给左栏会话框
          dispatchRailSend(text);
        }
      } else if (action.kind === 'open_preview') {
        setPreviewPath(action.path);
      } else if (action.kind === 'reset_session') {
        void handleResetSession();
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : '操作失败';
      console.error('[SDUI] action error:', e);
      updateSkillRun({ phase: 'error', errorMsg: msg });
      setError(msg);
    }
  }, [handleStart, doResume, handleResetSession, handleIntent, useClawMode, taskId, runId, skillId, activeRunId, storeRun]);

  // ── 在线编辑型 HITL 提交（resume · rows 由 skill.apply_resume_payload 写回 project）──
  const handleRowsSubmit = useCallback(async (rows: Record<string, unknown>[], _stepId?: string) => {
    await doResume({ rows });
  }, [doResume]);

  // ── run-patch 轻量补丁（任务进展保存 / 返回上一步等 · 不重跑 LangGraph）──────────
  const handleRunPatch = useCallback(async (payload: Record<string, unknown>) => {
    if (!activeRunId) return;
    await runPatchRun(skillId, activeRunId, payload);
  }, [activeRunId, skillId]);

  useEffect(() => {
    if (skillId === 'system_design') void ensureAgentBase(skillId);
  }, [skillId]);

  const handleUpload = useCallback(async (
    files: FileList,
    _purpose?: string,
    _stepId?: string,
    slotTag?: string,
    slotLabel?: string,
  ) => {
    const arr = Array.from(files);
    const kinds = arr.map(f => resolveUploadSlotTag(slotTag, slotLabel, f.name));
    const labels = arr.map(() => (slotLabel?.trim() ? slotLabel.trim() : ''));
    if (kinds.some(k => !k)) {
      throw new Error('无法识别输入件类型，请从对应槽位（如「项目信息收集表」）点击「上传」');
    }
    const rid = activeRunId ?? (storeRun?.skillId === skillId ? storeRun.runId : null);
    try {
      const result = await uploadBatch(skillId, arr, [], kinds, rid, labels);
      if (skillId === 'system_design') {
        const staleMsg = staleSystemDesignUploadMessage(result);
        if (staleMsg) throw new Error(staleMsg);
      }
      const failed = (result.uploaded ?? []).filter(u => u.ok === false);
      if (failed.length) {
        const msg = failed.map(f => String(f.error || f.filename || '未知文件')).join('；');
        throw new Error(`上传失败：${msg}`);
      }
      const saved = (result.uploaded ?? []).filter(u => u.ok !== false && u.path);
      const uploadDir = String(result.upload_dir || result.data_root || result.system_design_root || '');
      if (saved.length && uploadDir) {
        console.info('[SDUI] uploaded to', uploadDir, saved.map(u => u.path).join(', '));
      }
      if (!saved.length && (result.uploaded ?? []).length) {
        throw new Error('上传未落盘，请确认 Agent 已重启并加载最新 system_design 配置');
      }
      // 双保险：run-patch sync 推送 SDUI（upload/batch 已 sync 时幂等）
      if (rid) {
        try {
          await runPatchRun(skillId, rid, { action: 'sync_inputs' });
        } catch {
          // upload/batch 可能已 sync；忽略
        }
        const snap = await fetchUiSnapshot(skillId, rid);
        if (snap) {
          postUploadEpochRef.current = Date.now();
          setPostUploadDoc(snap);
        }
      } else if (saved.length) {
        // 无 run_id 时至少提示落盘路径（文件已在 upload_dir）
        console.warn('[SDUI] uploaded without run_id — 请启动 run 后刷新页面以更新槽位状态');
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
      setTimeout(() => {
        void (async () => {
          await doResume({ uploaded: arr.map(f => f.name) });
          // step_retry 异步完成后再拉 /ui，刷新左栏「输入件检查完成 / 选择规划任务」会话气泡
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
      }, HITL_HOLD_MS);
    }
    // zhgk / guihua / device_install：上传后统一续跑；system_design 仅在「输入件准备」HITL 内续跑（上方已处理），其余只 sync
    if (skillId !== 'system_design') {
      await doResume({ uploaded: arr.map(f => f.name) });
    }
  }, [skillId, doResume, activeRunId, storeRun]);

  const handleChoiceSubmit = useCallback(async (value: string, _stepId?: string) => {
    // 组件已显示「已提交」确认态 → 先 hold 再推进，保证确认态可见一段时间
    await new Promise(r => setTimeout(r, HITL_HOLD_MS));
    await doResume({ choice: value });
  }, [doResume]);

  // ── HITL 提升到左侧会话框 ─────────────────────────────────────────────────
  // sduiDoc 出现 hitl-card → 连同 resume 回调写入 skillHitlStore；
  // 左侧 SkillRunBanner 据此渲染可交互卡。无 HITL / 卸载时清除。
  // 在线编辑卡（hitl-edit-card）默认留在右侧大盘，仅 meta.route_hitl_edit==='chat' 才移交。
  useEffect(() => {
    if (!effectiveSduiDoc || !activeRunId) { clearSkillHitl(skillId); return; }
    const card = findNodeById(effectiveSduiDoc.root, 'hitl-card')
      ?? (routeHitlEdit === 'chat' ? findNodeById(effectiveSduiDoc.root, 'hitl-edit-card') : null);
    if (card) {
      setSkillHitl({
        skillId, runId: activeRunId, node: card,
        onChoiceSubmit: handleChoiceSubmit,
        onUpload: handleUpload,
        onAction: (action) => { void handleAction(action); },
      });
    } else if (!frozenDoc && !frozenSnapshotRef.current) {
      clearSkillHitl(skillId);
    }
  }, [effectiveSduiDoc, frozenDoc, activeRunId, skillId, handleChoiceSubmit, handleUpload, handleAction, routeHitlEdit]);

  useEffect(() => () => clearSkillHitl(skillId), [skillId]);  // 卸载清理

  // ── 会话流（AIDA 助手）提升到左侧会话框（system_design 交付台）────────────
  useEffect(() => {
    if (!usesDeliveryWorkbench) { clearSkillConversation(skillId); return; }
    if (!effectiveSduiDoc || !activeRunId) { clearSkillConversation(skillId); return; }
    const conv = findNodeById(effectiveSduiDoc.root, 'sd-conversation');
    if (conv) {
      setSkillConversation({
        skillId, runId: activeRunId,
        node: ensureConversationErrorBubble(conv, effectiveSduiDoc),
        runtime: {
          runId: activeRunId,
          skillId,
          onAction: (action) => { void handleAction(action); },
          onUpload: handleUpload,
          onChoiceSubmit: handleChoiceSubmit,
        },
      });
    } else {
      clearSkillConversation(skillId);
    }
  }, [usesDeliveryWorkbench, effectiveSduiDoc, sduiDoc, activeRunId, skillId, handleAction, handleUpload, handleChoiceSubmit]);

  useEffect(() => () => clearSkillConversation(skillId), [skillId]);

  // ── SDUI 运行时 ──────────────────────────────────────────────────────────
  const runtime: SduiRuntime = {
    runId: activeRunId,
    skillId,
    onAction: (action) => { void handleAction(action); },
    onUpload: handleUpload,
    onChoiceSubmit: handleChoiceSubmit,
    onRowsSubmit: (rows, stepId) => { void handleRowsSubmit(rows, stepId); },
    onRunPatch: handleRunPatch,
    streamEpoch,
  };

  // ── 渲染 ────────────────────────────────────────────────────────────────
  const isIdle = useClawMode ? !taskId : !runId;
  if (isIdle && !starting) {
    return (
      <div style={{ height: '100%', overflow: 'auto' }}>
        <IdleScreen skillId={skillId} title={title} description={description} onStart={() => { void handleStart(); }} loading={starting} />
        {nextModule && <NextModuleButton label={nextModule.label} onClick={() => navigate(nextModule.to)} />}
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
        {usesDeliveryWorkbench && !!displayDoc?.meta?.error && (
          <div style={{ marginBottom: 12, padding: 12, background: 'var(--c-danger-soft)', borderRadius: 'var(--r-md)', color: 'var(--c-danger-text)', fontSize: 'var(--fs-13)' }}>
            {String(displayDoc.meta.error)}
          </div>
        )}
        {error && (
          <div style={{ marginBottom: 12, padding: 12, background: 'var(--c-danger-soft)', borderRadius: 'var(--r-md)', color: 'var(--c-danger-text)', fontSize: 'var(--fs-13)' }}>
            {error}
          </div>
        )}
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
      {nextModule && <NextModuleButton label={nextModule.label} onClick={() => navigate(nextModule.to)} />}
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
