import {database} from './server';
import {QUEUE_CAPACITY, type QueueHealth} from './queue-state';

export async function queueHealth(): Promise<QueueHealth> {
  const checkedAt = Date.now();
  const row = await database().prepare(`SELECT
    (SELECT heartbeat FROM worker WHERE id='primary') AS lastHeartbeat,
    COUNT(CASE WHEN status='running' THEN 1 END) AS running,
    COUNT(CASE WHEN status='queued' THEN 1 END) AS queued,
    MIN(CASE WHEN status='queued' THEN created_at END) AS oldestQueuedAt
    FROM jobs WHERE status IN ('queued','running')`).first<{
      lastHeartbeat:number|null; running:number; queued:number; oldestQueuedAt:number|null;
    }>();
  const lastHeartbeat = row?.lastHeartbeat ?? null;
  return {online:lastHeartbeat!==null && lastHeartbeat>checkedAt-90000,
    lastHeartbeat, running:row?.running??0, queued:row?.queued??0,
    oldestQueuedAt:row?.oldestQueuedAt??null, capacity:QUEUE_CAPACITY, checkedAt};
}
