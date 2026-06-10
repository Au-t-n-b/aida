// @ts-nocheck
'use client';

/* /landing · 项目选择落地页
 * 严格对齐会议结论："登录后第一屏只有项目列表 + 创建按钮，无 AI 输入窗"
 * 故意不要 LeftNav 的项目空间分支，也不要 ClawRail —— 因为这里还没选项目。
 */

import { useState } from 'react';
import Link from '@/compat/link';
import {
  LANDING_USER, LANDING_ACTIVE, LANDING_CREATE_HINT,
  STAGE4_LABELS,
} from '../../data/landing-data';
import CreateProjectModal from '../create-modal';

/* ── AidaMark logo · 与 /login login-kit 统一 ── */
const AidaMark = ({ size = 28 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 120 120" fill="none" aria-label="AIDA">
    <path d="M60 14 L104 104 L80 104 L60 56 L40 104 L16 104 Z" fill="#F6F7F9" />
    <path d="M44 83 L63 83 L57 96 L38 96 Z" fill="#19B8D8" />
  </svg>
);

/* ── 5.27 编辑笔 SVG ── */
const IcEdit = () => (
  <svg width={11} height={11} viewBox="0 0 12 12" fill="none">
    <path d="M2 8.5 L2 10 L3.5 10 L9.5 4 L8 2.5 Z M7.5 3 L9 4.5" stroke="currentColor" strokeWidth="1" fill="none" strokeLinecap="square" />
  </svg>
);

const STAGE_KEYS = ['survey', 'modeling', 'install', 'deploy'];

/* ── 项目卡片（5.27 重做版 + UX 抛光）── */
function ProjectCard({ p, onClick, onEdit }) {
  const overdue = p.overdueCount > 0;
  const stageIndex = STAGE_KEYS.indexOf(p.stage4);

  return (
    <div
      className={`lp-card${overdue ? ' has-overdue' : ''}`}
      style={{ fontFamily: '"Microsoft YaHei", "微软雅黑", sans-serif' }}
    >
      <button type="button" className="lp-card-main" onClick={onClick}>
        <div className="lp-card-name block w-full text-sm font-bold text-slate-900">{p.name}</div>
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

        {/* 阶段进度（4 段灯）*/}
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
                    reached
                      ? 'font-medium text-slate-800'
                      : 'text-slate-400'
                  }`}
                >
                  {STAGE4_LABELS[key]}
                </span>
              </span>
            );
          })}
        </div>

        <div className="lp-card-foot mt-auto flex flex-wrap items-center gap-2 border-0 border-t-0 pt-3">
          <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-normal text-amber-600">
            待办 {p.todoCount}
          </span>
          {p.overdueCount > 0 && (
            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-normal text-red-600">
              超期 {p.overdueCount}
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

/* ── 主屏 ── */
export default function LandingScreen() {
  const [tab, setTab] = useState('active'); // active | archive

  /* G-10/G-11 · 创建/编辑共用模态弹窗 */
  const [modal, setModal] = useState({ open: false, mode: 'create', preset: null });
  const openCreate = () => setModal({ open: true, mode: 'create', preset: null });
  const openEdit = (id) => {
    const p = LANDING_ACTIVE.find(x => x.id === id);
    const preset = p ? {
      name: p.name,
      code: p.code,
      proposal: '',
      sceneNew: '',
      sceneRun: '',
      pd: '',
      td: '',
      pcm: '',
    } : null;
    setModal({ open: true, mode: 'edit', preset });
  };
  const closeModal = () => setModal(s => ({ ...s, open: false }));

  const openProject = (id) => {
    if (typeof window !== 'undefined') {
      window.location.assign('../cockpit/');
    }
  };

  return (
    <div className="lp-wrap">
      {/* ── 顶部品牌条（minimal）── */}
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
            <div className="lp-top-user-name">{LANDING_USER.name}</div>
            <div className="lp-top-user-title">{LANDING_USER.title}</div>
          </div>
          <div className="lp-top-user-av">{LANDING_USER.avatar}</div>
          <Link href="/login" className="lp-top-logout">退出</Link>
        </div>
      </header>

      {/* ── 主体 ── */}
      <main className="lp-main">
        <section className="lp-hero mb-8 border-0 pb-0">
          <div>
            <h1 className="lp-hero-greet m-0 text-[28px] font-extrabold tracking-tight text-slate-900">
              早上好，{LANDING_USER.name}
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
                {LANDING_ACTIVE.length}
              </span>
            </button>
          </div>
          <div className="lp-toolbar-spacer" />
        </div>

        <div className="lp-grid">
          {tab === 'active' && (
            <>
              {LANDING_ACTIVE.map(p => (
                <ProjectCard
                  key={p.id}
                  p={p}
                  onClick={() => openProject(p.id)}
                  onEdit={openEdit}
                />
              ))}
              <CreateCard onClick={openCreate} />
            </>
          )}
        </div>
      </main>

      <CreateProjectModal
        open={modal.open}
        mode={modal.mode}
        preset={modal.preset}
        onClose={closeModal}
      />
    </div>
  );
}

/* ── 大创建卡片（占一格） ── */
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
