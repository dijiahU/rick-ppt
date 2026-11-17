import {executionAvailability, type ExecutionAvailability} from './execution-backend';

// Which worker a request comes from is decided by the secret it presented
// (WORKER_TOKEN = server, LOCAL_WORKER_TOKEN = local), never by a body field.
export type WorkerIdentity = 'server' | 'local';
export const WORKER_ONLINE_MS = 90000;

// The server keeps the historical 'primary' row so existing deployments and
// older workers continue to report into the same place.
export function workerRow(identity: WorkerIdentity): string {
  return identity === 'local' ? 'local' : 'primary';
}

// Local-first routing: while the local worker is online, the server worker
// does not claim new tasks; once local has been silent for WORKER_ONLINE_MS,
// the server takes queued work. Running tasks keep their own leases.
export function deferToLocal(identity: WorkerIdentity, localHeartbeat: number | null | undefined, now: number): boolean {
  return identity === 'server' && typeof localHeartbeat === 'number' && localHeartbeat > now - WORKER_ONLINE_MS;
}

type WorkerRowValue = {heartbeat: number; execution_backends: string | null};

// The site is online when any worker is; a backend is available when any
// online worker advertises it.
export function combinedWorkerStatus(rows: WorkerRowValue[], now: number): {online: boolean; executionAvailability: ExecutionAvailability} {
  const live = rows.filter(row => row.heartbeat > now - WORKER_ONLINE_MS);
  const availability = live.map(row => executionAvailability(row.execution_backends, true));
  return {
    online: live.length > 0,
    executionAvailability: {
      api: availability.some(a => a.api),
      codex: availability.some(a => a.codex),
    },
  };
}
