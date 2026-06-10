/**
 * useClawTaskSdui — 订阅 ClawManager 任务事件流，从 payload.sdui 提取 SduiDocument。
 *
 * 与 useSduiStream 的区别：
 *   - useSduiStream：直连 aida/agent :7401 SSE（本地开发模式）
 *   - useClawTaskSdui：订阅 ClawManager /tasks/{id}/events SSE（生产容器模式）
 *     后端 aida_runner.py 把每步的 SDUI 树打包进 TaskEvent.payload.sdui 推给前端
 *
 * SDUI 渲染组件（SduiNodeView 等）两种模式下完全复用，零改动。
 */
import { useEffect, useRef, useState } from 'react';
import type { SduiDocument } from '@/lib/sdui';
import { parseSduiDocument } from '@/lib/sdui';
import { subscribeTaskEvents, type TaskSnapshotResponse } from '@/lib/claw-manager-client';

export type ClawTaskState = 'idle' | 'running' | 'hitl' | 'succeeded' | 'failed';

export interface ClawTaskSduiResult {
  doc: SduiDocument | null;
  taskState: ClawTaskState;
  hitl: Record<string, unknown> | null;  // HITL 暂停时的详情（step/type/need 等）
  progress: number | null;
  step: string | null;
  runId: string | null;  // 容器内 aida/agent 的 run_id，用于文件上传等操作
}

export function useClawTaskSdui(
  taskId: string | null,
  accessToken: string,
): ClawTaskSduiResult {
  const [doc, setDoc] = useState<SduiDocument | null>(null);
  const [taskState, setTaskState] = useState<ClawTaskState>('idle');
  const [hitl, setHitl] = useState<Record<string, unknown> | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [step, setStep] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!taskId || !accessToken) {
      setDoc(null);
      setTaskState('idle');
      return;
    }

    setTaskState('running');

    const es = subscribeTaskEvents({
      accessToken,
      taskId,
      onEvent: (event: TaskSnapshotResponse & { seq?: number }) => {
        // 提取 SDUI 树
        const sduiRaw = event.payload?.sdui;
        if (sduiRaw) {
          const result = parseSduiDocument(sduiRaw);
          if (result.ok) setDoc(result.doc);
        }

        // 提取 HITL 状态
        const hitlRaw = event.payload?.hitl;
        if (hitlRaw && typeof hitlRaw === 'object') {
          const h = hitlRaw as Record<string, unknown>;
          if (h.step) {
            setHitl(h);
            setTaskState('hitl');
          } else {
            setHitl(null);
          }
        }

        // 提取容器内 run_id（用于文件上传到 aida/agent）
        const rid = event.payload?.run_id;
        if (typeof rid === 'string') setRunId(rid);

        // 进度 / step
        if (event.progress != null) setProgress(event.progress);
        if (event.step) setStep(event.step);

        // 终态
        if (event.state === 'succeeded') setTaskState('succeeded');
        if (event.state === 'failed') setTaskState('failed');
      },
      onError: () => {
        // EventSource 断线自动重连，静默处理
      },
    });

    esRef.current = es;

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [taskId, accessToken]);

  return { doc, taskState, hitl, progress, step, runId };
}
