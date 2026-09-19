export const QUEUE_CAPACITY = 3;
export type QueueHealth = {
  online: boolean;
  lastHeartbeat: number | null;
  running: number;
  queued: number;
  capacity: number;
  oldestQueuedAt: number | null;
  checkedAt: number;
};
export type QueueReason = 'offline' | 'busy' | 'waiting' | 'idle';
export function queueReason(queue: QueueHealth): QueueReason {
  if (!queue.online) return 'offline';
  if (!queue.queued) return 'idle';
  return queue.running >= queue.capacity ? 'busy' : 'waiting';
}
// Match the claim query's FIFO tie-break exactly. Filtering/pagination must not
// change a task's position in the global queue.
export const QUEUE_POSITION_SQL = `CASE WHEN jobs.status='queued' THEN
  (SELECT COUNT(*) + 1 FROM jobs AS ahead WHERE ahead.status='queued'
   AND (ahead.created_at < jobs.created_at OR (ahead.created_at = jobs.created_at AND ahead.id < jobs.id)))
  ELSE NULL END`;
