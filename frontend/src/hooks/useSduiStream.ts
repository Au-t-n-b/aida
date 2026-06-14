/**

 * useSduiStream — 订阅任意 skill 的 SSE 流，接收 sdui 事件更新 SduiDocument。

 *

 * skill 参数化：所有端点为 /agent/<skillId>/*（不再写死 zhgk）——

 * 新业务场景 Skill（guihua/install/...）复用此 hook + SkillAgentScreen，无需复制。

 * 首屏快照 + 流式增量（每个 node_update / step_retry 后后端推一棵完整 sdui 树）。

 *

 * device_install 额外订阅 run_log 事件（RunLogFeed）；其它 skill 以 SSE 为权威来源，

 * 快照仅作首包到达前的保底（避免 resume 后旧快照覆盖含 meta.error 的最新树）。

 */

import { useEffect, useRef, useState } from 'react';
import type { SduiDocument, SduiNode } from '@/lib/sdui';
import { parseSduiDocument } from '@/lib/sdui';
import { pushRunLog, clearRunLog, type RunLogEvent } from '@/lib/runLogStore';

function walkSduiNodes(node: SduiNode, visit: (n: SduiNode) => void): void {
  visit(node);
  const ch = (node as { children?: SduiNode[] }).children;
  if (Array.isArray(ch)) ch.forEach(child => walkSduiNodes(child, visit));
}

/** 从 SDUI 树提取整体进度（DonutChart.centerValue）；无则 -1。*/
export function extractSduiProgress(doc: SduiDocument): number {
  let best = -1;
  walkSduiNodes(doc.root, (node) => {
    if (node.type === 'DonutChart' && node.centerValue) {
      const n = parseInt(node.centerValue, 10);
      if (!isNaN(n)) best = Math.max(best, n);
    }
  });
  return best;
}

/** 从 Stepper 提取已推进到的最远步骤序号；无 Stepper 则 -1。 */
function extractSduiStepRank(doc: SduiDocument): number {
  let best = -1;
  walkSduiNodes(doc.root, (node) => {
    if (node.type !== 'Stepper') return;
    node.steps.forEach((step, index) => {
      if (['done', 'completed', 'skipped', 'running', 'current', 'error'].includes(step.status)) {
        best = Math.max(best, index);
      }
    });
  });
  return best;
}

/** 是否已有执行态 UI 面（进度环 / Stepper / HITL 卡 / 多页签工作台）。*/
function hasExecutionSurface(doc: SduiDocument): boolean {
  let found = false;
  walkSduiNodes(doc.root, (node) => {
    if (found) return;
    const id = (node as { id?: string }).id ?? '';
    if (id === 'hitl-card' || id === 'hitl-edit-card' || id === 'completion-card') { found = true; return; }
    if (node.type === 'DonutChart' && node.centerValue) {
      const n = parseInt(node.centerValue, 10);
      if (!isNaN(n) && n > 0) found = true;
    }
    if (node.type === 'Stepper') {
      if (node.steps.some(s => s.status === 'done' || s.status === 'running')) found = true;
    }
    // TabGroup（如 guihua 三页签工作台）= 有实质执行内容，阻止 full_restart 期间被 idle 覆盖
    if (node.type === 'TabGroup') { found = true; return; }
  });
  return found;
}

/** idle 引导态：*-intro 节点，或 device_install 空根 suppress_idle_panel。*/
export function isIdleLikeSduiDoc(doc: SduiDocument): boolean {
  const meta = (doc.meta ?? {}) as Record<string, unknown>;
  if (meta.suppress_idle_panel) {
    const ch = (doc.root as { children?: SduiNode[] }).children;
    return !ch || ch.length === 0;
  }
  let intro = false;
  walkSduiNodes(doc.root, (node) => {
    const id = (node as { id?: string }).id ?? '';
    if (id.endsWith('-intro')) intro = true;
  });
  return intro;
}

/** 作业区已有可见节点（含仅 Stepper 的中间态，如设备安装重连首帧）。*/
function hasWorkbenchContent(doc: SduiDocument): boolean {
  const ch = (doc.root as { children?: SduiNode[] }).children;
  return Array.isArray(ch) && ch.length > 0;
}

/** full_restart 重连时拒绝比当前更低的进度快照（与后端 display_state 双保险）。*/
function mergeSduiDoc(prev: SduiDocument | null, next: SduiDocument): SduiDocument {
  if (!prev) return next;
  if (isErrorSduiDoc(next)) return next;
  const pPrev = extractSduiProgress(prev);
  const pNext = extractSduiProgress(next);
  const rPrev = extractSduiStepRank(prev);
  const rNext = extractSduiStepRank(next);
  if (rPrev >= 0 && rNext >= 0 && rNext < rPrev) return prev;
  if (pPrev >= 0 && pNext >= 0 && pNext < pPrev) return prev;
  if (isIdleLikeSduiDoc(next) && (hasExecutionSurface(prev) || hasWorkbenchContent(prev))) return prev;
  if (pPrev > 0 && pNext < 0 && !hasExecutionSurface(next)) return prev;
  return next;
}

