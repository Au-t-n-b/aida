import {
  AlertTriangle,
  ArrowRight,
  CalendarDays,
  ClipboardList,
  FileWarning,
  ShieldAlert,
} from 'lucide-react';
import Link from '@/compat/link';
import { AppShell } from '@/components/app-shell';
import {
  getScheduleRiskReportState,
  type RiskReportCategory,
  type RiskReportSeverity,
  type RiskReportTodoItem,
  type ScheduleRiskReport,
} from '@/features/schedule/services/schedule-risk-report';
import './risk-report.css';

const categoryIcon: Record<RiskReportCategory['id'], typeof ClipboardList> = {
  customer: ClipboardList,
  purchase: CalendarDays,
  supply: FileWarning,
  sla: ShieldAlert,
};

export default function RiskReportScreen() {
  const state = getScheduleRiskReportState();

  return (
    <AppShell breadcrumbs={['项目管理 · 风险报告']}>
      <main className="risk-report-page">
        <div className="risk-report-inner">
          {state.status === 'empty' ? <RiskReportEmpty /> : <RiskReportReady report={state.report} />}
        </div>
      </main>
    </AppShell>
  );
}

function RiskReportEmpty() {
  return (
    <section className="risk-report-empty">
      <div className="risk-report-empty-icon" aria-hidden>
        <FileWarning size={24} />
      </div>
      <div className="risk-report-empty-title">暂无下发版本</div>
      <div className="risk-report-empty-text">
        完成计划排期的「确认&下发」后，这里会生成客户、采购、供应、超 SLA 四类业务待办。
      </div>
      <Link href="/plan" className="risk-report-empty-action">
        去计划排期
        <ArrowRight size={15} />
      </Link>
    </section>
  );
}

function RiskReportReady({ report }: { report: ScheduleRiskReport }) {
  return (
    <>
      <div className="risk-report-head">
        <div>
          <div className="risk-report-title">
            <span className="risk-report-title-icon" aria-hidden>
              <FileWarning size={18} />
            </span>
            <span>风险报告</span>
          </div>
          <div className="risk-report-sub">
            下发版本的业务跟进清单，按客户、采购、供应、超 SLA 四类收口。
          </div>
        </div>
        <div className="risk-report-head-tags">
          <span className="risk-report-tag strong">{report.baselineVersion}</span>
          <span className="risk-report-tag">{formatDateFull(report.generatedAt)}</span>
        </div>
      </div>

      <div className="risk-report-wrap">
        <article className="risk-report-sheet">
          <header className="risk-report-cover">
            <div>
              <div className="risk-report-eyebrow">交付项目风险报告</div>
              <div className="risk-report-h1">{report.projectName}</div>
              <div className="risk-report-meta">
                <span><b>项目编号</b>　{report.projectId}</span>
                <span><b>规模</b>　{formatProjectScale(report.projectScale, report.totalCardCount)}</span>
                <span><b>场景</b>　{report.scene}</span>
                <span><b>产品</b>　{report.productForm}</span>
              </div>
            </div>
            <div className="risk-report-cover-side">
              <div className="risk-report-side-label">报告生成</div>
              <div className="risk-report-side-value">{formatDateFull(report.generatedAt)}</div>
              <div className="risk-report-side-label" style={{ marginTop: 10 }}>基线版本</div>
              <div className="risk-report-side-value">{report.baselineVersion}</div>
            </div>
          </header>

          <div className="risk-report-divider" />

          <section>
            <h2 className="risk-report-h2">一、整体结论</h2>
            <div className="risk-report-callout">
              <AlertTriangle size={16} aria-hidden />
              <div>
                当前下发版本识别出 <b>{report.todoCount}</b> 项业务待办，其中 <b>{report.highCount}</b> 项为高优先级。
                建议先锁定客户侧 ready / 目标日期与供应 ETA，再跟进超 SLA 活动。
              </div>
            </div>
            <div className="risk-report-summary-grid">
              <SummaryCell label="业务待办" value={report.todoCount} danger={report.todoCount > 0} />
              <SummaryCell label="高优先级" value={report.highCount} danger={report.highCount > 0} />
              <SummaryCell label="计划活动" value={report.activityCount} />
              <SummaryCell label="关键路径活动" value={report.criticalActivityCount} />
            </div>
          </section>

          <section>
            <h2 className="risk-report-h2">二、业务待办四清单</h2>
            <p className="risk-report-p">
              四清单由当前下发计划与项目输入数据确定性派生，责任方采用通用配合口径，后续业务确认后再扩展模板字段。
            </p>
            {report.categories.map((category, index) => (
              <RiskCategorySection key={category.id} category={category} index={index + 1} />
            ))}
          </section>

          <div className="risk-report-divider" />
          <footer className="risk-report-footer">
            <div>本报告基于 {report.baselineVersion} 自动生成 · 下发时间 {formatDateTime(report.committedAt)}</div>
            <div>整体交付日 <b style={{ color: 'var(--c-text)' }}>{formatDateFull(report.projectFinishDate)}</b></div>
          </footer>
        </article>
      </div>
    </>
  );
}

