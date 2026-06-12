/**
 * useSduiStream — 订阅任意 skill 的 SSE 流，接收 sdui 事件更新 SduiDocument。
 *
 * skill 参数化：所有端点为 /agent/<skillId>/*（不再写死 zhgk）——
 * 新业务场景 Skill（guihua/install/...）复用此 hook + SkillAgentScreen，无需复制。
 * 首屏快照 + 流式增量（每个 node_update / step_retry 后后端推一棵完整 sdui 树）。
 */
import { useEffect, useRef, useState } from 'react';
import type { SduiDocument, SduiNode } from '@/lib/sdui';
import { parseSduiDocument } from '@/lib/sdui';

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

/** 是否已有执行态 UI 面（进度环 / Stepper / HITL 卡）。*/
function hasExecutionSurface(doc: SduiDocument): boolean {
  let found = false;
  walkSduiNodes(doc.root, (node) => {
    if (found) return;
    const id = (node as { id?: string }).id ?? '';
    if (id === 'hitl-card' || id === 'hitl-edit-card') { found = true; return; }
    if (node.type === 'DonutChart' && node.centerValue) {
      const n = parseInt(node.centerValue, 10);
      if (!isNaN(n) && n > 0) found = true;
    }
    if (node.type === 'Stepper') {
      if (node.steps.some(s => s.status === 'done' || s.status === 'running')) found = true;
    }
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

/** full_restart 重连时拒绝比当前更低的进度快照（与后端 display_state 双保险）。*/
function mergeSduiDoc(prev: SduiDocument | null, next: SduiDocument): SduiDocument {
  if (!prev) return next;
  const pPrev = extractSduiProgress(prev);
  const pNext = extractSduiProgress(next);
  if (pPrev >= 0 && pNext >= 0 && pNext < pPrev) return prev;
  if (hasExecutionSurface(prev) && isIdleLikeSduiDoc(next)) return prev;
  if (pPrev > 0 && pNext < 0 && !hasExecutionSurface(next)) return prev;
  return next;
}

import { pushRunLog, clearRunLog, type RunLogEvent } from '@/lib/runLogStore';

// 后端 aida/agent 地址：默认本地直连；服务器部署经 VITE_AGENT_BASE 注入（编译期）。
const AGENT_BASE = import.meta.env.VITE_AGENT_BASE || 'http://127.0.0.1:7401';

/**
 * @param epoch  重订阅令牌。HITL resume 后后端会新建队列 + 新 task（full_restart），
 *   而旧 task 早已往旧队列推过 None 哨兵——靠 EventSource 自动重连追新队列既慢又不稳。
 *   调用方在 resume 成功后自增 epoch，即可强制销毁旧 ES、重拉快照、对准新队列，0 延迟刷新。
 */
export function useSduiStream(skillId: string, runId: string | null, epoch = 0): SduiDocument | null {
  const [doc, setDoc] = useState<SduiDocument | null>(null);
  const esRef = useRef<EventSource | null>(null);
  // 只在 runId 真正变化时清空日志；epoch 自增（resume/full_restart）保留已有气泡，
  // 以便下发确认后追加 sn_generate 等新节点的日志。
  const clearedRunIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!runId) {
      setDoc(null);
      return;
    }

    if (clearedRunIdRef.current !== runId) {
      clearRunLog(runId);
      clearedRunIdRef.current = runId;
    }

    let cancelled = false;

    // 1. 先拉快照（run 已完成 / 晚接入 SSE / resume 重订阅时保底）
    fetchUiSnapshot(skillId, runId).then(snap => {
      if (!cancelled && snap) setDoc(prev => mergeSduiDoc(prev, snap));
    }).catch(() => { /* ignore */ });

    // 2. 同步订阅 SSE 增量更新（后续事件会覆盖快照，保持最新）
    const es = new EventSource(`${AGENT_BASE}/agent/${skillId}/stream/${runId}`);
    esRef.current = es;

    const handleSdui = (e: MessageEvent) => {
      try {
        const raw = typeof e.data === 'string' ? JSON.parse(e.data) : e.data;
        const result = parseSduiDocument(raw);
        if (result.ok) {
          setDoc(prev => mergeSduiDoc(prev, result.doc));
        }
      } catch {
        // ignore parse errors
      }
    };

    const handleRunLog = (e: MessageEvent) => {
      try {
        const raw = typeof e.data === 'string' ? JSON.parse(e.data) : e.data;
        pushRunLog(runId, raw as RunLogEvent);
      } catch {
        // ignore parse errors
      }
    };

    es.addEventListener('sdui', handleSdui as EventListenerOrEventListenerObject);
    es.addEventListener('run_log', handleRunLog as EventListenerOrEventListenerObject);
    es.addEventListener('error', () => {
      // connection dropped; SSE will auto-reconnect
    });

    return () => {
      cancelled = true;
      es.removeEventListener('sdui', handleSdui as EventListenerOrEventListenerObject);
      es.removeEventListener('run_log', handleRunLog as EventListenerOrEventListenerObject);
      es.close();
      esRef.current = null;
    };
  }, [skillId, runId, epoch]);

  return doc;
}

