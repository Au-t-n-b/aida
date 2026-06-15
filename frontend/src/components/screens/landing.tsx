// @ts-nocheck
'use client';

/* /landing · 项目选择落地页
 * 登录后调用数据中心 GET /api/v1/projects/my，展示当前用户参与的项目。
 */

import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLogout } from '@/lib/use-logout';
import { useCurrentProject } from '@/lib/current-project';
import { useAidaSession } from '@/lib/aida-session';
import { fetchMyProjects } from '@/lib/claw-manager-client';
import {
  mapDcProjectToCard,
  projectToFormPreset,
  visibleLandingProjects,
  STAGE_KEYS,
  type LandingProjectCard,
} from '@/lib/landing-projects';
import { LANDING_CREATE_HINT, STAGE4_LABELS } from '../../data/landing-data';
import CreateProjectModal from '../create-modal';

const AidaMark = ({ size = 28 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 120 120" fill="none" aria-label="AIDA">
    <path d="M60 14 L104 104 L80 104 L60 56 L40 104 L16 104 Z" fill="#F6F7F9" />
    <path d="M44 83 L63 83 L57 96 L38 96 Z" fill="#19B8D8" />
  </svg>
);

const IcEdit = () => (
  <svg width={11} height={11} viewBox="0 0 12 12" fill="none">
    <path d="M2 8.5 L2 10 L3.5 10 L9.5 4 L8 2.5 Z M7.5 3 L9 4.5" stroke="currentColor" strokeWidth="1" fill="none" strokeLinecap="square" />
  </svg>
);

function ProjectCard({ p, onClick, onEdit }) {
  const overdue = p.overdueCount > 0;
  const stageIndex = STAGE_KEYS.indexOf(p.stage4);
  const disabled = !p.canEnter;
  const approved = p.status === 'APPROVED';
  const pending = p.status === 'PENDING_APPROVAL';

  return (
    <div
      className={`lp-card${overdue ? ' has-overdue' : ''}${disabled ? ' opacity-60' : ''}`}
      style={{ fontFamily: '"Microsoft YaHei", "微软雅黑", sans-serif' }}
      title={disabled ? (p.disabledReason || '项目暂不可进入') : undefined}
    >
      <button
        type="button"
        className="lp-card-main"
        onClick={disabled ? undefined : onClick}
        disabled={disabled}
      >
        <div className="flex w-full flex-wrap items-center gap-2">
          <span className="lp-card-name text-sm font-bold text-slate-900">{p.name}</span>
          {approved && (
            <span className="rounded bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
              已审批
            </span>
          )}
          {pending && (
            <span className="rounded bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
              待审批
            </span>
          )}
        </div>
        <div className="lp-card-head mt-1.5 flex w-full flex-wrap items-center gap-1.5">
          {p.roles?.map((r) => (
            <span
              key={r}
              className="rounded bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-600"
              data-role={r}
            >
              {r}
            </span>
          ))}
        </div>
        <div className="lp-card-code mt-1 text-left text-xs text-slate-400">{p.code}</div>

        <div className="lp-stage-track">
          {STAGE_KEYS.map((key, i) => {
            const reached = stageIndex >= i;
            const isCurrent = p.stage4 === key;
            return (
              <span
                key={key}
                className={`lp-stage-cell${reached ? ' reached' : ''}${isCurrent ? ' current' : ''}`}
                title={STAGE4_LABELS[key]}
              >
                <span className="lp-stage-dot" />
                <span
                  className={`lp-stage-name whitespace-nowrap text-[10px] ${
                    reached ? 'font-medium text-slate-800' : 'text-slate-400'
                  }`}
                >
                  {STAGE4_LABELS[key]}
                </span>
              </span>
            );
          })}
        </div>

        <div className="lp-card-foot mt-auto flex flex-wrap items-center gap-2 border-0 border-t-0 pt-3">
          {typeof p.progress === 'number' && p.progress > 0 ? (
            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-normal text-slate-600">
              进度 {p.progress}%
            </span>
          ) : p.todoCount > 0 ? (
            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-normal text-amber-600">
              待办 {p.todoCount}
            </span>
          ) : null}
          {p.overdueCount > 0 && (
            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-normal text-red-600">
              高风险
            </span>
          )}
          <span className="ml-auto text-xs text-slate-400">
            上次操作 {p.updated}
          </span>
        </div>
      </button>

      {p.canEdit && (
        <button
          type="button"
          className="absolute right-2 top-2 z-[2] inline-flex h-6 items-center gap-1 rounded border-0 bg-transparent px-2 text-[11px] text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
          onClick={(e) => {
            e.stopPropagation();
            onEdit?.(p.id);
          }}
          title="编辑项目（PD / PCM 可见）"
        >
          <IcEdit />
          <span>编辑</span>
        </button>
      )}
    </div>
  );
}

function userAvatar(name: string): string {
  const s = (name || '').trim();
  if (!s) return 'U';
  if (/[\u4e00-\u9fff]/.test(s)) return s.slice(0, 2);
  return s.slice(0, 2).toUpperCase();
}

export default function LandingScreen() {
  const navigate = useNavigate();
  const doLogout = useLogout();
  const { session } = useAidaSession();
  const { selectProject } = useCurrentProject();
  const [tab, setTab] = useState('active');
  const [projects, setProjects] = useState<LandingProjectCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  const [modal, setModal] = useState({ open: false, mode: 'create', preset: null, projectId: null });
  const openCreate = () => setModal({ open: true, mode: 'create', preset: null, projectId: null });
  const openEdit = (id: string) => {
    const p = projects.find((x) => x.id === id);
    const preset = p ? projectToFormPreset(p) : null;
    setModal({ open: true, mode: 'edit', preset, projectId: id });
  };
  const closeModal = () => setModal((s) => ({ ...s, open: false }));

  const reloadProjects = useCallback(async (opts?: { silent?: boolean }) => {
    if (!session?.accessToken) return;
    if (!opts?.silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const resp = await fetchMyProjects(session.accessToken, { page: 1, pageSize: 100 });
      const list = (resp.data?.list || []).map(mapDcProjectToCard);
      setProjects(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载项目列表失败');
      setProjects([]);
      throw e;
    } finally {
      if (!opts?.silent) setLoading(false);
    }
  }, [session?.accessToken]);

  useEffect(() => {
    void reloadProjects();
  }, [reloadProjects]);

  const handleProjectCreated = useCallback(async () => {
    await reloadProjects({ silent: true });
    setFlash('项目已提交创建，状态为待审批');
    window.setTimeout(() => setFlash(null), 5000);
  }, [reloadProjects]);

  const openProject = (id: string) => {
    const p = projects.find((x) => x.id === id);
    if (!p || !p.canEnter) return;
    selectProject({
      id: p.id,
      name: p.name,
      code: p.code,
      projectCode: p.projectCode || (String(p.code).startsWith('PROP-') ? undefined : p.code),
      proposalId: p.bidCode || (String(p.code).startsWith('PROP-') ? p.code : undefined),
    });
    navigate('/cockpit');
  };

  const displayName = session?.user?.display_name || session?.user?.username || '用户';
  const roleLabel = session?.user?.global_roles?.[0]?.roleName
    || session?.role
    || '交付成员';

  const visibleProjects = visibleLandingProjects(projects);

  const renderCard = (p: LandingProjectCard) => (
    <ProjectCard
      key={p.id}
      p={p}
      onClick={() => openProject(p.id)}
      onEdit={openEdit}
    />
  );

  return (
    <div className="lp-wrap">
      <header className="lp-top">
        <div className="lp-top-brand">
          <AidaMark size={22} />
          <div>
            <div className="lp-top-name">AIDA</div>
            <div className="lp-top-sub">ICT DELIVERY · AI</div>
          </div>
        </div>
        <div className="lp-top-spacer" />
        <div className="lp-top-user">
          <div className="lp-top-user-meta">
            <div className="lp-top-user-name">{displayName}</div>
            <div className="lp-top-user-title">{roleLabel}</div>
          </div>
          <div className="lp-top-user-av">{userAvatar(displayName)}</div>
          <button type="button" className="lp-top-logout" onClick={() => void doLogout()}>
            退出
          </button>
        </div>
      </header>

      <main className="lp-main">
        <section className="lp-hero mb-8 border-0 pb-0">
          <div>
            <h1 className="lp-hero-greet m-0 text-[28px] font-extrabold tracking-tight text-slate-900">
              早上好，{displayName}
            </h1>
          </div>
        </section>

        <div className="lp-toolbar mb-4">
          <div className="lp-tabs border-0 bg-transparent p-0">
            <button
              type="button"
              className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold shadow-sm transition-colors ${
                tab === 'active'
                  ? 'bg-slate-800 text-white'
                  : 'bg-transparent text-slate-500 hover:text-slate-700'
              }`}
              onClick={() => setTab('active')}
            >
              我的项目
              <span
                className={`rounded px-1.5 py-0.5 font-mono text-xs ${
                  tab === 'active' ? 'bg-white/15 text-white' : 'bg-slate-100 text-slate-600'
                }`}
              >
                {loading ? '…' : visibleProjects.length}
              </span>
            </button>
          </div>
          <div className="lp-toolbar-spacer" />
        </div>

        {flash && (
          <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            {flash}
          </div>
        )}

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="lp-grid-scroll">
          <div className="lp-grid">
            {tab === 'active' && (
              <>
                {loading && (
                  <div className="col-span-full py-12 text-center text-sm text-slate-500">
                    正在加载项目列表…
                  </div>
                )}
                {!loading && visibleProjects.length === 0 && !error && (
                  <div className="col-span-full py-12 text-center text-sm text-slate-500">
                    暂无参与的项目，可点击下方新建项目
                  </div>
                )}
                {!loading && visibleProjects.map(renderCard)}
                {!loading && <CreateCard onClick={openCreate} />}
              </>
            )}
          </div>
        </div>
      </main>

      <CreateProjectModal
        open={modal.open}
        mode={modal.mode}
        preset={modal.preset}
        projectId={modal.projectId}
        onClose={closeModal}
        onCreated={handleProjectCreated}
      />
    </div>
  );
}

function CreateCard({ onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="lp-create group flex min-h-[200px] w-full cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-200 bg-slate-50/40 p-4 transition-all duration-300 hover:border-blue-400 hover:bg-blue-50/30"
    >
      <div className="flex flex-col items-center gap-2.5">
        <div className="flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-400 transition-transform duration-300 group-hover:scale-110 group-hover:border-blue-200 group-hover:text-blue-500">
          <svg width={20} height={20} viewBox="0 0 20 20" fill="none" aria-hidden>
            <path
              d="M10 4 L10 16 M4 10 L16 10"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </div>
        <div className="text-sm font-medium text-slate-500 transition-colors group-hover:text-blue-600">
          {LANDING_CREATE_HINT?.headline ?? '新建项目'}
        </div>
      </div>
    </button>
  );
}
