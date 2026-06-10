// @ts-nocheck
'use client';

import { useState, useEffect } from 'react';
import { ICON_MAP } from './icons';
import { Badge, Button, Panel, Stepper, KPI, FileChip, Progress, Skeleton, StreamingText } from './primitives';
import { EmbedView } from './embed-views';

/* ── track status helpers ── */
function trackStatus(phase, trackIndex) {
  if (phase === 0) return 'waiting';
  if (phase === 1) return trackIndex === 0 ? 'running' : 'waiting';
  if (phase === 2) return trackIndex < 2 ? 'running' : 'waiting';
  if (phase === 3) return 'done';
  return 'done';
}

export function buildTracks(schema, phase) {
  return schema.tracks.map((t, i) => ({
    ...t,
    status: phase === 0 ? 'waiting' : phase >= 4 ? 'done' : phase === 1 && i === 0 ? 'running' : phase >= 2 && i <= 1 ? (phase >= 3 ? 'done' : 'running') : phase >= 3 && i === 2 ? 'running' : 'waiting',
    progress: phase === 0 ? 0 : phase >= 4 ? 100 : i < phase ? 100 : i === phase - 1 ? 65 : 0,
    logs: phase > i ? [
      `[${t.skill}] 初始化完成`,
      `[${t.skill}] 处理中 (37%)...`,
      `[${t.skill}] 处理中 (72%)...`,
      `[${t.skill}] 完成`,
    ] : [],
    kpis: phase > i ? [
      { label: '处理量', value: Math.floor(100 + i * 150 + phase * 80), unit: '条' },
      { label: '耗时', value: `${12 + i * 8}s` },
    ] : [],
  }));
}

/* ── ModuleHeader ── */
export function ModuleHeader({ schema, stage, project = '华南区 DC 扩容', onOpenDetails }) {
  const Icon = ICON_MAP[schema.iconName];
  const stages = schema.steps;
  const currentIdx = stages.indexOf(stage.charAt(0).toUpperCase() + stage.slice(1));
  const safeIdx = currentIdx < 0 ? 0 : currentIdx;

  return (
    <div style={{ padding: 'var(--sp-3) var(--pad-panel)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 12, background: 'var(--surface)', flexShrink: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
        {Icon && <Icon size={16} color="var(--accent)" />}
        <div>
          <div style={{ fontWeight: 700, fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>{schema.name}</div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>{project}</div>
        </div>
      </div>
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <Stepper steps={stages} currentIndex={safeIdx} />
      </div>
      {onOpenDetails && (
        <Button variant="ghost" size="sm" onClick={onOpenDetails}>详情</Button>
      )}
    </div>
  );
}

/* ── ParallelTrack ── */
export function ParallelTrack({ track }) {
  const statusColor = track.status === 'running' ? 'var(--accent)' : track.status === 'done' ? 'var(--green-600)' : track.status === 'error' ? 'var(--red-600)' : 'var(--zinc-300)';
  const dotClass = `claw-dot claw-dot--${track.status === 'running' ? 'running' : track.status === 'done' ? 'done' : 'wait'}`;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '160px 1fr 1fr', gap: 8, alignItems: 'start', padding: '6px 0', borderBottom: '1px solid var(--zinc-100)' }}>
      {/* Status column */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className={dotClass} />
          <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-primary)' }}>{track.label}</span>
        </div>
        <div style={{ fontSize: '10px', color: 'var(--text-tertiary)', paddingLeft: 14 }}>{track.skill}</div>
        {track.status !== 'waiting' && (
          <div style={{ paddingLeft: 14 }}>
            <Progress value={track.progress} status={track.status === 'running' ? 'running' : track.status === 'done' ? 'done' : 'default'} height={3} />
          </div>
        )}
      </div>

      {/* KPI column */}
      <div style={{ display: 'flex', gap: 12 }}>
        {track.status === 'waiting' ? (
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>等待中…</div>
        ) : track.kpis.map((kpi, i) => (
          <div key={i}>
            <div style={{ fontSize: '10px', color: 'var(--text-tertiary)' }}>{kpi.label}</div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{kpi.value}{kpi.unit}</div>
          </div>
        ))}
      </div>

      {/* Log column */}
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: 1, maxHeight: 56, overflow: 'hidden' }}>
        {track.status === 'waiting' ? null : track.logs.slice(-3).map((log, i) => (
          <div key={i} style={{ opacity: i < track.logs.length - 1 ? 0.5 : 1 }}>{log}</div>
        ))}
        {track.status === 'running' && <div className="claw-caret" style={{ fontSize: 10 }} />}
      </div>
    </div>
  );
}

/* ── FileRail ── */
export function FileRail({ files = [], onPreview, title = '文件', output = false, badge }) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
        <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)' }}>{title}</span>
        {badge && <Badge tone={output ? 'green' : 'default'} size="xs">{badge}</Badge>}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {files.map((f, i) => (
          <FileChip key={i} file={f} onClick={() => onPreview?.(f)} output={output} />
        ))}
      </div>
    </div>
  );
}

/* ── GoldenMetrics ── */
export function GoldenMetrics({ metrics = [] }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, padding: 'var(--pad-panel)', borderBottom: '1px solid var(--border)' }}>
      {metrics.map((m, i) => (
        <KPI key={i} {...m} />
      ))}
    </div>
  );
}

