/**
 * runLogStore — 运行日志逐行流（中间对话框「节点日志气泡」数据源）
 *
 * 背景：后端在每个 step「转圈」期间按 emit 的 sleep 节奏推 `run_log` SSE 事件
 *   （main.py · _push_run_log）。SSE 是单消费者队列，已被 useSduiStream 独占，
 *   因此不能再开第二个 EventSource —— 改由 useSduiStream 在同一条流上把 run_log
 *   事件写入本 store，SkillRunBanner（左侧会话）读取后逐条渲染。
 *
 * 时序天然对齐：行的到达节奏 = 后端 sleep 节奏，无需前端定时器；右侧步进条与
 *   左侧日志由同一批事件驱动，不会错位。
 *
 * 实现：module-level 单例（按 runId 分桶）+ useSyncExternalStore（React 18+）。
 */
import { useSyncExternalStore } from 'react';

export type RunLogStatus = 'running' | 'done' | 'failed';

/** 一个 step 的日志气泡：节点名 + 逐行内容 + 终态 */
export interface RunLogGroup {
  step: string;
  name: string;
  lines: string[];
  status: RunLogStatus;
}

/** 主建设 build 流程末尾串过的辅助只读步（ESN 完成后从中间对话框移除） */
const BUILD_AUX_LOG_STEPS = new Set([
  'progress_query',
  'plan_query',
  'device_overview',
  'plan_adjust',
]);

function withoutBuildAuxLogs(groups: RunLogGroup[]): RunLogGroup[] {
  return groups.filter((g) => !BUILD_AUX_LOG_STEPS.has(g.step));
}

/** 后端 run_log 事件载荷 */
export interface RunLogEvent {
  step: string;
  name?: string;
  msg?: string;
  phase?: 'start' | 'log' | 'done' | 'failed';
}

/** 去掉 emit 里的 [step_key] 前缀 */
function stripStepTag(msg: string): string {
  return msg.replace(/^\[[^\]]+\]\s*/, '').trimStart();
}

/** 去掉中英文括号及其中的说明文字 */
function stripParens(text: string): string {
  let s = text;
  for (let i = 0; i < 6; i++) {
    const next = s.replace(/（[^）]*）/g, '').replace(/\([^)]*\)/g, '');
    if (next === s) break;
    s = next;
  }
  return s.replace(/\s{2,}/g, ' ').trim();
}

const PATH_RE = /[A-Za-z]:\\|\/Users\/|ProjectData[\\/]|\.nanobot[\\/]|workspace[\\/]/;

/** 中间对话框专用：精简为业务可读短句，不展示路径与括号解释 */
function simplifyLogLine(msg: string): string {
  const raw = stripStepTag(msg).trim();
  if (!raw) return '';

  // 整行丢弃：路径、内部态、低价值信息
  if (/^源文件目录：/.test(raw)) return '';
  if (/^源目录\s/.test(raw)) return '';
  if (/当前命令:/.test(raw)) return '';
  if (/重放续跑/.test(raw)) return '';
  if (/▶\s*开始/.test(raw)) return '';
  if (/此前已下发.*幂等/.test(raw)) return '';
  if (PATH_RE.test(raw)) return '';

  let s = stripParens(raw);

  // 常见句式缩短
  if (/^⚠\s*LLM 摘要跳过/.test(s)) return 'LLM 摘要跳过';
  if (/^✓\s*上游·/.test(s) && /已就绪/.test(s)) return '上游实施计划已就绪';
  if (/^✗\s*上游·/.test(s)) return '上游实施计划缺失';
  if (/^重新解析上游实施计划：/.test(s)) return '正在解析实施计划';
  if (/^✓\s*已解析 (\d+) 条/.test(s)) {
    const m = s.match(/已解析 (\d+) 条/);
    return m ? `已解析 ${m[1]} 条实施计划` : '实施计划解析完成';
  }
  if (s === '🤖 AI 摘要：') return '预检结论';
  if (/^✓\s*已下发 (\d+) 条/.test(s)) {
    const m = s.match(/已下发 (\d+) 条/);
    return m ? `已下发 ${m[1]} 条计划` : '计划下发完成';
  }
  if (/^✓\s*已按勾选/.test(s) && /SN 扫码表/.test(s)) {
    const tm = s.match(/生成 (\d+) 张 SN 扫码表/);
    const dm = s.match(/共 (\d+) 台设备/);
    if (tm && dm) return `已生成 ${tm[1]} 张 SN 扫码表，共 ${dm[1]} 台设备`;
    return 'SN 扫码表已生成';
  }
  if (/下一步.*ESN/.test(s)) return '下一步：ESN 信息填写';
  if (/^✓\s*ESN 校验通过/.test(s)) {
    const m = s.match(/(\d+) 组 \/ (\d+) 台/);
    return m ? `ESN 校验通过，${m[1]} 组 ${m[2]} 台设备` : 'ESN 校验通过';
  }
  if (/^✓\s*已生成完工清单/.test(s)) {
    const m = s.match(/完工清单 (\d+) 份.*标记 (\d+) 条/);
    return m ? `已生成完工清单 ${m[1]} 份，${m[2]} 条任务完成` : '已生成完工清单与完工报告';
  }

  s = s.replace(/^\s+/, '').trim();
  if (!s || PATH_RE.test(s)) return '';
  return s;
}

