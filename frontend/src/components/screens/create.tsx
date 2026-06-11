// @ts-nocheck
'use client';

/* /create — 项目创建向导
 * 4 步：填字段 → 上传文档 → OCC 审批模拟 → 项目空间激活
 * 严格对齐会议结论：
 *  - 字段不超过 5 项，proposal 自动回填
 *  - OCC 审批是合规闸门（数据出境风险）
 *  - 审批通过才能跳进 cockpit
 */

import { Fragment, useEffect, useRef, useState } from 'react';
import Link from '@/compat/link';

const STEPS = [
  { key: 'fields', label: '基本字段', desc: '名称 / 编码 / 场景 / PD·TD·PCM' },
  { key: 'docs', label: '文档摄取', desc: '售前工勘 / HLD / BOQ / CAD' },
  { key: 'occ', label: 'OCC 审批', desc: '数据出境合规闸门' },
  { key: 'active', label: '项目激活', desc: '跳转到项目孪生看板' },
];

/* 5.27 早会拍板：
 *   - 项目名称必填；编码非必填
 *   - Proposal ID 非必填；但 Proposal ID 与 项目编码 至少二选一
 *   - 场景 = 两组互斥（新增/扩容 + 推理/训练/训推）
 *   - 去掉 product/cluster（自动从 BOQ 解析）
 *   - 新增 PCM 角色（与 PD 等价）
 *   - 所有人员字段支持姓名+工号模糊搜索
 *
 * 校验规则在 validateFields() 里统一实现 */
export const INITIAL_FIELDS = [
  { key: 'name',     label: '项目名称', value: '', placeholder: '京东三期', required: true },
  /* G-8 · 至少二选一，两字段均支持 ID 或名称模糊搜索 */
  { key: 'code',     label: '交付项目编码', value: '', placeholder: 'HALL 号 / 机会点 ID', required: false, fuzzy: true, hint: '与 Proposal ID 至少填一项' },
  { key: 'proposal', label: 'Proposal ID',  value: '', placeholder: '机会点名称 / PROP 编码', required: false, fuzzy: true, hint: '与交付项目编码至少填一项' },
  /* 项目交付特点：合并原两组场景，改为多选 checkbox */
  { key: 'scene', label: '项目交付特点', value: '', required: true, multi: true,
    options: ['新增', '节点扩容', '推理', '训练', '训推一体', '大EP'],
    optionGroups: [['新增', '节点扩容'], ['推理', '训练', '训推一体'], ['大EP']] },
  /* 人员（5.27 早会新增 PCM）*/
  { key: 'pd',  label: '项目 PD',  value: '', placeholder: '', required: true,  fuzzy: true },
  { key: 'td',  label: '项目 TD',  value: '', placeholder: '', required: true,  fuzzy: true },
  { key: 'pcm', label: '项目 PCM', value: '', placeholder: '', required: false, fuzzy: true },
];

/* 校验规则：
 *   1. name 必填
 *   2. G-8 · proposal 与 code 至少二选一（强校验，两字段同时高亮 + 错误指向同一原因）
 *   3. sceneNew + sceneRun 都需填（不互斥同组，但跨组都必填）
 *   4. pd / td 必填
 */
export function validateFields(fields) {
  const errors = {};
  const get = k => fields.find(f => f.key === k)?.value ?? '';
  if (!get('name')) errors.name = '必填';
  /* G-8 · 两个字段都标错，用同一条文案让用户清楚二选一关系 */
  if (!get('proposal') && !get('code')) {
    const msg = '二选一';
    errors.proposal = msg;
    errors.code = msg;
  }
  if (!get('scene')) errors.scene = '请至少选择一项';
  if (!get('pd')) errors.pd = '必填';
  if (!get('td')) errors.td = '必填';
  return errors;
}

const SAMPLE_DOCS = [
  { name: '售前-工勘记录_K1903.pdf', size: '4.2 MB', type: 'PDF' },
  { name: 'HLD-K1903-v2.docx', size: '1.8 MB', type: 'DOC' },
  { name: 'BOQ-K1903.xlsx', size: '380 KB', type: 'XLS' },
  { name: '机房-CAD底图.dwg', size: '6.1 MB', type: 'CAD' },
];

