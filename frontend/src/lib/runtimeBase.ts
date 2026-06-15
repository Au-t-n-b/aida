function cleanBase(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  if (!trimmed || trimmed === '/') return '';
  return trimmed.replace(/\/$/, '');
}

export function agentBase(): string {
  return cleanBase(import.meta.env.VITE_AGENT_BASE) ?? '';
}

export function managerBaseUrl(): string {
  return cleanBase(import.meta.env.VITE_CLAWMANAGER_BASE) ?? '';
}

export function ontologyBase(): string {
  return cleanBase(import.meta.env.VITE_ONTOLOGY_BASE) ?? '';
}