function isErrorSduiDoc(doc: SduiDocument): boolean {
  return Boolean(doc.meta?.error);
}

export function isRunUnavailableDoc(doc: SduiDocument | null | undefined): boolean {
  return Boolean(doc?.meta?.run_unavailable);
}

function makeRunUnavailableDoc(skillId: string, runId: string, message: string): SduiDocument {
  return {
    schemaVersion: 1,
    type: 'SduiDocument',
    root: {
      type: 'Stack',
      id: 'run-unavailable-root',
      gap: 'md',
      children: [
        {
          type: 'Alert',
          tone: 'error',
          title: '运行已失效',
          message,
        },
      ],
    },
    meta: { skill: skillId, run_id: runId, phase: 'error', error: message, run_unavailable: true },
  };
}

import { ensureAgentBase } from '@/lib/agentBase';
import { agentBase } from '@/lib/runtimeBase';

// 后端 aida/agent 地址：默认同源反代；本地/演示可用 VITE_AGENT_BASE 覆盖。
// system_design 走 ensureAgentBase（可探测 7402+）；其余 skill / 旧调用点用此常量。
export const AGENT_BASE = agentBase();

const RUN_LOG_SKILLS = new Set(['device_install']);

export function useSduiStream(skillId: string, runId: string | null, epoch = 0): SduiDocument | null {

  const [doc, setDoc] = useState<SduiDocument | null>(null);

  const esRef = useRef<EventSource | null>(null);

  const clearedRunIdRef = useRef<string | null>(null);

  // 最近一次已应用的 SDUI 内容序列化（内容门控：相同则不重渲染，避免轮询/重发抖动）
  const lastDocJsonRef = useRef<string | null>(null);
  // close 后的轻量快照轮询定时器（替代 EventSource 自动重连，避免重连风暴打断交互）
  const pollTimerRef = useRef<number | null>(null);

  const useRunLog = RUN_LOG_SKILLS.has(skillId);



  useEffect(() => {

    if (!runId) {

      setDoc(null);

      return;

    }



    if (useRunLog && clearedRunIdRef.current !== runId) {

      clearRunLog(runId);

      clearedRunIdRef.current = runId;

    }



    let cancelled = false;

    let sseReceived = false;

    let es: EventSource | null = null;

    // 每次重订阅（runId / epoch 变化）重置内容门控与遗留轮询
    lastDocJsonRef.current = null;
    if (pollTimerRef.current != null) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }



    void (async () => {

      const base = await ensureAgentBase(skillId);

      if (cancelled) return;



      // 1. 先拉快照（run 已完成 / 晚接入 SSE / resume 重订阅时保底）
      fetchUiSnapshot(skillId, runId, base).then(snap => {

        if (cancelled) return;

        if (!snap) {

          setDoc(prev => {

            if (sseReceived || prev?.meta?.error) return prev;

            return null;

          });

          return;

        }

        // 快照经 mergeSduiDoc：full_restart 重连时拒绝比当前更低的进度（zhgk 防闪回）
        setDoc(prev => {

          if (sseReceived) return prev;

          if (prev?.meta?.error && !snap.meta?.error) return prev;

          return useRunLog ? snap : mergeSduiDoc(prev, snap);

        });

      }).catch(() => { /* ignore */ });



      es = new EventSource(`${base}/agent/${skillId}/stream/${runId}`);

      esRef.current = es;



      const handleSdui = (e: MessageEvent) => {

        try {

          const raw = typeof e.data === 'string' ? JSON.parse(e.data) : e.data;

          const result = parseSduiDocument(raw);

          if (result.ok) {

            sseReceived = true;

            // 内容门控：与上次应用的树相同则跳过（避免重发/快照导致整树重渲染、握碎交互）
            const json = JSON.stringify(result.doc);
            if (json === lastDocJsonRef.current) return;
            lastDocJsonRef.current = json;

            // SSE 增量经 mergeSduiDoc：与后端 display_state 双保险，防 full_restart 闪回低进度
            setDoc(prev => useRunLog ? result.doc : mergeSduiDoc(prev, result.doc));

          }

        } catch {

          // ignore parse errors

        }

      };



      const handleRunLog = (e: MessageEvent) => {

        if (!useRunLog) return;

        try {

          const raw = typeof e.data === 'string' ? JSON.parse(e.data) : e.data;

          pushRunLog(runId, raw as RunLogEvent);

        } catch {

          // ignore parse errors

        }

      };



      const handleStreamError = (e: MessageEvent) => {

        if (!e.data) return;

        try {

          const raw = typeof e.data === 'string' ? JSON.parse(e.data) : e.data;

          const msg = String(raw?.error ?? raw?.message ?? '执行失败');

          sseReceived = true;

          setDoc(prev => ({
            schemaVersion: prev?.schemaVersion ?? 1,
            type: 'SduiDocument' as const,
            root: prev?.root ?? { type: 'Stack', id: 'stream-error-root', gap: 'sm', children: [] },
            meta: { ...(prev?.meta ?? {}), skill: skillId, run_id: runId, phase: 'error', error: msg },
          }));

        } catch {

          // ignore parse errors

        }

      };



      // 「内容门控的轻量快照轮询」：整段订阅期间常驻运行（不依赖 close 事件时序）。
      // 后端 SSE 是分段的——run 跑到 HITL 暂停 / 结束就发 close 关连接，期间若错过
      // 增量（重订阅竞态、close 时序、冻结遮罩等）会导致界面停在旧态，需手动刷新。
      // 故每 2.5s 拉一次 /ui 快照兜底：内容变化（步骤推进 / 新 HITL 弹框）→ 自动 setDoc
      // 刷新；内容相同 → 不 setDoc、不重渲染，既不打断交互也不空耗。投影确定性保证
      // 同一状态序列化一致，不会误判抖动。
      const startSnapshotPoll = () => {
        if (pollTimerRef.current != null) return;
        pollTimerRef.current = window.setInterval(() => {
          if (cancelled) return;
          fetchUiSnapshot(skillId, runId, base).then(snap => {
            if (cancelled || !snap) return;
            const json = JSON.stringify(snap);
            if (json === lastDocJsonRef.current) return;  // 无变化：不触发重渲染
            lastDocJsonRef.current = json;
            setDoc(prev => useRunLog ? snap : mergeSduiDoc(prev, snap));
          }).catch(() => { /* ignore */ });
        }, 2500);
      };
      // 收到 close 主动 es.close() 终止 EventSource 自带的重连风暴（避免整树高频重渲染、
      // 握碎文件选择）；状态刷新交给常驻的快照轮询。
      const handleClose = () => {
        es?.close();
        if (esRef.current === es) esRef.current = null;
      };

      es.addEventListener('sdui', handleSdui as EventListenerOrEventListenerObject);

      if (useRunLog) {

        es.addEventListener('run_log', handleRunLog as EventListenerOrEventListenerObject);

      }

      // run 正常结束（done）后补拉一次快照，避免错过末尾增量（software_deployment）
      const handleDone = () => {
        fetchUiSnapshot(skillId, runId, base).then(snap => {
          if (!cancelled && snap) setDoc(prev => useRunLog ? snap : mergeSduiDoc(prev, snap));
        }).catch(() => { /* ignore */ });
      };

      es.addEventListener('done', handleDone as EventListenerOrEventListenerObject);

      es.addEventListener('error', handleStreamError as EventListenerOrEventListenerObject);

      es.addEventListener('close', handleClose as EventListenerOrEventListenerObject);

      es.onerror = () => {

        // 连接异常断开（网络抖动）→ 交给浏览器自动重连；run 正常结束由 close 事件终止。

      };

      // 常驻快照轮询：保证后端状态推进时界面自动刷新，无需手动刷新页面（内容门控防抖动）。
      startSnapshotPoll();

    })();


    return () => {

      cancelled = true;

      es?.close();

      esRef.current = null;

      if (pollTimerRef.current != null) {
        window.clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }

    };

  }, [skillId, runId, epoch, useRunLog]);



  return doc;

}



