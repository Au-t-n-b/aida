'use client';

/* ActionFooter · 主区底部 fixed 操作条 (5.27 SVG 校正)
 *
 * SVG Image 4 显示：保存草稿 / 确认 应该挂在主区**底部 fixed**，
 * 不是混在顶部的 VersionBar 里。
 *
 * 用法：在 design / plan / sandbox / preview 等版本控制页的最后挂上：
 *   <ActionFooter
 *     dirty={hasUnsavedChanges}
 *     onSaveDraft={handleSaveDraft}
 *     onConfirm={handleConfirm}
 *     confirmLabel="确认 · 版本 +0.1"
 *     readonly={isViewingHistoricVersion}
 *   />
 *
 * 视觉：fixed 在视口底部，跨越主区宽度（不覆盖左导和会话框）
 */

const IcCheck = () => (
  <svg width={12} height={12} viewBox="0 0 12 12" fill="none">
    <path d="M2 6.5 L5 9 L10 3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="square" fill="none" />
  </svg>
);

export interface ActionFooterProps {
  dirty?: boolean;
  onSaveDraft?: () => void;
  onConfirm?: () => void;
  draftLabel?: string;
  confirmLabel?: string;
  readonly?: boolean;
  /** 可选：左侧 hint 文字 */
  hint?: string;
  /** 可选：覆盖确认按钮的 className（用于深色按钮等场景）*/
  confirmClass?: string;
}

export default function ActionFooter({
  dirty = false,
  onSaveDraft,
  onConfirm,
  draftLabel = '保存草稿',
  confirmLabel = '确认',
  readonly = false,
  hint,
  confirmClass,
}: ActionFooterProps) {
  if (readonly) {
    return (
      <div className="action-footer readonly">
        <span className="action-footer-hint">查看历史版本 · 不可编辑</span>
      </div>
    );
  }
  return (
    <div className={`action-footer${dirty ? ' is-dirty' : ''}`}>
      <span className="action-footer-hint">
        {hint || (dirty ? '● 有未保存改动' : '已保存')}
      </span>
      <div className="action-footer-spacer" />
      <button
        type="button"
        className="btn sm ghost"
        onClick={onSaveDraft}
        disabled={!dirty}
        title="保存为草稿 · 不改版本号"
      >
        {draftLabel}
      </button>
      <button
        type="button"
        className={confirmClass ?? 'btn sm primary'}
        onClick={onConfirm}
      >
        {!confirmClass && <IcCheck />} {confirmLabel}
      </button>
    </div>
  );
}
