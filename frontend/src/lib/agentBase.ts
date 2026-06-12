/**
 * Agent 后端地址解析。
 * 本地开发时 7401 可能被旧进程占用（仍写 ProjectData），自动探测 7402+ 上已加载 project_paths.json 的实例。
 */
const LOCAL_PROBE_PORTS = [7402, 7403, 7404, 7401] as const;
const SYNC_DEFAULT = 'http://127.0.0.1:7402';

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

/** 同步回落（探测完成前）；优先 VITE_AGENT_BASE，否则 7402。 */
export function agentBaseSync(): string {
  return envBase() ?? _resolvedBase ?? SYNC_DEFAULT;
}

/** 解析可用 Agent 基址；system_design 跳过仍使用 ProjectData 的旧实例。 */
export async function ensureAgentBase(skillId = 'system_design'): Promise<string> {
  const fromEnv = envBase();
  if (fromEnv) return fromEnv;
  if (_resolvedBase) return _resolvedBase;
  if (!_resolvePromise) _resolvePromise = probeLocalAgent(skillId);
  return _resolvePromise;
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
  _resolvedBase = SYNC_DEFAULT;
  console.warn('[agent] 未找到可用的 system_design Agent，回落', SYNC_DEFAULT);
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
