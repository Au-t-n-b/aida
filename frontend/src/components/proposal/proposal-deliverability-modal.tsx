'use client';

import { DELIVER_RISKS } from './proposal-data';

export function DeliverabilityModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  if (!open) return null;

  return (
    <div className="aida-modal-backdrop" onClick={onClose}>
      <div
        className="aida-modal deliver-modal"
        role="dialog"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="aida-modal-head">
          <span>预案可交付性研判</span>
          <button type="button" className="aida-modal-close" onClick={onClose}>
            ✕
          </button>
        </div>
        <div className="aida-modal-body">
          <p className="mb-3 text-xs text-slate-500">
            核心决策：方案可交付性 · 四域指数：① 组网 ② 设备 ③ 服务 ④ 验收。确认后可一键创建跟踪任务。
          </p>
          <div className="deliver-risk-list">
            {DELIVER_RISKS.map((r, i) => (
              <div key={i} className={`deliver-risk-row level-${r.level}`}>
                <div className="deliver-risk-title">{r.title}</div>
                <div className="deliver-risk-action">建议：{r.action}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="aida-modal-foot">
          <button type="button" className="btn sm ghost" onClick={onClose}>
            关闭
          </button>
          <button
            type="button"
            className="btn sm"
            onClick={() => {
              if (typeof window !== 'undefined') window.location.href = '/plan?view=risk';
            }}
          >
            查看风险表
          </button>
          <button
            type="button"
            className="btn sm primary"
            onClick={() => {
              if (typeof window !== 'undefined') {
                window.dispatchEvent(
                  new CustomEvent('aida:progress', {
                    detail: {
                      role: 'ai',
                      body: '可交付性研判完成 · 已为 4 项风险创建跟踪任务，责任人已通知。',
                      chips: ['跟踪任务 +4', '已通知责任人'],
                      actions: [
                        { label: '查看任务列表', kind: 'primary', icon: 'Eye' },
                        { label: '查看风险预警', kind: 'ghost' },
                      ],
                    },
                  }),
                );
              }
              onClose();
            }}
          >
            确认 · 创建跟踪任务
          </button>
        </div>
      </div>
    </div>
  );
}