// ── REST helpers（均按 skillId 拼端点）─────────────────────────────────────────



export interface StartReq {

  project_code?: string;

  project_name?: string;

  scenario_run?: string;
  /** zhgk：从 3D 机房入口下钻时预选意图（写入 initial project） */
  intent?: string;
  /** system_design：NL 命令 / 自由文本 / 动作 */
  command?: string;
  text?: string;
  action?: string;
  /** software_deployment：Toolkit 前置满足时直达命令调测工作台 */
  entry_mode?: 'commission' | string;
}



/** 启动一次 run。默认值由后端 skill.initial_project 兜（如 zhgk 的 K1903），前端不写死。 */

export async function startRun(skillId: string, req: StartReq = {}): Promise<string> {

  const base = await ensureAgentBase(skillId);

  const res = await fetch(`${base}/agent/${skillId}/start`, {

    method: 'POST',

    headers: { 'Content-Type': 'application/json' },

    body: JSON.stringify(req),

  });

  if (!res.ok) throw new Error(await res.text());

  const data = await res.json();

  return data.run_id as string;

}

/** 清空 skill 工作区产物与运行态（保留 Input），重置会话时调用。 */
export async function resetWorkspace(skillId: string): Promise<void> {

  const base = await ensureAgentBase(skillId);

  const res = await fetch(`${base}/agent/${skillId}/reset-workspace`, {

    method: 'POST',

    headers: { 'Content-Type': 'application/json' },

    body: JSON.stringify({}),

  });

  if (!res.ok) throw new Error(await res.text());

}



