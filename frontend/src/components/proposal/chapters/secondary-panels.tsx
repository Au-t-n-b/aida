'use client';

import {
  ProposalChapterCard,
  ProposalDataTable,
  ProposalDataTableBody,
  ProposalDataTableHead,
} from '../primitives';
import {
  COMPUTE_DEVICES,
  INTEL_PARTS,
  PBI_LIST,
  SERVICE_CONFIG,
} from '../proposal-data';
import { SourceBadge } from '../proposal-source-badge';
import { CHAPTER_TARGETS, chapterKeyFromName } from '../proposal-navigation';

export function DtobChapter() {
  return (
    <ProposalChapterCard
      id="panel-dtob"
      title="DTOB 加工摘要"
      variant="secondary"
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-700">设备 · DTOB 加工后</h3>
          <ProposalDataTable compact>
            <ProposalDataTableHead>
              <tr>
                <th>设备型号</th>
                <th>产品编码</th>
                <th>版本</th>
                <th className="num">数量</th>
                <th>来源</th>
              </tr>
            </ProposalDataTableHead>
            <ProposalDataTableBody>
              {COMPUTE_DEVICES.slice(0, 4).map((d, i) => (
                <tr key={i}>
                  <td>{d.model}</td>
                  <td className="num font-mono text-xs">{d.code}</td>
                  <td className="num font-mono text-xs">{d.ver}</td>
                  <td className="num">{d.qty}</td>
                  <td><SourceBadge source={d.source} /></td>
                </tr>
              ))}
              {INTEL_PARTS.slice(0, 2).map((p, i) => (
                <tr key={`i-${i}`}>
                  <td>{p.name}</td>
                  <td className="num font-mono text-xs">{p.code}</td>
                  <td>—</td>
                  <td>—</td>
                  <td><SourceBadge source={p.source} /></td>
                </tr>
              ))}
            </ProposalDataTableBody>
          </ProposalDataTable>
        </div>
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-700">服务 · DTOB 加工后</h3>
          <ProposalDataTable compact>
            <ProposalDataTableHead>
              <tr>
                <th>大类</th>
                <th>细项</th>
                <th>交付界面</th>
                <th>来源</th>
              </tr>
            </ProposalDataTableHead>
            <ProposalDataTableBody>
              {SERVICE_CONFIG.slice(0, 6).map((s, i) => (
                <tr key={i}>
                  <td>{s.major}</td>
                  <td>{s.item}</td>
                  <td>{s.channel}</td>
                  <td><SourceBadge source={s.source} /></td>
                </tr>
              ))}
            </ProposalDataTableBody>
          </ProposalDataTable>
        </div>
      </div>
    </ProposalChapterCard>
  );
}

export function PbiChapter({
  pbiOpen,
  onTogglePbi,
}: {
  pbiOpen: boolean;
  onTogglePbi: () => void;
}) {
  return (
    <ProposalChapterCard
      id="panel-pbi"
      title="PBI · 产品 Backlog（TD 手动维护）"
      variant="secondary"
      headerExtra={
        <button type="button" className="btn-link text-sm" onClick={onTogglePbi}>
          {pbiOpen ? '收起' : '展开 / 编辑'}
        </button>
      }
    >
      {pbiOpen && (
        <ProposalDataTable compact>
          <ProposalDataTableHead>
            <tr>
              <th>PBI ID</th>
              <th>类型</th>
              <th>标题</th>
              <th>关联章节</th>
              <th>状态</th>
            </tr>
          </ProposalDataTableHead>
          <ProposalDataTableBody>
            {PBI_LIST.map((p) => (
              <tr key={p.id}>
                <td className="num font-mono text-xs">{p.id}</td>
                <td><span className={`status-pill ${p.tone}`}>{p.type}</span></td>
                <td>{p.title}</td>
                <td>{p.chapter}</td>
                <td>
                  <span className={`status-pill ${p.state === 'ok' ? 'green' : 'amber'}`}>
                    {p.state === 'ok' ? '已确认' : '待确认'}
                  </span>
                </td>
              </tr>
            ))}
          </ProposalDataTableBody>
        </ProposalDataTable>
      )}
    </ProposalChapterCard>
  );
}

type ChapterRow = { name: string; state: string; note?: string };

export function CompletenessChapter({
  snapLabel,
  chapters,
  onJump,
}: {
  snapLabel: string;
  chapters: ChapterRow[];
  onJump: (chapterKey: string) => void;
}) {
  return (
    <ProposalChapterCard
      id="panel-completeness"
      title={`本版完整性校验（${snapLabel}）`}
      variant="secondary"
    >
      <div className="jn-chapters">
        {chapters.map((c) => {
          const chapterKey = chapterKeyFromName(c.name);
          const t = CHAPTER_TARGETS[chapterKey];
          const jumpable = !!(t && t.anchor);
          return (
            <div
              key={c.name}
              className={`jn-chapter state-${c.state}${jumpable ? ' jumpable' : ''}`}
            >
              <span
                className="jn-chapter-name"
                onClick={() => jumpable && onJump(chapterKey)}
                style={jumpable ? { cursor: 'pointer' } : undefined}
                role={jumpable ? 'button' : undefined}
                tabIndex={jumpable ? 0 : undefined}
                onKeyDown={(e) => {
                  if (jumpable && (e.key === 'Enter' || e.key === ' ')) onJump(chapterKey);
                }}
              >
                {c.name}
              </span>
              <span className={`jn-chapter-state state-${c.state}`}>
                {c.state === 'ok' ? '齐备' : c.state === 'partial' ? '部分' : '缺失'}
              </span>
              {c.note && <div className="jn-chapter-note">{c.note}</div>}
            </div>
          );
        })}
      </div>
    </ProposalChapterCard>
  );
}
