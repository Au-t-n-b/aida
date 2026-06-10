'use client';

/* VersionBar · 跨页复用的版本号 + 草稿 + 确认 + 历史回看 控制条
 *
 * 5.27 早会拍板（AM-36 / AM-37 / AM-38）：
 *   - 版本号自动 +0.1 递增（一位小数）
 *   - 保存草稿 / 确认 两按钮，放右上角
 *   - 老版本下拉切换 + 只读模式（切到非最新版时全字段禁用）
 *
 * 用法：
 *   <VersionBar
 *     versions={['v0.1', 'v0.2', 'v0.3']}        // 历史版本数组（按时间升序）
 *     currentVersion="v0.3"                       // 当前选中版
 *     onSelectVersion={(v) => setCurrentVersion(v)}
 *     onSaveDraft={() => ...}                     // 草稿不改版本号
 *     onConfirm={() => ...}                       // 确认 → 版本号 +0.1
 *     dirty={hasUnsavedChanges}                   // 是否有未保存改动
 *   />
 *
 * 父组件需要把 `isReadonly = currentVersion !== versions[versions.length - 1]`
 * 透传到所有输入字段，禁用编辑（一处约束）。
 */

import { useState } from 'react';

const IcCheck = () => (
  <svg width={11} height={11} viewBox="0 0 12 12" fill="none">
    <path d="M2 6.5 L5 9 L10 3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="square" fill="none" />
  </svg>
);
const IcLock = () => (
  <svg width={10} height={10} viewBox="0 0 12 12" fill="none">
    <rect x="3" y="5.5" width="6" height="5" stroke="currentColor" strokeWidth="1" fill="none" />
    <path d="M4 5.5 V3.5 a2 2 0 0 1 4 0 V5.5" stroke="currentColor" strokeWidth="1" fill="none" />
  </svg>
);

/** 计算下一个版本号 v0.3 → v0.4；v0.9 → v1.0；v9.9 → v10.0 */
export function bumpVersion(v: string): string {
  const m = String(v || '').match(/^v?(\d+)\.(\d+)$/);
  if (!m) return 'v0.1';
  const major = parseInt(m[1]!, 10);
  const minor = parseInt(m[2]!, 10);
  if (minor + 1 < 10) return `v${major}.${minor + 1}`;
  return `v${major + 1}.0`;
}

export interface VersionBarProps {
  versions?: string[];
  currentVersion?: string;
  onSelectVersion?: (v: string) => void;
  onSaveDraft?: () => void;
  onConfirm?: () => void;
  /** 5.27 SVG 校正：保存/确认按钮下沉到 ActionFooter；这里默认隐藏。
   *  旧调用方仍传 onSaveDraft/onConfirm 不影响兼容性，UI 中不渲染按钮。 */
  showActionButtons?: boolean;
  /** R-9 · 手动指定版本号（可选） */
  onConfirmWithVersion?: (v: string) => void;
  dirty?: boolean;
  /** 可选：自定义按钮文字 */
  draftLabel?: string;
  confirmLabel?: string;
}

