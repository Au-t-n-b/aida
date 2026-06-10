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