/* 5.27 R-7 · 起手式：每文档一张卡引导上传
 * 来源：SVG "TD上传所有文件（HLD,维护建议书,培训建议书,售前工勘PPT,提资文件,服务建议书）每一个大块都要确认"
 */
const DOC_CATEGORIES = [
  { key: 'hld',       label: 'HLD 总体设计',     accept: '.docx,.pdf',  required: true,  hint: '陈卓接口主入口' },
  { key: 'boq',       label: 'BOQ 设备清单',     accept: '.xlsx,.csv',  required: true,  hint: '解析后写入风险与计划' },
  { key: 'cad',       label: 'CAD 机房底图',     accept: '.dwg,.dxf',   required: false, hint: '解析机柜与桥架坐标（兜底手工拖）' },
  { key: 'presale',   label: '售前工勘 PPT',     accept: '.pptx,.pdf',  required: true,  hint: '售前继承问题到交付' },
  { key: 'maint',     label: '维护建议书',       accept: '.docx,.pdf',  required: false, hint: '多模态解析 · 维保倒计时' },
  { key: 'train',     label: '培训建议书',       accept: '.docx,.pdf',  required: false, hint: '培训计划自动入计划页' },
  { key: 'rfp',       label: '提资文件',         accept: '.zip,.pdf',   required: false, hint: '客户需求基线' },
  { key: 'service',   label: '服务建议书',       accept: '.docx,.pdf',  required: false, hint: '5 大服务类自动归类' },
];

const OCC_TL = [
  { t: '+ 0s', who: 'TD 何博', act: '提交项目初始化（5 字段 + 4 文档）', state: 'done' },
  { t: '+ 6s', who: 'AIDA',    act: '风险扫描 · 发现 3 处敏感字段（地址/联系人）', state: 'done' },
  { t: '+ 12s', who: 'AIDA',    act: '调用 DORA · 校验合规规则（35 条全部通过）', state: 'done' },
  { t: '+ 18s', who: 'OCC 黎芳', act: '审批中 · 复核敏感字段访问范围',           state: 'active' },
  { t: '+ 25s', who: 'OCC 黎芳', act: '审批通过 · 项目空间获权激活',             state: 'pending' },
];

const OCC_DURATION_MS = 7000; // 演示版：7 秒走完

function Stepper({ current }) {
  return (
    <div className="cw-stepper">
      {STEPS.map((st, i) => (
        <div key={st.key} className={`cw-step${i === current ? ' active' : ''}${i < current ? ' done' : ''}`}>
          <div className="cw-step-dot">{i < current ? '✓' : i + 1}</div>
          <div className="cw-step-meta">
            <div className="cw-step-label">{st.label}</div>
            <div className="cw-step-desc">{st.desc}</div>
          </div>
          {i < STEPS.length - 1 && <div className="cw-step-line" />}
        </div>
      ))}
    </div>
  );
}

function ClawHint({ children }) {
  return (
    <div className="cw-claw">
      <span className="cw-claw-tag">AIDA</span>
      <span>{children}</span>
    </div>
  );
}