// ── REST helpers（均按 skillId 拼端点）─────────────────────────────────────────

export interface StartReq {
  project_code?: string;
  project_name?: string;
  scenario_run?: string;

  /** zhgk：从 3D 机房入口下钻时预选意图（写入 initial project） */
  intent?: string;
}

/** 启动一次 run。默认值由后端 skill.initial_project 兜（如 zhgk 的 K1903），前端不写死。 */
export async function startRun(skillId: string, req: StartReq = {}): Promise<string> {
  const res = await fetch(`${AGENT_BASE}/agent/${skillId}/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`start failed: ${res.status}`);
  const data = await res.json() as { run_id: string };
  return data.run_id;
}

/** 清空 skill 工作区产物与运行态（保留 Input），重置会话时调用。 */
export async function resetWorkspace(skillId: string): Promise<void> {
  const res = await fetch(`${AGENT_BASE}/agent/${skillId}/reset-workspace`, {
    method: 'POST',
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `reset-workspace failed: ${res.status}`);
  }
}

export async function runPatchRun(skillId: string, runId: string, payload: Record<string, unknown> = {}): Promise<void> {
  const res = await fetch(`${AGENT_BASE}/agent/${skillId}/run-patch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ run_id: runId, payload }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `run-patch failed: ${res.status}`);
  }
}

export async function resumeRun(skillId: string, runId: string, payload: Record<string, unknown> = {}): Promise<void> {
  await fetch(`${AGENT_BASE}/agent/${skillId}/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ run_id: runId, payload }),
  });
}

/**
 * HITL 批量上传：走 /upload/batch，后端按文件名自动推断 kind。
 * 注意：不要用 /upload + kind=<purpose>，purpose 形如 hitl_scene_filter 不是合法 kind，会 500。
 * needFiles 仅用于返回对齐的齐备检查（可选）；真正的门禁是 resume 时 step.check_inputs 重校验。
 */
export async function uploadBatch(skillId: string, files: File[], needFiles: string[] = []): Promise<void> {
  const form = new FormData();
  for (const f of files) form.append('files', f);
  for (const n of needFiles) form.append('need', n);
  const res = await fetch(`${AGENT_BASE}/agent/${skillId}/upload/batch`, { method: 'POST', body: form });
  if (!res.ok) throw new Error(`upload failed: ${res.status}`);
}

export async function fetchUiSnapshot(skillId: string, runId: string): Promise<SduiDocument | null> {
  try {
    const res = await fetch(`${AGENT_BASE}/agent/${skillId}/ui/${runId}`);
    if (!res.ok) return null;
    const raw = await res.json();
    const result = parseSduiDocument(raw);
    return result.ok ? result.doc : null;
  } catch {
    return null;
  }
}
