/**
 * SdSkillStepCard — 部署调测单步引导卡（左侧会话流内，每节点一张）
 */
import { SduiNodeView } from '@/components/sdui/SduiNodeView';
import { SduiRuntimeContext } from '@/components/sdui/SduiContext';
import type { SkillStepMsg } from '@/lib/skillStepFeed';
import { dispatchSdAction } from '@/lib/skillStepFeed';
import { useSkillHitlStore } from '@/lib/skillHitlStore';
import { useCommissionBusy } from '@/lib/commissionBusyStore';

const SKILL_LABELS: Record<string, string> = {
  software_deployment: '部署调测',
};

export function SdSkillStepCard({ step }: { step: SkillStepMsg }) {
  const hitl = useSkillHitlStore();
  const busy = useCommissionBusy();
  const hitlMatchesStep =
    hitl?.skillId === step.skillId
    && (
      !hitl.stepKey
      || hitl.stepKey === step.stepKey
      || hitl.stepKey === 'commission_scope'
    );
  const scopeBusy = busy.active && busy.kind === 'scope' && step.stepKey === 'commission_scope';
  const importBusy = busy.active && busy.kind === 'import' && step.stepKey === 'toolkit_import';
  const commandBusy = busy.active && busy.kind === 'command' && step.stepKey !== 'commission_scope';
  const showHitl = step.status === 'active'
    && hitlMatchesStep
    && !!hitl
    && !scopeBusy
    && !importBusy
    && !commandBusy;

  const done = step.status === 'done';
  const failed = step.status === 'failed';
  const running = step.status === 'active' && (step.phase === 'running' || scopeBusy || importBusy || commandBusy);
  const awaitingHitl = !failed && !running && (showHitl || step.phase === 'hitl');
  const badge = failed
    ? '失败'
    : done
      ? '已完成 ✓'
      : running
        ? '执行中…'
        : awaitingHitl
          ? '待你确认'
          : '执行中…';
  const badgeTone = failed ? 'error' : done ? 'done' : running ? 'running' : awaitingHitl ? 'hitl' : 'running';

  return (
    <div className="zhgk-card" style={{ marginTop: 8, opacity: running ? 0.92 : 1 }}>
      <div className="zhgk-card-head">
        <span className="zhgk-card-title">
          {step.stepNum > 0 ? `${step.stepNum}. ` : ''}{step.stepTitle}
        </span>
        <span className={`zhgk-card-badge ${badgeTone}`}>{badge}</span>
      </div>

      <div className="zhgk-card-info" style={{ padding: '4px 10px 8px' }}>
        {failed ? (
          <>
            <span className="zhgk-card-curstep" style={{ color: 'var(--red-700)' }}>
              ✗ 本步执行失败
            </span>
            {step.errorMessage ? (
              <div style={{
                marginTop: 6, padding: '8px 10px', fontSize: 12, lineHeight: 1.5,
                color: '#991b1b', background: 'rgba(239,68,68,.06)',
                border: '1px solid rgba(220,38,38,.2)', borderRadius: 6,
              }}>
                {step.errorMessage}
              </div>
            ) : null}
            <button
              type="button"
              className="a-btn primary"
              style={{ marginTop: 8 }}
              onClick={() => dispatchSdAction({
                kind: 'post_user_message',
                text: `/retry_step_${step.stepKey}`,
              })}
            >
              重试本步
            </button>
          </>
        ) : done ? (
          <span className="zhgk-card-curstep" style={{ color: 'var(--green-700)' }}>
            ✓ {SKILL_LABELS[step.skillId] ?? step.skillId} · 本步已完成
          </span>
        ) : running ? (
          <span className="zhgk-card-curstep" style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <i style={{
              width: 12, height: 12, borderRadius: '50%',
              border: '2px solid #3551d8', borderTopColor: 'transparent',
              display: 'inline-block', animation: 'spin .8s linear infinite',
            }} />
            {busy.label ? `正在处理 · ${busy.label}…` : '正在执行本步，请稍候…'}
          </span>
        ) : awaitingHitl && !showHitl ? (
          <span className="zhgk-card-curstep">交互卡加载中…</span>
        ) : (
          <span className="zhgk-card-curstep">请在下方确认后继续推进</span>
        )}
      </div>

      {showHitl && hitl && (
        <div style={{ margin: '0 10px 10px' }}>
          <SduiRuntimeContext.Provider
            value={{
              runId: hitl.runId,
              onAction: () => {},
              onUpload: hitl.onUpload,
              onChoiceSubmit: hitl.onChoiceSubmit,
              onFormSubmit: hitl.onFormSubmit,
              onRowsSubmit: () => {},
            }}
          >
            <SduiNodeView node={hitl.node} />
          </SduiRuntimeContext.Provider>
        </div>
      )}

      {step.status === 'active' && step.phase === 'hitl' && !showHitl && !running && (
        <div style={{
          margin: '0 10px 10px', padding: '8px 10px', fontSize: 12, color: '#92400e',
          background: 'rgba(251,191,36,.06)', border: '1px solid rgba(217,119,6,.2)', borderRadius: 6,
        }}>
          交互卡加载中…
        </div>
      )}
    </div>
  );
}
