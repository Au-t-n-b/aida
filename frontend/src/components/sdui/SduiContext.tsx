/**
 * SDUI 运行时 Context — 为 Button/FilePicker/ChoiceCard 等交互节点提供 intent 回调。
 * 消费方：SduiNodeView 内的交互节点；提供方：SurveyAgentScreen。
 */
import { createContext, useContext } from 'react';
import type { SduiAction } from '@/lib/sdui';

export interface SduiRuntime {
  runId: string | null;
  onAction: (action: SduiAction) => void;
  onUpload: (files: FileList, purpose: string, stepId?: string) => void;
  onChoiceSubmit: (value: string, stepId?: string) => void;
  /** 字段型 HITL 提交：把表单 payload 回传 /resume。 */
  onFormSubmit?: (payload: Record<string, unknown>, stepId?: string) => void;
  /** 可编辑 DataTable 提交：把编辑后的行回传 /resume（payload={rows}）。可选 —— 不支持的提供方不实现。 */
  onRowsSubmit?: (rows: Record<string, unknown>[], stepId?: string) => void;
  /** run-patch 轻量补丁（任务进展保存、返回上一步等）。 */
  onRunPatch?: (payload: Record<string, unknown>) => Promise<void>;
  /** resume 后自增，用于编辑表解除 submitted 冻结 */
  streamEpoch?: number;
}

const defaultRuntime: SduiRuntime = {
  runId: null,
  onAction: () => {},
  onUpload: () => {},
  onChoiceSubmit: () => {},
};

export const SduiRuntimeContext = createContext<SduiRuntime>(defaultRuntime);

export function useSduiRuntime(): SduiRuntime {
  return useContext(SduiRuntimeContext);
}
