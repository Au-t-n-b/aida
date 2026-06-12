'use client';

/* CreateProjectModal · 创建 / 编辑项目模态弹窗 (G-10 + G-11)
 *
 * 5.27 早会拍板：
 *   - 落地页"+"卡 与 项目卡的编辑按钮 用同一个弹窗（共用字段组件）
 *   - 弹窗里只有"字段填写"一步 —— 不在弹窗里走文档/OCC，那些进项目空间再做
 *   - 点确认 → 写 sessionStorage 标记 → 跳 /cockpit
 *   - ClawRail 进入 cockpit 后读到标记 → 推「拉容器 + 异步解析」进度
 *
 * 复用 create.jsx 里的 INITIAL_FIELDS / validateFields / FieldsStep —— 一处约束。
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { deriveProjectId, useCurrentProject } from '@/lib/current-project';
import { INITIAL_FIELDS, FieldsStep } from './screens/create';

/** 创建/编辑字段值 —— key/value 任意，运行时由 FieldsStep 维护 */
interface CreateFieldDef {
  key: string;
  value: string;
  [extra: string]: unknown;
}

type CreatePreset = Record<string, string> | null;

const SAMPLE: Record<string, string> = {
  name: '京东三期',
  code: 'PROP-2026-K1903',
  proposal: 'PROP-2026-K1903',
  scene: '新增,训推一体',
  pd: '李伟 / 01234568',
  td: '何博 / 01234567',
  pcm: '王婷 / 01234569',
};

/** 把字段 array → flat object 方便写 sessionStorage */
function fieldsToObj(fields: CreateFieldDef[]): Record<string, string> {
  return Object.fromEntries(fields.map((f) => [f.key, f.value]));
}

/** 给定可编辑的项目对象 → 填回字段初值 */
function prefill(fields: CreateFieldDef[], presetObj: CreatePreset): CreateFieldDef[] {
  if (!presetObj) return fields;
  return fields.map((f) => ({ ...f, value: presetObj[f.key] ?? f.value }));
}

export interface CreateProjectModalProps {
  open: boolean;
  mode?: 'create' | 'edit';
  preset?: CreatePreset;
  projectId?: string | null;
  onClose?: () => void;
}

export default function CreateProjectModal({
  open,
  mode = 'create',
  preset = null,
  projectId = null,
  onClose,
}: CreateProjectModalProps) {
  const navigate = useNavigate();
  const { selectProject } = useCurrentProject();
  const [fields, setFields] = useState<CreateFieldDef[]>(INITIAL_FIELDS as CreateFieldDef[]);

  /* 打开 / 切换 mode 时重置 */
  useEffect(() => {
    if (!open) return;
    setFields(prefill(INITIAL_FIELDS as CreateFieldDef[], preset));
  }, [open, preset]);

  if (!open) return null;

  const setField = (k: string, v: string) =>
    setFields((s) => s.map((f) => (f.key === k ? { ...f, value: v } : f)));
  const autoFill = () =>
    setFields((s) => s.map((f) => ({ ...f, value: SAMPLE[f.key] ?? f.value })));

  const handleSubmit = () => {
    if (typeof window === 'undefined') return;
    const obj = fieldsToObj(fields);
    const payload = {
      mode,
      fields: obj,
      ts: Date.now(),
    };
    try { sessionStorage.setItem('aida:just-created', JSON.stringify(payload)); } catch {}
    const id = projectId ?? deriveProjectId(obj.code, obj.proposal);
    selectProject({
      id,
      name: obj.name || '未命名项目',
      code: obj.code || obj.proposal || undefined,
    });
    onClose?.();
    navigate('/cockpit');
  };

  const title = mode === 'edit' ? '编辑项目空间' : '新建项目空间';
  const ctaLabel = mode === 'edit' ? '保存' : '创建并进入';

  return (
    <div className="cm-mask" onClick={onClose} role="dialog" aria-modal="true">
      <div className="cm-wrap" onClick={(e) => e.stopPropagation()}>
        <div className="cm-head">
          <div className="cm-title">{title}</div>
          <button className="cm-close" onClick={onClose} title="关闭">✕</button>
        </div>

        <div className="cm-body">
          <FieldsStep
            fields={fields}
            onChange={setField}
            onAutoFill={autoFill}
            onNext={handleSubmit}
            nextLabel={ctaLabel}
            hideCancel
            inModal
            onCancel={onClose}
          />
        </div>

      </div>
    </div>
  );
}