function SummaryCell({ label, value, danger = false }: { label: string; value: number; danger?: boolean }) {
  return (
    <div className={`risk-report-summary-cell${danger ? ' danger' : ''}`}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
    </div>
  );
}

function RiskCategorySection({ category, index }: { category: RiskReportCategory; index: number }) {
  const Icon = categoryIcon[category.id];

  return (
    <section>
      <div className="risk-report-section-head">
        <div className="risk-report-section-title">
          <Icon size={15} aria-hidden />
          <span>{index}. {category.title}</span>
        </div>
        <span className="risk-report-rule-tag">{category.recognition}</span>
        <span className="risk-report-count">{category.items.length} 项</span>
      </div>
      <p className="risk-report-p">{category.description}</p>
      {category.items.length ? (
        <>
          <table className="risk-report-table">
            <thead>
              <tr>
                <th className="num">#</th>
                <th>等级</th>
                <th>事项</th>
                <th>责任方</th>
                <th>建议完成日</th>
                <th>关联活动</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {category.items.map((item, itemIndex) => (
                <tr key={item.id}>
                  <td className="num">{itemIndex + 1}</td>
                  <td><SeverityPill severity={item.severity} /></td>
                  <td>{item.matter}</td>
                  <td>{item.owner}</td>
                  <td className="date">{formatDateFull(item.suggestedDate)}</td>
                  <td>{item.relatedActivity}</td>
                  <td>{item.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="risk-report-todo-list">
            {category.items.map((item) => (
              <TodoCallout key={item.id} item={item} />
            ))}
          </div>
        </>
      ) : (
        <div className="risk-report-empty-section">{category.emptyText}</div>
      )}
    </section>
  );
}

function SeverityPill({ severity }: { severity: RiskReportSeverity }) {
  const cls = severity === '高' ? 'high' : severity === '中' ? 'mid' : 'low';
  return <span className={`risk-report-severity ${cls}`}>{severity}</span>;
}

function TodoCallout({ item }: { item: RiskReportTodoItem }) {
  return (
    <div className="risk-report-todo">
      <AlertTriangle size={15} color="var(--c-danger)" aria-hidden />
      <div className="risk-report-todo-body">
        <div className="risk-report-todo-title">{item.matter}</div>
        <div className="risk-report-todo-reason">
          <b>原因：</b>{item.reason}
        </div>
        <span className="risk-report-activity-tag">关联活动：{item.relatedActivity}</span>
      </div>
    </div>
  );
}

function formatProjectScale(scale: string, cardCount: number | null): string {
  if (!cardCount) return scale;
  return `${scale} · ${cardCount.toLocaleString()} 卡`;
}

function formatDateFull(value: string | null): string {
  if (!value) return '待确认';
  return value.slice(0, 10);
}

function formatDateTime(value: string): string {
  const normalized = value.slice(0, 16).replace('T', ' ');
  return normalized || value;
}