// ── 模块级单例（按 runId 分桶）────────────────────────────────────────────────
const _byRun: Record<string, RunLogGroup[]> = {};
const _subs = new Set<() => void>();
const EMPTY: RunLogGroup[] = [];

function _notify(): void {
  _subs.forEach((fn) => fn());
}

// ── 写 API ────────────────────────────────────────────────────────────────────

/** 处理一条 run_log 事件，更新对应 runId 的分组（不可变替换数组）。 */
export function pushRunLog(runId: string, ev: RunLogEvent): void {
  if (!runId || !ev?.step) return;
  const cur = _byRun[runId] ?? [];
  // ESN 完成后不再接收辅助只读步日志（build 主流程末尾空转步）
  if (
    BUILD_AUX_LOG_STEPS.has(ev.step)
    && cur.some((g) => g.step === 'esn_fill' && g.status === 'done')
  ) {
    return;
  }
  const idx = cur.findIndex((g) => g.step === ev.step);
  const phase = ev.phase ?? 'log';
  let next = cur;

  if (phase === 'start') {
    // 新开 / 重开该 step 的气泡（go_back 重跑时清空旧行重新计数）
    const group: RunLogGroup = {
      step: ev.step,
      name: ev.name || (idx >= 0 ? cur[idx]!.name : ev.step),
      lines: [],
      status: 'running',
    };
    next = idx >= 0 ? cur.map((g, i) => (i === idx ? group : g)) : [...cur, group];
  } else if (phase === 'done' || phase === 'failed') {
    if (idx < 0) return;
    next = cur.map((g, i) =>
      i === idx ? { ...g, status: phase as RunLogStatus } : g,
    );
    // ESN 填写完成 → 移除末尾辅助只读步的空日志气泡
    if (ev.step === 'esn_fill' && phase === 'done') {
      next = withoutBuildAuxLogs(next);
    }
  } else {
    // phase === 'log'：追加一行（缺 start 时容错补建气泡）
    if (!ev.msg) return;
    const line = simplifyLogLine(ev.msg);
    if (!line) return;
    if (idx >= 0) {
      next = cur.map((g, i) =>
        i === idx ? { ...g, lines: [...g.lines, line] } : g,
      );
    } else {
      next = [
        ...cur,
        { step: ev.step, name: ev.name || ev.step, lines: [line], status: 'running' as RunLogStatus },
      ];
    }
  }

  if (next === cur) return;

  _byRun[runId] = next;
  _notify();
}

/** 读取某 run 的日志分组（稳定引用，供 useSyncExternalStore） */
function getRunLogGroups(runId: string | null): RunLogGroup[] {
  return runId ? _byRun[runId] ?? EMPTY : EMPTY;
}

/** 清空某个 run 的全部日志（新 run 开始时调用，避免串台）。 */
export function clearRunLog(runId: string): void {
  if (runId in _byRun) {
    delete _byRun[runId];
    _notify();
  }
}

// ── 读 API（React hook）───────────────────────────────────────────────────────

export function useRunLogStore(runId: string | null): RunLogGroup[] {
  return useSyncExternalStore(
    (cb) => {
      _subs.add(cb);
      return () => {
        _subs.delete(cb);
      };
    },
    () => getRunLogGroups(runId),
  );
}
