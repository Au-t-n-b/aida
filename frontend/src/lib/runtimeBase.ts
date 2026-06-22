function cleanBase(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  if (trimmed === '/') return '';
  return trimmed.replace(/\/$/, '');
}

/**
 * 演示服务器用 python http.server :8080 提供静态页，无 nginx 反代。
 * 此时 Manager(:8081) / Agent(:7401) 需按主机名直连，否则会打到 :8080 导致 Failed to fetch。
 * Docker/nginx 同源部署（如 :8080）不走此分支。
 */
function bareMetalServiceBase(servicePort: number): string {
  if (typeof window === 'undefined' || import.meta.env.DEV) return '';
  const { protocol, hostname, port } = window.location;
  if (port === '8080') {
    return `${protocol}//${hostname}:${servicePort}`;
  }
  return '';
}

/**
 * Agent / Claw 后端基址。
 * 优先 session 中的 container_endpoint（enter-project 后），其次 VITE_AGENT_BASE / bareMetal。
 */
function readContainerEndpoint(): string | undefined {
  if (typeof window === 'undefined') return undefined;
  try {
    const raw = sessionStorage.getItem('aida:session');
    if (!raw) return undefined;
    const parsed = JSON.parse(raw) as { containerEndpoint?: string | null };
    return cleanBase(parsed.containerEndpoint);
  } catch {
    return undefined;
  }
}

export function agentBase(): string {
  return (
    readContainerEndpoint()
    ?? cleanBase(import.meta.env.VITE_AGENT_BASE)
    ?? bareMetalServiceBase(7401)
  );
}

export function managerBaseUrl(): string {
  return cleanBase(import.meta.env.VITE_CLAWMANAGER_BASE) ?? bareMetalServiceBase(8001);
}

export function ontologyBase(): string {
  return cleanBase(import.meta.env.VITE_ONTOLOGY_BASE) ?? bareMetalServiceBase(8011);
}