export default function VersionBar({
  versions = [],
  currentVersion,
  onSelectVersion,
  onSaveDraft,
  onConfirm,
  showActionButtons = false,
  onConfirmWithVersion,
  dirty = false,
  draftLabel = '保存草稿',
  confirmLabel = '确认 · 版本 +0.1',
}: VersionBarProps) {
  const latest = versions[versions.length - 1];
  const isReadonly = currentVersion !== latest;
  const [pickerOpen, setPickerOpen] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);
  const [manualValue, setManualValue] = useState('');

  return (
    <div className={`vbar${isReadonly ? ' is-readonly' : ''}`}>
      {/* 版本号下拉 */}
      <div className="vbar-version">
        <button
          type="button"
          className="vbar-version-btn"
          onClick={() => setPickerOpen(v => !v)}
          title="切换历史版本（只读）"
        >
          <span className="vbar-version-tag">{currentVersion}</span>
          {isReadonly && <span className="vbar-readonly-chip"><IcLock /> 只读</span>}
          <span className="vbar-caret">▾</span>
        </button>
        {pickerOpen && (
          <div className="vbar-picker" onMouseLeave={() => setPickerOpen(false)}>
            <div className="vbar-picker-head">历史版本（{versions.length}）</div>
            {[...versions].reverse().map(v => (
              <button
                key={v}
                type="button"
                className={`vbar-picker-row${v === currentVersion ? ' on' : ''}${v === latest ? ' latest' : ''}`}
                onClick={() => { onSelectVersion?.(v); setPickerOpen(false); }}
              >
                <span className="vbar-picker-v">{v}</span>
                {v === latest && <span className="vbar-picker-badge">最新</span>}
                {v === currentVersion && <span className="vbar-picker-check"><IcCheck /></span>}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 状态指示 */}
      <div className="vbar-status">
        {isReadonly ? (
          <span className="vbar-status-readonly">查看历史版本 · 不可编辑</span>
        ) : dirty ? (
          <span className="vbar-status-dirty">● 有未保存改动</span>
        ) : (
          <span className="vbar-status-clean">已保存</span>
        )}
      </div>

      <div className="vbar-spacer" />

      {/* 草稿 / 确认 / 手动版本号 三按钮
       * 5.27 SVG 校正：保存草稿 / 确认 下沉到 ActionFooter（主区底部 fixed），
       *               这里只保留「手动版本号」popover —— 切版本属于版本号操作语义。
       * 仅 showActionButtons={true} 时旧调用方法仍能拿到 3 按钮（向后兼容）。*/}
      {!isReadonly && (
        <>
          {showActionButtons && (
            <button
              type="button"
              className="btn sm ghost"
              onClick={onSaveDraft}
              disabled={!dirty}
              title="保存为草稿 · 不改版本号"
            >
              {draftLabel}
            </button>
          )}
          {/* R-9 · 手动指定版本号 */}
          {onConfirmWithVersion && (
            <div className="vbar-manual-wrap">
              <button
                type="button"
                className="btn sm ghost"
                onClick={() => setManualOpen(o => !o)}
                title="手动指定版本号（5.27 SVG 决策）"
              >
                ⚙ 手动版本号
              </button>
              {manualOpen && (
                <div className="vbar-manual-pop" onMouseLeave={() => setManualOpen(false)}>
                  <div className="vbar-manual-head">指定版本号</div>
                  <input
                    type="text"
                    value={manualValue}
                    placeholder={`如 v1.5 · 当前 ${currentVersion}`}
                    onChange={e => setManualValue(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter' && /^v?\d+\.\d+$/.test(manualValue)) {
                        const norm = manualValue.startsWith('v') ? manualValue : 'v' + manualValue;
                        onConfirmWithVersion(norm);
                        setManualOpen(false);
                        setManualValue('');
                      }
                    }}
                    className="vbar-manual-input"
                    autoFocus
                  />
                  <button
                    type="button"
                    className="btn sm primary"
                    disabled={!/^v?\d+\.\d+$/.test(manualValue)}
                    onClick={() => {
                      const norm = manualValue.startsWith('v') ? manualValue : 'v' + manualValue;
                      onConfirmWithVersion(norm);
                      setManualOpen(false);
                      setManualValue('');
                    }}
                  >
                    应用
                  </button>
                  <div className="vbar-manual-hint">格式 v1.5；回车确认</div>
                </div>
              )}
            </div>
          )}
          {showActionButtons && (
          <button
            type="button"
            className="btn sm primary"
            onClick={onConfirm}
            title={`确认后版本变成 ${bumpVersion(currentVersion ?? '')}`}
          >
            <IcCheck /> {confirmLabel}
          </button>
          )}
        </>
      )}
      {isReadonly && (
        <button
          type="button"
          className="btn sm primary"
          onClick={() => latest && onSelectVersion?.(latest)}
        >
          回到最新版编辑 →
        </button>
      )}
    </div>
  );
}
