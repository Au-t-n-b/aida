import { useCallback, useEffect, useState } from 'react';
import {
  CONTINGENCY_ANCHOR,
  deriveContingencyRisks,
  publishContingencyFindings,
  type DeriveContingencyParams,
} from './ontology-api';
import { mapGenerationToView } from './contingency-view';
import type { OntologyView } from '@/types/domain';

export interface ContingencyOntologyState {
  view: OntologyView | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

/** 挂载时调一次 deriveContingencyRisks，把后端真实派生结果映射成脑图视图模型。
 * 失败（如 :8011 未启动）返回 error；调用方据此渲染错误态 + 重试。 */
export function useContingencyOntology(
  params: DeriveContingencyParams = {},
): ContingencyOntologyState {
  const [view, setView] = useState<OntologyView | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  // 逐字段取值，避免字面量 params 对象每次渲染都触发 effect。
  const { planId, projectKey, assessmentId, referenceDate } = params;
  const effectivePlanId = planId || CONTINGENCY_ANCHOR.planId;
  const effectiveProjectKey = projectKey || CONTINGENCY_ANCHOR.projectKey;
  const effectiveAssessmentId = assessmentId || CONTINGENCY_ANCHOR.assessmentId;

  useEffect(() => {
    const controller = new AbortController();
    let alive = true;
    setLoading(true);
    setError(null);
    deriveContingencyRisks(
      {
        planId: effectivePlanId,
        projectKey: effectiveProjectKey,
        assessmentId: effectiveAssessmentId,
        referenceDate,
      },
      controller.signal,
    )
      .then((result) => {
        if (!alive) return;
        setView(mapGenerationToView(result));
        setLoading(false);
        void publishContingencyFindings(
          {
            planId: result.planId || effectivePlanId,
            projectKey: result.projectKey || effectiveProjectKey,
            assessmentId: result.assessmentId || effectiveAssessmentId,
            referenceDate,
          },
          controller.signal,
        ).catch((err: unknown) => {
          if (!alive || controller.signal.aborted) return;
          console.warn('[contingency] publish findings failed', err);
        });
      })
      .catch((err: unknown) => {
        if (!alive || controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : '本体服务连接失败');
        setLoading(false);
      });
    return () => {
      alive = false;
      controller.abort();
    };
  }, [effectivePlanId, effectiveProjectKey, effectiveAssessmentId, referenceDate, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { view, loading, error, reload };
}
