/* 带说明的 KPI 卡片 */
import type { ReactNode } from 'react';

export function EvalStat({
  label,
  value,
  hint,
  valueStyle,
}: {
  label: string;
  value: ReactNode;
  /** 计算方法 + 含义（显示在数值下方） */
  hint?: string;
  valueStyle?: React.CSSProperties;
}) {
  return (
    <div className="jn-stat">
      <div className="jn-stat-k">{label}</div>
      <div className="jn-stat-v" style={valueStyle}>{value}</div>
      {hint ? <div className="jn-stat-h">{hint}</div> : null}
    </div>
  );
}
