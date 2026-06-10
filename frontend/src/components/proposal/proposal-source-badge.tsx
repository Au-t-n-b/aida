const SOURCE_LABEL: Record<string, string> = {
  BOQ: '自动解析',
  HLD: '人工录入',
  人工: '人工录入',
};

export function SourceBadge({ source }: { source: string }) {
  if (!source || source === '—') {
    return <span className="text-slate-400">—</span>;
  }
  const label = SOURCE_LABEL[source] ?? source;
  const tone =
    label === '自动解析' ? 'green'
    : label === '人工录入' ? 'amber'
    : 'gray';
  return (
    <span className={`data-source-badge tone-${tone}`}>
      <span className="data-source-dot" />
      {label}
    </span>
  );
}

export function HwBadge({ isHW }: { isHW: boolean }) {
  return (
    <span className={`data-source-badge tone-${isHW ? 'green' : 'gray'}`}>
      <span className="data-source-dot" />
      {isHW ? '是' : '否'}
    </span>
  );
}