export function FieldsStep({ fields, onChange, onAutoFill, onNext, nextLabel, hideCancel, inModal, onCancel }) {
  const [attempted, setAttempted] = useState(false);
  const errors = validateFields(fields);
  const canNext = Object.keys(errors).length === 0;

  const handleNext = () => {
    setAttempted(true);
    if (canNext) onNext();
  };

  /**
   * handleFeatureToggle — "项目交付特点" chip 互斥逻辑
   *
   * 规则 A 【新增 / 扩容互斥】
   *   选中"新增"→ 自动移除"扩容"；选中"扩容"→ 自动移除"新增"
   *
   * 规则 B 【训推互斥】
   *   选中"训推一体"→ 自动移除"推理"和"训练"
   *   选中"推理"或"训练"→ 自动移除"训推一体"（推理与训练之间可共存）
   *
   * 等价于 react-hook-form：
   *   const cur = getValues('projectFeatures')
   *   setValue('projectFeatures', newValues, { shouldValidate: true })
   */
  const handleFeatureToggle = (fieldKey: string, currentValue: string, feature: string) => {
    const cur = currentValue.split(',').filter(Boolean);
    const isSelected = cur.includes(feature);

    let next: string[];
    if (isSelected) {
      // 已选中 → 移出（直接取消，无互斥）
      next = cur.filter(x => x !== feature);
    } else {
      // 未选中 → 加入，再执行互斥规则
      next = [...cur, feature];

      // Rule A: 新增 / 节点扩容 互斥
      if (feature === '新增')      next = next.filter(x => x !== '节点扩容');
      else if (feature === '节点扩容') next = next.filter(x => x !== '新增');

      // Rule B: 训推一体 与 推理 / 训练 互斥
      if (feature === '训推一体') next = next.filter(x => x !== '推理' && x !== '训练');
      else if (feature === '推理' || feature === '训练') next = next.filter(x => x !== '训推一体');
    }

    // 等价于 setValue('projectFeatures', next, { shouldValidate: true })
    onChange(fieldKey, next.join(','));
  };

  /* ── Tech-Minimalism 重构（5.31）──
   * focus:ring / ring-1 / shadow-sm 在本项目需用 inline style 实现（@tailwind base 已关闭）。
   * 所有 state / onChange / validateFields 原样保留，仅替换 JSX 结构和 class。 */
  const INPUT_BASE: React.CSSProperties = {
    width: '100%', height: 40, padding: '0 12px',
    borderRadius: 8, border: '1px solid #e4e4e7',
    background: '#ffffff', fontSize: 14, color: '#18181b',
    outline: 'none', transition: 'border-color .15s, box-shadow .15s',
  };
  const INPUT_ERR: React.CSSProperties = { ...INPUT_BASE, borderColor: '#dc2626' };

  return (
    <>
      {/* 表单区：纯白底、纵向 space-y-6 */}
      <div className="flex flex-col gap-6">
        {fields.map((f) => (
          <div key={f.key} className="grid gap-1.5" style={{ gridTemplateColumns: '140px 1fr', alignItems: 'start' }}>
            {/* Label 列 */}
            <div className="pt-2">
              <span className="text-sm font-medium text-zinc-800">
                {f.label}
                {f.required && <span className="ml-0.5 text-red-500">*</span>}
              </span>
            </div>

            {/* Input 列 */}
            <div>
              {f.multi ? (
                /* 项目交付特点 — Chip 多选，隐藏原生 checkbox
                 * 选中状态 = watch('projectFeatures').includes(o)  等价于 f.value.split(',').includes(o)
                 * 点击    = handleFeatureToggle(...)  含 A/B 互斥规则
                 * optionGroups：把互斥关系不同的三组在视觉上隔离 */
                <div className="flex flex-wrap items-center gap-2">
                  {(f.optionGroups || [f.options]).map((group, gi) => (
                    <Fragment key={gi}>
                      {gi > 0 && (
                        <span className="mx-1 h-7 w-px self-center bg-slate-200" aria-hidden />
                      )}
                      <div className="flex flex-wrap items-center gap-2">
                        {group.map((o) => {
                          const selected = f.value.split(',').filter(Boolean).includes(o);
                          return (
                            <label
                              key={o}
                              className={`cursor-pointer select-none rounded-lg border px-4 py-2 text-sm font-medium transition-colors ${
                                selected
                                  ? 'border-blue-500 bg-blue-50 text-blue-700'
                                  : 'border-slate-200 bg-white text-slate-700 hover:border-blue-400'
                              }`}
                            >
                              <input
                                type="checkbox"
                                checked={selected}
                                className="sr-only"
                                onChange={() => handleFeatureToggle(f.key, f.value, o)}
                              />
                              {o}
                            </label>
                          );
                        })}
                      </div>
                    </Fragment>
                  ))}
                </div>
              ) : f.options ? (
                /* 单选 radio（兼容性保留）*/
                <div className="flex flex-wrap gap-2">
                  {f.options.map((o) => (
                    <label
                      key={o}
                      className={`px-4 py-2 rounded-lg text-sm font-medium cursor-pointer transition-colors select-none ${
                        f.value === o
                          ? 'bg-zinc-900 text-white'
                          : 'bg-zinc-50 text-zinc-600 hover:bg-zinc-100'
                      }`}
                      style={f.value === o ? { boxShadow: '0 0 0 1px #18181b' } : undefined}
                    >
                      <input
                        type="radio"
                        name={f.key}
                        value={o}
                        checked={f.value === o}
                        className="sr-only"
                        onChange={(e) => onChange(f.key, e.target.value)}
                      />
                      {o}
                    </label>
                  ))}
                </div>
              ) : (
                <input
                  value={f.value}
                  placeholder={inModal ? '' : f.placeholder}
                  onChange={(e) => onChange(f.key, e.target.value)}
                  style={attempted && errors[f.key] ? INPUT_ERR : INPUT_BASE}
                  onFocus={e => {
                    e.target.style.borderColor = '#18181b';
                    e.target.style.boxShadow = '0 0 0 1px #18181b';
                  }}
                  onBlur={e => {
                    e.target.style.borderColor = attempted && errors[f.key] ? '#dc2626' : '#e4e4e7';
                    e.target.style.boxShadow = 'none';
                  }}
                />
              )}
              {f.hint && (
                <p className="mt-1.5 text-[11px] text-slate-400">{f.hint}</p>
              )}
              {attempted && errors[f.key] && (
                <p className="mt-1 text-xs text-red-500">{errors[f.key]}</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Footer — 右对齐 */}
      <div className="mt-8 flex items-center justify-end">
        {inModal && onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="mr-2 rounded-lg px-4 py-2 text-slate-600 transition-colors hover:bg-slate-100"
          >
            取消
          </button>
        )}
        {!hideCancel && !inModal && (
          <Link
            href="/cockpit"
            className="mr-3 text-sm text-zinc-500 transition-colors hover:text-zinc-700"
          >
            取消
          </Link>
        )}
        <button
          type="button"
          onClick={handleNext}
          className={
            inModal
              ? 'rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700'
              : 'rounded-lg bg-zinc-900 px-6 py-2 text-sm font-medium text-white transition-all hover:bg-zinc-800'
          }
          style={
            inModal
              ? undefined
              : { boxShadow: '0 1px 3px rgba(0,0,0,0.10), inset 0 0 0 1px rgba(255,255,255,0.08)' }
          }
          onMouseEnter={
            inModal
              ? undefined
              : (e) => {
                  e.currentTarget.style.transform = 'translateY(-1px)';
                }
          }
          onMouseLeave={
            inModal
              ? undefined
              : (e) => {
                  e.currentTarget.style.transform = 'translateY(0)';
                }
          }
        >
          {nextLabel || '下一步：上传文档 →'}
        </button>
      </div>
    </>
  );
}

function DocsStep({ docs, onAdd, onRemove, onNext, onPrev }) {
  /* 5.27 R-7 · 每文档一卡引导上传
   * 用 docs 列表反推每个 category 已有什么 */
  const byCategory = (catKey) => docs.filter(d => d.category === catKey);
  const requiredOK = DOC_CATEGORIES
    .filter(c => c.required)
    .every(c => byCategory(c.key).length > 0);
  const filled  = DOC_CATEGORIES.filter(c => byCategory(c.key).length > 0).length;
  const missing = DOC_CATEGORIES.filter(c => c.required && byCategory(c.key).length === 0).map(c => c.label);

  return (
    <>
      <ClawHint>
        每个大块都要确认 · <strong>{filled} / {DOC_CATEGORIES.length} 已上传</strong>，必填项{missing.length === 0 ? '✓ 已全' : `还缺 ${missing.length} 项`}
        {missing.length > 0 && <span style={{ color: 'var(--c-warning, #d97706)', marginLeft: 8 }}>（{missing.join(' / ')}）</span>}
      </ClawHint>

      <div className="cw-actions-row" style={{ marginBottom: 16 }}>
        <button
          className="btn sm ghost"
          onClick={() => {
            /* 演示快填：HLD/BOQ/CAD/售前 各加 1 个样例 */
            const samples = [
              { ...SAMPLE_DOCS[1], category: 'hld' },
              { ...SAMPLE_DOCS[2], category: 'boq' },
              { ...SAMPLE_DOCS[3], category: 'cad' },
              { ...SAMPLE_DOCS[0], category: 'presale' },
            ];
            samples.forEach(onAdd);
          }}
        >
          一键填入 4 个样例文件
        </button>
      </div>

      {/* 每文档一卡 */}
      <div className="cw-doc-cards">
        {DOC_CATEGORIES.map(cat => {
          const items = byCategory(cat.key);
          const has = items.length > 0;
          return (
            <div key={cat.key} className={`cw-doc-card${has ? ' has' : cat.required ? ' missing' : ''}`}>
              <div className="cw-doc-card-head">
                <span className="cw-doc-card-label">{cat.label}</span>
                {cat.required && <span className="cw-doc-card-req">必填</span>}
                {has && <span className="cw-doc-card-tick">✓ {items.length}</span>}
              </div>
              <div className="cw-doc-card-hint">{cat.hint}</div>
              {has ? (
                <div className="cw-doc-card-files">
                  {items.map((d, j) => {
                    const idx = docs.indexOf(d);
                    return (
                      <div key={j} className="cw-doc-card-file">
                        <span className="cw-doc-ext">{d.type}</span>
                        <span className="cw-doc-card-name">{d.name}</span>
                        <span className="cw-doc-card-size">{d.size}</span>
                        <button className="cw-doc-rm" onClick={() => onRemove(idx)}>✕</button>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="cw-doc-card-empty">未上传</div>
              )}
              <label className="cw-doc-card-add">
                + 添加 {cat.label.split(' ')[0]} 文件
                <input
                  type="file"
                  multiple
                  accept={cat.accept}
                  onChange={(e) => {
                    const files = Array.from(e.target.files || []);
                    files.forEach((f) => onAdd({
                      name: f.name,
                      size: `${(f.size / 1024 / 1024).toFixed(2)} MB`,
                      type: (f.name.split('.').pop() || '').toUpperCase(),
                      category: cat.key,
                    }));
                    e.target.value = '';
                  }}
                />
              </label>
            </div>
          );
        })}
      </div>

      <div className="cw-bar">
        <button className="btn sm ghost" onClick={onPrev}>← 上一步</button>
        <button className="btn sm primary" disabled={!requiredOK} onClick={onNext} title={requiredOK ? '' : `还缺：${missing.join('、')}`}>
          {requiredOK ? '提交 OCC 审批 →' : `还缺 ${missing.length} 项必填`}
        </button>
      </div>
    </>
  );
}

function OccStep({ onPrev, onApprove }) {
  const [tIdx, setTIdx] = useState(0);
  const [progress, setProgress] = useState(0);
  const [done, setDone] = useState(false);

  useEffect(() => {
    const startedAt = Date.now();
    const stepDuration = OCC_DURATION_MS / OCC_TL.length;
    const id = setInterval(() => {
      const dt = Date.now() - startedAt;
      const pct = Math.min(1, dt / OCC_DURATION_MS);
      setProgress(pct);
      const newIdx = Math.min(OCC_TL.length - 1, Math.floor(dt / stepDuration));
      setTIdx(newIdx);
      if (pct >= 1) {
        clearInterval(id);
        setDone(true);
      }
    }, 80);
    return () => clearInterval(id);
  }, []);

  return (
    <>
      <ClawHint>
        关联 Proposal 后会拉到机会点 / 合同 / BOQ 全量数据，存在新加坡数据出境风险。
        必须经 OCC 审批后才能激活项目空间。
      </ClawHint>

      <div className="cw-occ">
        <div className="cw-occ-bar">
          <div className="cw-occ-fill" style={{ width: `${progress * 100}%` }} />
        </div>
        <div className="cw-occ-stats">
          <div className="cw-occ-stat"><div className="k">关联机会点</div><div className="v">1</div></div>
          <div className="cw-occ-stat"><div className="k">合同</div><div className="v">0 (未签)</div></div>
          <div className="cw-occ-stat"><div className="k">BOQ 行数</div><div className="v">127</div></div>
          <div className="cw-occ-stat"><div className="k">敏感字段</div><div className="v">3 处</div></div>
        </div>
        <div className="cw-occ-tl">
          {OCC_TL.map((it, i) => {
            const state = i < tIdx ? 'done' : i === tIdx ? (done && i === OCC_TL.length - 1 ? 'done' : 'active') : 'pending';
            return (
              <div key={i} className={`cw-occ-row state-${state}`}>
                <span className="cw-occ-time">{it.t}</span>
                <span className="cw-occ-dot" />
                <span className="cw-occ-who">{it.who}</span>
                <span className="cw-occ-act">{i === OCC_TL.length - 1 && done ? '审批通过 · 项目空间已激活' : it.act}</span>
              </div>
            );
          })}
        </div>
      </div>

      <div className="cw-bar">
        <button className="btn sm ghost" onClick={onPrev}>← 上一步</button>
        <button className="btn sm primary" disabled={!done} onClick={onApprove}>
          {done ? '激活项目空间 → 进入孪生看板' : `审批中 · ${Math.round(progress * 100)}%`}
        </button>
      </div>
    </>
  );
}

function ActivatedStep() {
  return (
    <div className="cw-success">
      <div className="cw-success-icon">✓</div>
      <h2>项目空间已激活</h2>
      <p>K1903 · 京东三期 已就绪 · 现在可以开始交付作业了。</p>
      <div className="cw-success-grid">
        <Link href="/cockpit" className="cw-success-card">
          <div className="cw-success-card-icon">◎</div>
          <div className="cw-success-card-title">项目孪生 · K1903</div>
          <div className="cw-success-card-sub">看板 + 3D 孪生 · 一进即可见的项目大屏</div>
        </Link>
        <Link href="/preview?tab=dtrb" className="cw-success-card">
          <div className="cw-success-card-icon">◇</div>
          <div className="cw-success-card-title">早期接入 · 预案三快照</div>
          <div className="cw-success-card-sub">DTRB → DRB → 合同 LLD</div>
        </Link>
        <Link href="/plan?view=plan" className="cw-success-card">
          <div className="cw-success-card-icon">⌖</div>
          <div className="cw-success-card-title">项目管理 · 人货站</div>
          <div className="cw-success-card-sub">甘特 + 三因素并行</div>
        </Link>
        <Link href="/journey?step=4" className="cw-success-card">
          <div className="cw-success-card-icon">▶</div>
          <div className="cw-success-card-title">继续故事线 · DTRB 阶段</div>
          <div className="cw-success-card-sub">看完整生命周期的下一步</div>
        </Link>
      </div>
    </div>
  );
}

export default function CreateScreen() {
  const [step, setStep] = useState(0);
  const [fields, setFields] = useState(INITIAL_FIELDS);
  const [docs, setDocs] = useState([]);

  const setField = (k, v) => setFields((s) => s.map((f) => f.key === k ? { ...f, value: v } : f));
  /* 5.27 字段一键填样例 */
  const autoFill = () => {
    const sample = {
      name: '京东三期',
      code: 'PROP-2026-K1903',
      proposal: 'PROP-2026-K1903',
      scene: '新增,训推一体',
      pd: '李伟 / 01234568',
      td: '何博 / 01234567',
      pcm: '王婷 / 01234569',
    };
    setFields((s) => s.map((f) => ({ ...f, value: sample[f.key] ?? f.value })));
  };

  return (
    <div className="jn-wrap" style={{ flex: 1, overflow: 'auto' }}>
      <div className="main-inner cw-wrap">
        <div className="page-head">
          <div>
            <h1>新建项目 · 全流程向导</h1>
            <div className="sub">5 字段 → 文档摄取 → OCC 审批 → 项目空间激活</div>
          </div>
        </div>


        <Stepper current={step} />

        <div className="cw-card">
          {step === 0 && (
            <FieldsStep
              fields={fields}
              onChange={setField}
              onAutoFill={autoFill}
              onNext={() => setStep(1)}
            />
          )}
          {step === 1 && (
            <DocsStep
              docs={docs}
              onAdd={(d) => setDocs((arr) => [...arr, d])}
              onRemove={(i) => setDocs((arr) => arr.filter((_, ix) => ix !== i))}
              onNext={() => setStep(2)}
              onPrev={() => setStep(0)}
            />
          )}
          {step === 2 && (
            <OccStep
              onPrev={() => setStep(1)}
              onApprove={() => setStep(3)}
            />
          )}
          {step === 3 && <ActivatedStep />}
        </div>
      </div>
    </div>
  );
}
