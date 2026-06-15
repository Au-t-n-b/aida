'use client';

/* CreateProjectModal · 创建 / 编辑项目模态弹窗 (G-10 + G-11)
 *
 * 创建：校验通过后调用数据中心 POST /api/v1/projects，成功后刷新落地页列表（待审批）。
 * 编辑：暂保留本地预填（后续对接 PUT /projects/{projectId}）。
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { deriveProjectId, useCurrentProject } from '@/lib/current-project';
import { useAidaSession } from '@/lib/aida-session';
import { createProject } from '@/lib/claw-manager-client';
import { formToCreateProjectBody } from '@/lib/landing-projects';
import { INITIAL_FIELDS, FieldsStep } from './screens/create';

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

function fieldsToObj(fields: CreateFieldDef[]): Record<string, string> {
  return Object.fromEntries(fields.map((f) => [f.key, f.value]));
}

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
  /** 创建成功后回调（用于刷新项目列表） */
  onCreated?: () => void | Promise<void>;
}

export default function CreateProjectModal({
  open,
  mode = 'create',
  preset = null,
  projectId = null,
  onClose,
  onCreated,
}: CreateProjectModalProps) {
  const navigate = useNavigate();
  const { session } = useAidaSession();
  const { selectProject } = useCurrentProject();
  const [fields, setFields] = useState<CreateFieldDef[]>(INITIAL_FIELDS as CreateFieldDef[]);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setFields(prefill(INITIAL_FIELDS as CreateFieldDef[], preset));
    setSubmitError(null);
    setSubmitting(false);
  }, [open, preset]);

  if (!open) return null;

  const setField = (k: string, v: string) =>
    setFields((s) => s.map((f) => (f.key === k ? { ...f, value: v } : f)));
  const autoFill = () =>
    setFields((s) => s.map((f) => ({ ...f, value: SAMPLE[f.key] ?? f.value })));

  const handleSubmit = async () => {
    if (typeof window === 'undefined' || submitting) return;
    const obj = fieldsToObj(fields);

    if (mode === 'create') {
      if (!session?.accessToken) {
        setSubmitError('登录已失效，请重新登录');
        return;
      }
      setSubmitting(true);
      setSubmitError(null);
      try {
        const body = formToCreateProjectBody(obj);
        await createProject(session.accessToken, body);
        await onCreated?.();
        onClose?.();
      } catch (e) {
        setSubmitError(e instanceof Error ? e.message : '创建项目失败');
      } finally {
        setSubmitting(false);
      }
      return;
    }

    // 编辑模式：暂保留原行为（后续对接 PUT）
    const payload = { mode, fields: obj, ts: Date.now() };
    try { sessionStorage.setItem('aida:just-created', JSON.stringify(payload)); } catch {}
    const id = projectId ?? deriveProjectId(obj.code, obj.proposal);
    selectProject({
      id,
      name: obj.name || '未命名项目',
      code: obj.code || obj.proposal || undefined,
      projectCode: obj.code || undefined,
      proposalId: obj.proposal || undefined,
    });
    onClose?.();
    navigate('/cockpit');
  };

  const title = mode === 'edit' ? '编辑项目空间' : '新建项目空间';
  const ctaLabel = mode === 'edit' ? '保存' : (submitting ? '提交中…' : '提交创建');

  return (
    <div className="cm-mask" onClick={onClose} role="dialog" aria-modal="true">
      <div className="cm-wrap" onClick={(e) => e.stopPropagation()}>
        <div className="cm-head">
          <div className="cm-title">{title}</div>
          <button className="cm-close" onClick={onClose} title="关闭" type="button">✕</button>
        </div>

        <div className="cm-body">
          {submitError && (
            <div
              className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
              role="alert"
            >
              {submitError}
            </div>
          )}
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