/* ── SynthesisBlock ── */
export function SynthesisBlock({ schema, phase }) {
  const paragraphs = schema.synthesisParagraphs || [];
  const showCount = phase >= 3 ? paragraphs.length : phase >= 2 ? 1 : 0;

  if (showCount === 0) return (
    <div style={{ padding: 'var(--pad-panel)', display: 'flex', flexDirection: 'column', gap: 6 }}>
      <Skeleton width="40%" height={10} />
      <Skeleton height={6} />
      <Skeleton height={6} />
      <Skeleton width="70%" height={6} />
    </div>
  );

  return (
    <div style={{ padding: 'var(--pad-panel)', display: 'flex', flexDirection: 'column', gap: 12 }}>
      {paragraphs.slice(0, showCount).map((p, i) => (
        <div key={i}>
          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--accent)', marginBottom: 4, borderLeft: '2px solid var(--accent)', paddingLeft: 6 }}>{p.title}</div>
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
            {i === showCount - 1 && phase < 4
              ? <StreamingText text={p.text} speed={20} showCaret />
              : p.text}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── GuidePlaceholder ── */
export function GuidePlaceholder({ schema, onStart }) {
  const Icon = ICON_MAP[schema.iconName];
  return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--sp-8)' }}>
      <div style={{ textAlign: 'center', maxWidth: 360 }}>
        {Icon && (
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}>
            <div style={{ width: 56, height: 56, borderRadius: 'var(--radius-xl)', background: 'var(--accent-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Icon size={28} color="var(--accent)" />
            </div>
          </div>
        )}
        <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, marginBottom: 6 }}>{schema.name}</h2>
        <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', marginBottom: 20, lineHeight: 1.6 }}>{schema.subtitle}</p>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginBottom: 20 }}>
          {schema.skillNames?.map((s, i) => (
            <Badge key={i} tone="accent" size="sm">{s}</Badge>
          ))}
        </div>
        <Button variant="primary" size="md" onClick={onStart}>开始 {schema.name}</Button>
      </div>
    </div>
  );
}

/* ── DeliverablesPanel ── */
export function DeliverablesPanel({ schema, onPreview }) {
  return (
    <Panel title="交付物" subtitle={`共 ${schema.outputs?.length || 0} 个文件`}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        {(schema.outputs || []).map((f, i) => (
          <FileChip key={i} file={f} onClick={() => onPreview?.(f)} output />
        ))}
      </div>
    </Panel>
  );
}

/* ── WarRoomWorkbench (the main workbench area) ── */
export function WarRoomWorkbench({ schema, stage, phase, onPreview, onStart }) {
  const stageKey = stage?.toLowerCase() || 'guide';
  const tracks = buildTracks(schema, phase);
  const metrics = schema.metricsByStage?.[stageKey] || schema.metricsByStage?.execute || [];

  if (stageKey === 'guide') {
    return <GuidePlaceholder schema={schema} onStart={onStart} />;
  }

  return (
    <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column' }} className="claw-scroll">
      {/* KPI strip */}
      {metrics.length > 0 && <GoldenMetrics metrics={metrics} />}

      <div style={{ flex: 1, padding: 'var(--pad-panel)', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* Embed view (topology/gantt) */}
        {schema.embed && (stageKey === 'execute' || stageKey === 'synthesize' || stageKey === 'finish') && (
          <Panel title={schema.embed === 'topology' ? '网络拓扑' : '项目甘特图'} padding="8px">
            <EmbedView kind={schema.embed} height={220} />
          </Panel>
        )}

        {/* Parallel tracks */}
        {(stageKey === 'execute' || stageKey === 'synthesize') && (
          <Panel title="并行任务" subtitle={`${tracks.filter(t => t.status === 'done').length}/${tracks.length} 完成`} padding="8px 12px">
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {tracks.map((t, i) => <ParallelTrack key={i} track={t} />)}
            </div>
          </Panel>
        )}

        {/* Synthesis */}
        {(stageKey === 'synthesize' || stageKey === 'finish') && (
          <Panel title="分析摘要" padding="0">
            <SynthesisBlock schema={schema} phase={phase} />
          </Panel>
        )}

        {/* Deliverables */}
        {stageKey === 'finish' && (
          <DeliverablesPanel schema={schema} onPreview={onPreview} />
        )}

        {/* Upload files */}
        {stageKey === 'upload' && (
          <Panel title="待上传文件" subtitle="将文件拖放到此处或点击选择" padding="12px">
            <div style={{ border: '2px dashed var(--border)', borderRadius: 'var(--radius-lg)', padding: 24, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 'var(--text-sm)' }}>
              <div style={{ marginBottom: 8 }}>📎 拖放文件到这里</div>
              <div style={{ fontSize: 'var(--text-xs)' }}>支持 Excel、PDF、图片格式</div>
            </div>
            {schema.files?.length > 0 && (
              <div style={{ marginTop: 10 }}>
                <FileRail files={schema.files} onPreview={onPreview} title="示例文件" />
              </div>
            )}
          </Panel>
        )}

        {/* Decide - HITL shown in chat, workbench shows scenario table */}
        {stageKey === 'decide' && schema.scenarioTable && (
          <Panel title="场景评估预览">
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--text-xs)' }}>
              <thead>
                <tr>
                  {['场景', '评分', '风险', '备注'].map(h => (
                    <th key={h} style={{ padding: '4px 8px', textAlign: 'left', fontWeight: 600, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {schema.scenarioTable.map((row, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--zinc-100)' }}>
                    <td style={{ padding: '5px 8px', fontWeight: 500 }}>{row.scenario}</td>
                    <td style={{ padding: '5px 8px', fontFamily: 'var(--font-mono)' }}>{row.score}</td>
                    <td style={{ padding: '5px 8px' }}><Badge tone={row.tone} size="xs">{row.risk}</Badge></td>
                    <td style={{ padding: '5px 8px', color: 'var(--text-tertiary)' }}>{row.notes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
        )}
      </div>
    </div>
  );
}
