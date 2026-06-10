// @ts-nocheck
'use client';

import { useState } from 'react';
import { IconClose, IconTable, IconPdf, IconImage, IconFile } from './icons';
import { Skeleton } from './primitives';

/* ── RailTabs ── */
export function RailTabs({ mode, onChange, hasFile = false }) {
  const tabs = [
    { key: 'reference', label: '参考资料' },
    { key: 'preview', label: '预览', disabled: !hasFile },
  ];
  return (
    <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', background: 'var(--surface)' }}>
      {tabs.map(tab => (
        <button
          key={tab.key}
          disabled={tab.disabled}
          onClick={() => !tab.disabled && onChange(tab.key)}
          style={{
            flex: 1, padding: '8px 0', fontSize: 'var(--text-xs)', fontWeight: 400,
            borderBottom: mode === tab.key ? '2px solid var(--c-text-muted)' : '2px solid transparent',
            color: mode === tab.key ? 'var(--c-text)' : tab.disabled ? 'var(--text-tertiary)' : 'var(--text-secondary)',
            background: 'none', border: 'none',
            cursor: tab.disabled ? 'not-allowed' : 'pointer',
            transition: 'color .12s',
          }}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

/* ── XLSXPreview ── */
function XLSXPreview({ file }) {
  const rows = [
    { no: 1, item: 'Catalyst 9300-48P', qty: 12, risk: '低', status: '在途' },
    { no: 2, item: 'Nexus 9508 Chassis', qty: 2, risk: '高', status: '待采购' },
    { no: 3, item: '25G SFP28 模块', qty: 96, risk: '中', status: '库存' },
    { no: 4, item: '单模光纤 LC-LC', qty: 240, risk: '低', status: '在途' },
    { no: 5, item: 'UPS 10kVA', qty: 4, risk: '中', status: '待采购' },
  ];
  const riskTone = { 低: 'green', 中: 'amber', 高: 'red' };

  return (
    <div style={{ overflow: 'auto' }} className="claw-scroll">
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--text-xs)' }}>
        <thead>
          <tr style={{ background: 'var(--zinc-50)' }}>
            {['#', '设备名称', '数量', '风险', '状态'].map(h => (
              <th key={h} style={{ padding: '5px 6px', textAlign: 'left', fontWeight: 400, color: 'var(--c-text-muted)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap' }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} style={{ borderBottom: '1px solid var(--zinc-100)' }}>
              <td style={{ padding: '4px 6px', color: 'var(--c-text-muted)', fontFamily: 'var(--font-mono)' }}>{r.no}</td>
              <td style={{ padding: '4px 6px', color: 'var(--c-text)' }}>{r.item}</td>
              <td style={{ padding: '4px 6px', color: 'var(--c-text-muted)', fontFamily: 'var(--font-mono)', textAlign: 'right' }}>{r.qty}</td>
              <td style={{ padding: '4px 6px', color: 'var(--c-text-muted)' }}>{r.risk}</td>
              <td style={{ padding: '4px 6px', color: 'var(--c-text-muted)' }}>{r.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── MDPreview ── */
function MDPreview({ file }) {
  return (
    <div style={{ padding: '12px', fontSize: 'var(--text-sm)', lineHeight: 1.7, color: 'var(--c-text)' }}>
      <h3 style={{ fontSize: 'var(--text-base)', fontWeight: 500, marginBottom: 8, color: 'var(--c-text)' }}>
        {file.name.replace(/\.[^.]+$/, '')}
      </h3>
      <p style={{ color: 'var(--c-text-muted)', marginBottom: 10 }}>
        本文档包含项目交付的关键基线信息和技术规格说明。请在实施前仔细阅读并确认所有参数。
      </p>
      <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: 500, marginBottom: 4, paddingLeft: 8, borderLeft: '2px solid var(--c-border-strong)' }}>
        关键指标
      </h4>
      <ul style={{ paddingLeft: 16, color: 'var(--c-text-muted)', marginBottom: 10 }}>
        <li>覆盖节点数：1,247 个</li>
        <li>关键路径工期：47 天</li>
        <li>设备清单总数：486 台</li>
      </ul>
      <div style={{ background: 'var(--c-bg-soft)', borderRadius: 'var(--radius-sm)', padding: '6px 10px', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--c-text-muted)', border: '1px solid var(--c-border)' }}>
        {`// 示例配置片段\ninterface GigabitEthernet0/0\n  ip address 192.168.1.1 255.255.255.0\n  no shutdown`}
      </div>
    </div>
  );
}

/* ── PDFPreview ── */
function PDFPreview({ file }) {
  return (
    <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <IconPdf size={14} color="var(--c-text-muted)" />
        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--c-text-muted)' }}>{file.name}</span>
      </div>
      {/* A4 skeleton */}
      <div style={{ background: 'var(--c-surface)', border: '1px solid var(--c-border)', borderRadius: 4, padding: 12 }}>
        <Skeleton width="60%" height={10} style={{ marginBottom: 8 }} />
        <Skeleton width="100%" height={6} style={{ marginBottom: 4 }} />
        <Skeleton width="95%" height={6} style={{ marginBottom: 4 }} />
        <Skeleton width="88%" height={6} style={{ marginBottom: 12 }} />
        <Skeleton width="40%" height={8} style={{ marginBottom: 8 }} />
        <Skeleton width="100%" height={6} style={{ marginBottom: 4 }} />
        <Skeleton width="100%" height={6} style={{ marginBottom: 4 }} />
        <Skeleton width="72%" height={6} style={{ marginBottom: 12 }} />
        <Skeleton width="100%" height={60} radius={4} style={{ marginBottom: 8 }} />
        <Skeleton width="100%" height={6} style={{ marginBottom: 4 }} />
        <Skeleton width="80%" height={6} />
      </div>
    </div>
  );
}

/* ── ImagePreview ── */
function ImagePreview({ file }) {
  const dots = [
    { x: 30, y: 40, label: '散热隐患', tone: 'red' },
    { x: 65, y: 25, label: '机柜满载', tone: 'amber' },
    { x: 50, y: 70, label: '走线凌乱', tone: 'amber' },
  ];
  return (
    <div style={{ padding: 12 }}>
      <div style={{ position: 'relative', paddingBottom: '75%', background: 'var(--c-bg-soft)', borderRadius: 'var(--radius-md)', border: '1px solid var(--c-border)', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 6 }}>
          <IconImage size={28} color="var(--c-text-faint)" />
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--c-text-muted)' }}>{file.name}</span>
        </div>
        {/* annotation dots */}
        {dots.map((dot, i) => (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: `${dot.x}%`, top: `${dot.y}%`,
              transform: 'translate(-50%, -50%)',
            }}
          >
            <div style={{
              width: 16, height: 16, borderRadius: '50%',
              background: 'var(--c-text-muted)',
              border: '2px solid var(--c-surface)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 9, color: 'white', cursor: 'pointer',
            }}>
              {i + 1}
            </div>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
        {dots.map((dot, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 'var(--text-xs)' }}>
            <div style={{ width: 14, height: 14, borderRadius: '50%', background: 'var(--c-text-muted)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9, flexShrink: 0 }}>{i + 1}</div>
            <span style={{ color: 'var(--c-text-muted)' }}>{dot.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── ReferencePreview ── */
export function ReferencePreview({ file, onClose }) {
  if (!file) return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 8 }}>
      <IconFile size={28} color="var(--zinc-300)" />
      <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>选择文件以预览</span>
    </div>
  );

  const ext = (file.name || '').split('.').pop().toLowerCase();
  const isXlsx = ['xlsx', 'xls', 'csv'].includes(ext);
  const isPdf = ext === 'pdf';
  const isImg = ['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext);

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 12px', borderBottom: '1px solid var(--c-border)' }}>
        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--c-text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {file.name}
        </span>
        <button onClick={onClose} style={{ flexShrink: 0, padding: 2, cursor: 'pointer', background: 'none', border: 'none', color: 'var(--text-tertiary)' }}>
          <IconClose size={12} />
        </button>
      </div>
      <div style={{ flex: 1, overflow: 'auto' }} className="claw-scroll">
        {isXlsx && <XLSXPreview file={file} />}
        {isPdf && <PDFPreview file={file} />}
        {isImg && <ImagePreview file={file} />}
        {!isXlsx && !isPdf && !isImg && <MDPreview file={file} />}
      </div>
    </div>
  );
}

/* ── RightRail ── */
export function RightRail({ previewFile, onClosePreview, referenceItems = [] }) {
  const [tab, setTab] = useState('reference');

  return (
    <aside style={{ width: 'var(--rail-w)', borderLeft: '1px solid var(--border)', background: 'var(--surface)', display: 'flex', flexDirection: 'column', overflow: 'hidden', flexShrink: 0 }}>
      <RailTabs mode={previewFile ? 'preview' : tab} onChange={setTab} hasFile={!!previewFile} />
      {previewFile ? (
        <ReferencePreview file={previewFile} onClose={onClosePreview} />
      ) : (
        <div style={{ flex: 1, overflow: 'auto', padding: 12 }} className="claw-scroll">
          {referenceItems.length === 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 8 }}>
              <IconFile size={24} color="var(--zinc-300)" />
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>暂无参考资料</span>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {referenceItems.map((item, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, padding: '6px 8px', borderRadius: 'var(--radius-md)', border: '1px solid var(--c-border)', background: 'var(--c-surface)' }}>
                  <div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--c-text)' }}>{item.title}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </aside>
  );
}