export async function runPatchRun(skillId: string, runId: string, payload: Record<string, unknown> = {}): Promise<void> {

  const base = await ensureAgentBase(skillId);

  const res = await fetch(`${base}/agent/${skillId}/run-patch`, {

    method: 'POST',

    headers: { 'Content-Type': 'application/json' },

    body: JSON.stringify({ run_id: runId, payload }),

  });

  if (!res.ok) throw new Error(await res.text());

}

export async function resumeRun(
  skillId: string,
  runId: string,
  payload: Record<string, unknown> = {},
  fromStep?: string,
): Promise<void> {

  const base = await ensureAgentBase(skillId);

  await fetch(`${base}/agent/${skillId}/resume`, {

    method: 'POST',

    headers: { 'Content-Type': 'application/json' },

    body: JSON.stringify({
      run_id: runId,
      payload,
      ...(fromStep ? { from_step: fromStep } : {}),
    }),
  }).then(async (res) => {
    if (!res.ok) throw new Error(await res.text());
  });

}



export async function uploadBatch(

  skillId: string,

  files: File[],

  needFiles: string[] = [],

  kinds: string[] = [],

  runId?: string | null,

  slotLabels: string[] = [],

): Promise<{ uploaded: Array<Record<string, unknown>>; check: Record<string, unknown>; system_design_root?: string; upload_dir?: string; data_root?: string }> {

  const base = await ensureAgentBase(skillId);

  const form = new FormData();

  files.forEach(f => form.append('files', f));

  needFiles.forEach(n => form.append('need', n));

  kinds.forEach(k => form.append('kinds', k));

  slotLabels.forEach(l => form.append('slot_labels', l));

  if (runId) form.append('run_id', runId);

  const res = await fetch(`${base}/agent/${skillId}/upload/batch`, { method: 'POST', body: form });

  if (!res.ok) throw new Error(await res.text());

  return res.json();

}



export async function overrideOutputArtifact(

  skillId: string,

  file: File,

  targetPath: string,

  runId?: string | null,

): Promise<{ ok?: boolean; path?: string; size?: number; error?: string }> {

  const base = await ensureAgentBase(skillId);

  const form = new FormData();

  form.append('file', file);

  form.append('target_path', targetPath);

  if (runId) form.append('run_id', runId);

  const res = await fetch(`${base}/agent/${skillId}/artifact/override`, { method: 'POST', body: form });

  if (!res.ok) throw new Error(await res.text());

  return res.json();

}



export async function fetchUiSnapshot(skillId: string, runId: string, base?: string): Promise<SduiDocument | null> {

  const agentBase = base ?? await ensureAgentBase(skillId);

  try {

    const res = await fetch(`${agentBase}/agent/${skillId}/ui/${runId}`);

    if (!res.ok) {
      if (res.status === 404) {
        return makeRunUnavailableDoc(
          skillId,
          runId,
          '当前运行已不在后端内存中，通常是本地 Agent 重启导致。请刷新页面并重新开始本次流程。',
        );
      }
      return null;
    }

    const raw = await res.json();

    const result = parseSduiDocument(raw);

    return result.ok ? result.doc : null;

  } catch {

    return null;

  }

}

export type RunStatusSnapshot = {
  error?: string;
  steps?: Array<{ key?: string; status?: string }>;
};

export async function fetchRunStatus(
  skillId: string,
  runId: string,
): Promise<RunStatusSnapshot | null> {
  try {
    const res = await fetch(`${AGENT_BASE}/agent/${skillId}/status/${runId}`);
    if (!res.ok) return null;
    return await res.json() as RunStatusSnapshot;
  } catch {
    return null;
  }
}

export function runStepOutcome(
  state: RunStatusSnapshot | null | undefined,
  stepKey: string,
): 'pending' | 'running' | 'done' | 'error' {
  if (!state) return 'pending';
  if (state.error) return 'error';
  const rec = (state.steps ?? []).find(s => s.key === stepKey);
  if (!rec) return 'pending';
  if (rec.status === 'completed') return 'done';
  if (rec.status === 'failed') return 'error';
  if (rec.status === 'running') return 'running';
  return 'pending';
}
