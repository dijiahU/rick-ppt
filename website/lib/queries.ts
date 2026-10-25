// Single INSERT...SELECT is atomic: quota and global queue admission cannot race.
export const INSERT_JOB = `INSERT INTO jobs (id,user_id,request_key,title,brief,pages,style,language,execution_backend,attachments,status,created_at,updated_at)
SELECT ?,?,?,?,?,?,?,?,?,?,'queued',?,?
WHERE (? = 1 OR (SELECT COUNT(*) FROM jobs WHERE user_id=?) < 10)
AND (SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')) < 100
ON CONFLICT(user_id,request_key) DO NOTHING RETURNING id,execution_backend`;
export const CLAIM_JOB = `UPDATE jobs SET status='running',lease=?,updated_at=?
WHERE id=(SELECT id FROM jobs WHERE status='queued'
AND (execution_backend IS NULL OR (execution_backend='api' AND ?=1) OR (execution_backend='codex' AND ?=1))
ORDER BY created_at,id LIMIT 1)
AND (SELECT COUNT(*) FROM jobs WHERE status='running') < 3
RETURNING id,title,brief,pages,style,language,execution_backend,attachments,lease,summary`;

// Legacy workers cannot consume customer-funded work. API support by itself
// does not prove support for per-user credentials; require version 1 explicitly.
export const CLAIM_ACCOUNT_JOB = CLAIM_JOB.replace(
 `AND (execution_backend IS NULL OR (execution_backend='api' AND ?=1) OR (execution_backend='codex' AND ?=1))`,
 `AND ((NOT EXISTS(SELECT 1 FROM task_funding WHERE job_id=jobs.id)
 AND (execution_backend IS NULL OR (execution_backend='api' AND ?=1) OR (execution_backend='codex' AND ?=1)))
 OR (execution_backend='api' AND ?=1 AND EXISTS(SELECT 1 FROM task_funding WHERE job_id=jobs.id)))`
);

// Explicit operator retry of one unchanged failed attempt. Reuses its row/quota.
export const RETRY_JOB = `UPDATE jobs SET status='queued',lease=NULL,progress=NULL,summary=NULL,updated_at=?
WHERE id=? AND status='failed' AND updated_at=? AND result_key IS NULL
AND (SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')) < 100
RETURNING id,status,execution_backend`;
