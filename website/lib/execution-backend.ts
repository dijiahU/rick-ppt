export const executionBackends = ['api', 'codex'] as const;
export type ExecutionBackend = typeof executionBackends[number];
export const defaultExecutionBackend: ExecutionBackend = 'codex';
export type ExecutionAvailability = Record<ExecutionBackend, boolean>;

// Admission is server-owned. An unavailable worker queues for the local default;
// API is selected only when a live worker actually advertises it without Codex.
export function automaticExecutionBackend(status: {online?: boolean; executionAvailability?: Partial<ExecutionAvailability>}): ExecutionBackend {
  return status.online && status.executionAvailability?.api === true &&
    status.executionAvailability.codex !== true ? 'api' : defaultExecutionBackend;
}

export function isExecutionBackend(value: unknown): value is ExecutionBackend {
  return value === 'api' || value === 'codex';
}

// A missing capability is the old worker contract: it may claim legacy rows only.
// Invalid capabilities are rejected; they never turn into a default route.
export function workerCapabilities(value: unknown): {backends: ExecutionBackend[]; advertised: boolean} | null {
  if (value === undefined) return {backends: [], advertised: false};
  if (!Array.isArray(value) || value.length > executionBackends.length ||
      value.some(item => !isExecutionBackend(item)) || new Set(value).size !== value.length) return null;
  return {backends: value as ExecutionBackend[], advertised: true};
}

export function executionAvailability(value: unknown, online: boolean): ExecutionAvailability {
  let parsed: unknown;
  try { parsed = typeof value === 'string' ? JSON.parse(value) : value; } catch { parsed = null; }
  const capabilities = workerCapabilities(parsed);
  return {
    api: online && !!capabilities?.backends.includes('api'),
    codex: online && !!capabilities?.backends.includes('codex'),
  };
}

export function backendChoiceUnavailable(backend: ExecutionBackend, online: boolean | undefined,
    availability: Partial<ExecutionAvailability> | undefined): boolean {
  return online === true && availability?.[backend] === false;
}
