'use client';

/* CreateProjectModal · 创建 / 编辑项目模态弹窗 (G-10 + G-11)
 *
 * 创建：校验通过后调用数据中心 POST /api/v1/projects，成功后刷新落地页列表（待审批）。
 * 编辑：打开时 GET /api/v1/projects/{uuid} 拉详情预填；保存时 PUT 更新并刷新列表。
 */

import { useEffect, useRef, useState } from 'react';
import { useAidaSession } from '@/lib/aida-session';
import { createProject, fetchProjectDetail, updateProject } from '@/lib/claw-manager-client';
import {
  dcProjectDetailToFormPreset,
  formToCreateProjectBody,
  formToUpdateProjectBody,
} from '@/lib/landing-projects';
import { CONTRACT_PRESALE, INITIAL_FIELDS, FieldsStep } from './screens/create';

interface CreateFieldDef {
  key: string;
  value: string;
  [extra: string]: unknown;
}

type CreatePreset = Record<string, string> | null;

const SAMPLE: Record<string, string> = {
  name: '京东三期',
  contractType: CONTRACT_PRESALE,
  code: 'PROP-2026-K1903',
  proposal: '',
  scene: '新建,训推一体',
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
  /** 创建或编辑保存成功后回调（用于刷新项目列表） */
  onSaved?: (kind: 'create' | 'edit') => void | Promise<void>;
}

export default function CreateProjectModal({
  open,
  mode = 'create',
  preset = null,
  projectId = null,
  onClose,
  onSaved,
}: CreateProjectModalProps) {
  const { session } = useAidaSession();
  const [fields, setFields] = useState<CreateFieldDef[]>(INITIAL_FIELDS as CreateFieldDef[]);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const detailReqRef = useRef(0);

  useEffect(() => {
    if (!open) return;
    setSubmitError(null);
    setSubmitting(false);

    if (mode !== 'edit' || !projectId) {
      setDetailLoading(false);
      setFields(prefill(INITIAL_FIELDS as CreateFieldDef[], preset));
      return;
    }

    // 编辑：先用列表占位，再拉详情覆盖
    setFields(prefill(INITIAL_FIELDS as CreateFieldDef[], preset));
    if (!session?.accessToken) {
      setSubmitError('登录已失效，请重新登录');
      return;
    }

    const reqId = ++detailReqRef.current;
    setDetailLoading(true);
    void (async () => {
      try {
        const resp = await fetchProjectDetail(session.accessToken, projectId);
        if (detailReqRef.current !== reqId) return;
        const presetFromApi = dcProjectDetailToFormPreset(resp.data);
        setFields(prefill(INITIAL_FIELDS as CreateFieldDef[], presetFromApi));
        setSubmitError(null);
      } catch (e) {
        if (detailReqRef.current !== reqId) return;
        setSubmitError(e instanceof Error ? e.message : '加载项目详情失败');
      } finally {
        if (detailReqRef.current === reqId) setDetailLoading(false);
      }
    })();
  }, [open, preset, mode, projectId, session?.accessToken]);

  if (!open) return null;

  const setField = (k: string, v: string) =>
    setFields((s) => s.map((f) => (f.key === k ? { ...f, value: v } : f)));
  const autoFill = () =>
    setFields((s) => s.map((f) => ({ ...f, value: SAMPLE[f.key] ?? f.value })));

  const handleSubmit = async () => {
    if (typeof window === 'undefined' || submitting || detailLoading) return;
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
        await onSaved?.('create');
        onClose?.();
      } catch (e) {
        setSubmitError(e instanceof Error ? e.message : '创建项目失败');
      } finally {
        setSubmitting(false);
      }
      return;
    }

    if (!projectId) {
      setSubmitError('缺少项目 ID，无法保存');
      return;
    }
    if (!session?.accessToken) {
      setSubmitError('登录已失效，请重新登录');
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const body = formToUpdateProjectBody(obj);
      if (Object.keys(body).length === 0) {
        setSubmitError('没有可保存的变更');
        return;
      }
      await updateProject(session.accessToken, projectId, body);
      await onSaved?.('edit');
      onClose?.();
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : '保存项目失败');
    } finally {
      setSubmitting(false);
    }
  };

  const title = mode === 'edit' ? '编辑项目空间' : '新建项目空间';
  const ctaLabel = mode === 'edit'
    ? (detailLoading ? '加载中…' : (submitting ? '保存中…' : '保存'))
    : (submitting ? '提交中…' : '提交创建');

  return (
    <div className="cm-mask" onClick={onClose} role="dialog" aria-modal="true">
      <div className="cm-wrap" onClick={(e) => e.stopPropagation()}>
        <div className="cm-head">
          <div className="cm-title">{title}</div>
          <button className="cm-close" onClick={onClose} title="关闭" type="button">✕</button>
        </div>

        <div className="cm-body">
          {detailLoading && mode === 'edit' && (
            <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
              正在加载项目详情…
            </div>
          )}
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
            mode={mode}
          />
        </div>
      </div>
    </div>
  );
}
