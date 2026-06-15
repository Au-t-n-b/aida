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
 * Docker/nginx 同源部署（如 :5401）不走此分支。
 */
function bareMetalServiceBase(servicePort: number): string {
  if (typeof window === 'undefined' || import.meta.env.DEV) return '';
  const { protocol, hostname, port } = window.location;
  if (port === '8080') {
    return `${protocol}//${hostname}:${servicePort}`;
  }
  return '';
}

export function agentBase(): string {
  return cleanBase(import.meta.env.VITE_AGENT_BASE) ?? bareMetalServiceBase(7401);
}

export function managerBaseUrl(): string {
  return cleanBase(import.meta.env.VITE_CLAWMANAGER_BASE) ?? bareMetalServiceBase(8081);
}

export function ontologyBase(): string {
  return cleanBase(import.meta.env.VITE_ONTOLOGY_BASE) ?? bareMetalServiceBase(8011);
}
