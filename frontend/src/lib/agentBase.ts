/**
 * Agent 后端地址解析。
 * 演示/生产默认走同源反代；需要直连本地 Agent 时显式配置 VITE_AGENT_BASE。
 */
import { agentBase as runtimeAgentBase } from '@/lib/runtimeBase';
const LOCAL_PROBE_PORTS = [7402, 7403, 7404, 7401] as const;

let _resolvedBase: string | null = null;
let _resolvePromise: Promise<string> | null = null;

function envBase(): string | undefined {
  const v = import.meta.env.VITE_AGENT_BASE;
  return typeof v === 'string' && v.trim() ? v.trim().replace(/\/$/, '') : undefined;
}

function isSystemDesignReady(workRoot: string): boolean {
  const norm = workRoot.replace(/\\/g, '/').toLowerCase();
  return norm.includes('file_path');
}

/** 同步回落（探测完成前）；优先 container_endpoint / VITE_AGENT_BASE，否则同源。 */
export function agentBaseSync(): string {
  const runtime = runtimeAgentBase();
  if (runtime) return runtime;
  return envBase() ?? _resolvedBase ?? '';
}

/** 解析可用 Agent 基址；enter-project 后优先 container_endpoint。 */
export async function ensureAgentBase(skillId = 'system_design'): Promise<string> {
  const fromRuntime = runtimeAgentBase();
  if (fromRuntime) return fromRuntime;
  const fromEnv = envBase();
  if (fromEnv) return fromEnv;
  // 开发期默认走 Vite /agent 代理（与页面同源），避免预览直连错误端口导致 403/404
  if (import.meta.env.DEV) return '';
  // 演示服务器默认走 Nginx 同源反代；不要探测访问者浏览器本机的 127.0.0.1。
  if (!import.meta.env.DEV) return '';
  if (_resolvedBase) return _resolvedBase;
  if (!_resolvePromise) _resolvePromise = probeLocalAgent(skillId);
  return _resolvePromise;
}

/** GET /agent/{skill}/artifact?path= — base 为空时走同源代理。 */
export function artifactUrl(base: string, skillId: string, path: string): string {
  const q = encodeURIComponent(normalizeArtifactPath(path));
  const prefix = base ? base.replace(/\/$/, '') : '';
  return `${prefix}/agent/${skillId}/artifact?path=${q}`;
}

/** 预览/下载统一逻辑路径；绝对路径或 输出结果/ 落盘 → ProjectData/Output/<文件名>。 */
export function normalizeArtifactPath(path: string): string {
  const raw = (path || '').trim();
  if (!raw) return raw;
  const norm = raw.replace(/\\/g, '/');
  if (/^ProjectData\//i.test(norm)) return norm;
  const name = norm.split('/').pop() ?? norm;
  if (/^[a-zA-Z]:\//.test(norm) || norm.startsWith('/opt/') || norm.includes('输出结果/')) {
    return `ProjectData/Output/${name}`;
  }
  return norm;
}

/** 从 artifact path 取展示用文件名（兼容 Windows 反斜杠绝对路径）。 */
export function artifactDisplayName(path: string): string {
  const norm = (path || '').replace(/\\/g, '/');
  return norm.split('/').pop() ?? path;
}

async function probeLocalAgent(skillId: string): Promise<string> {
  for (const port of LOCAL_PROBE_PORTS) {
    const base = `http://127.0.0.1:${port}`;
    try {
      const r = await fetch(`${base}/healthz`, { signal: AbortSignal.timeout(2500) });
      if (!r.ok) continue;
      const h = (await r.json()) as { skills?: Record<string, { work_root?: string }> };
      const wr = String(h?.skills?.[skillId]?.work_root ?? '');
      if (skillId === 'system_design') {
        if (!isSystemDesignReady(wr)) continue;
      } else if (!wr) {
        continue;
      }
      _resolvedBase = base;
      console.info('[agent] 已连接', base, skillId, 'work_root=', wr);
      return base;
    } catch {
      // try next port
    }
  }
  _resolvedBase = '';
  console.warn('[agent] 未找到可用的 system_design Agent，回落同源 /agent 代理');
  return _resolvedBase;
}

export interface UploadBatchResult {
  uploaded?: Array<Record<string, unknown>>;
  upload_dir?: string;
  data_root?: string;
  system_design_root?: string;
}

/** 旧 Agent 仍写 ProjectData 时返回用户可读错误；否则 null。 */
export function staleSystemDesignUploadMessage(result: UploadBatchResult): string | null {
  const item = result.uploaded?.[0];
  if (!item || item.ok === false) return null;
  const path = String(item.path ?? '');
  const hasNew = !!(result.upload_dir || item.abs_path);
  if (hasNew) return null;
  if (path.includes('ProjectData')) {
    return (
      'Agent 仍在使用旧路径（ProjectData），文件未落入 project_paths.json 配置的 input 目录。'
      + '请关闭占用 7401 端口的旧进程后重启 Agent，或刷新页面以自动连接 7402。'
    );
  }
  if (!result.upload_dir && path) {
    return 'Agent 未返回 upload_dir，可能仍在运行旧版本。请重启 Agent 后重试上传。';
  }
  return null;
}
