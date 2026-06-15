'use client';

/* CreateProjectModal · 创建 / 编辑项目模态弹窗 (G-10 + G-11)
 *
 * 创建：校验通过后调用数据中心 POST /api/v1/projects，成功后刷新落地页列表（待审批）。
 * 编辑：打开时 GET /api/v1/projects/{uuid} 拉详情预填；保存时 PUT 更新并刷新列表。
 */

import { useEffect, useRef, useState } from 'react';
import { useAidaSession, type AidaSessionState } from '@/lib/aida-session';
import { createProject, fetchProjectDetail, updateProject } from '@/lib/claw-manager-client';
import {
  type ApiErrorDetail,
  apiErrorDiagnosticLines,
  applyApiError,
} from '@/lib/api-error';
import {
  dcProjectDetailToFormPreset,
  formToCreateProjectBody,
  formToUpdateProjectBody,
} from '@/lib/landing-projects';
import { INITIAL_FIELDS, FieldsStep } from './screens/create';

interface CreateFieldDef {
  key: string;
  value: string;
  [extra: string]: unknown;
}

type CreatePreset = Record<string, string> | null;

/** 与规范 §4.6 示例请求字段一致 */
const SAMPLE: Record<string, string> = {
  name: '深圳数据中心一期',
  contractType: '标准合同',
  code: '',
  proposal: 'BID-2026-001',
  scene: '新建,液冷',
  pd: 'lisi',
  td: 'zhangsan',
  pcm: '',
};

function sessionPersonLabel(session: AidaSessionState | null): string {
  const u = session?.user?.username?.trim();
  if (!u) return '';
  const d = (session?.user?.display_name || '').trim();
  if (d && d !== u) return `${d} / ${u}`;
  return u;
}

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
  const [submitErrorDetail, setSubmitErrorDetail] = useState<ApiErrorDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const detailReqRef = useRef(0);
  const wasOpenRef = useRef(false);

  useEffect(() => {
    if (!open) {
      wasOpenRef.current = false;
      return;
    }
    const justOpened = !wasOpenRef.current;
    wasOpenRef.current = true;

    setSubmitError(null);
    setSubmitErrorDetail(null);
    setSubmitting(false);

    if (mode !== 'edit' || !projectId) {
      setDetailLoading(false);
      if (justOpened) {
        const presetObj: CreatePreset = preset ? { ...preset } : {};
        const tdDefault = sessionPersonLabel(session);
        if (!presetObj.td && tdDefault) presetObj.td = tdDefault;
        setFields(prefill(INITIAL_FIELDS as CreateFieldDef[], presetObj));
      }
      return;
    }

    if (justOpened) {
      setFields(prefill(INITIAL_FIELDS as CreateFieldDef[], preset));
    }
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
        setSubmitErrorDetail(null);
      } catch (e) {
        if (detailReqRef.current !== reqId) return;
        applyApiError(e, setSubmitError, setSubmitErrorDetail, '加载项目详情失败');
      } finally {
        if (detailReqRef.current === reqId) setDetailLoading(false);
      }
    })();
  }, [open, preset, mode, projectId, session?.accessToken]);

  const handleBackdropClose = (e: React.MouseEvent<HTMLDivElement>) => {
    // 用 mousedown 且仅点在遮罩本身，避免「点新建」的 click 穿透到刚挂载的 mask 上立刻关窗
    if (e.target !== e.currentTarget) return;
    onClose?.();
  };

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
      setSubmitErrorDetail(null);
      try {
        const sessionUsername = session.user?.username?.trim() || undefined;
        const body = formToCreateProjectBody(obj, { sessionUsername });
        await createProject(session.accessToken, body);
        await onSaved?.('create');
        onClose?.();
      } catch (e) {
        applyApiError(e, setSubmitError, setSubmitErrorDetail, '创建项目失败');
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
    setSubmitErrorDetail(null);
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
      applyApiError(e, setSubmitError, setSubmitErrorDetail, '保存项目失败');
    } finally {
      setSubmitting(false);
    }
  };

  const title = mode === 'edit' ? '编辑项目空间' : '新建项目空间';
  const ctaLabel = mode === 'edit'
    ? (detailLoading ? '加载中…' : (submitting ? '保存中…' : '保存'))
    : (submitting ? '提交中…' : '提交创建');

  return (
    <div
      className="cm-mask"
      onMouseDown={handleBackdropClose}
      role="dialog"
      aria-modal="true"
    >
      <div className="cm-wrap" onMouseDown={(e) => e.stopPropagation()}>
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
              <div className="font-medium">{submitError}</div>
              {submitErrorDetail && apiErrorDiagnosticLines(submitErrorDetail).length > 0 && (
                <dl className="mt-2 space-y-1.5 border-t border-red-200/80 pt-2 text-xs font-normal text-red-800/90">
                  {apiErrorDiagnosticLines(submitErrorDetail).map((row) => (
                    <div key={row.label}>
                      <dt className="font-semibold text-red-900/80">{row.label}</dt>
                      <dd className="mt-0.5 whitespace-pre-wrap break-all font-mono">{row.value}</dd>
                    </div>
                  ))}
                </dl>
              )}
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
