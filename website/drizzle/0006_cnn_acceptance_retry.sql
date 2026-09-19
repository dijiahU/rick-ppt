-- Retry only the newly authorized CNN acceptance task after the verified host fix.
-- Preserve the failed attempt on disk and add a visible explanation; no prior task is changed.
INSERT INTO task_messages (id,job_id,user_id,role,kind,body,attachments,status,created_at,updated_at)
SELECT '86212341-6a43-4d9b-9d5e-c21b3ee61e36',id,user_id,'assistant','chat','Release check: the first attempt stopped before slide authoring because the journal rejected the installed plugin version suffix. Version validation has been corrected and tested. This same task is being retried; its original request and failure record are preserved.','[]','applied',CAST(strftime('%s','now') AS INTEGER) * 1000,CAST(strftime('%s','now') AS INTEGER) * 1000
FROM jobs WHERE id='db69fb9d-5d27-4fc2-9553-a722e2a5acbc' AND status='failed' AND updated_at=1789853316870 AND result_key IS NULL AND user_id=(SELECT user_id FROM jobs WHERE id='2d8c4072-7aee-4f55-8fb0-8f074de4f8cb' AND title='介绍cnn')
ON CONFLICT(job_id,id) DO NOTHING;
--> statement-breakpoint
UPDATE jobs SET status='queued',lease=NULL,summary='resume_requested',updated_at=CAST(strftime('%s','now') AS INTEGER) * 1000
WHERE id='db69fb9d-5d27-4fc2-9553-a722e2a5acbc' AND status='failed' AND updated_at=1789853316870 AND result_key IS NULL AND user_id=(SELECT user_id FROM jobs WHERE id='2d8c4072-7aee-4f55-8fb0-8f074de4f8cb' AND title='介绍cnn')
AND EXISTS(SELECT 1 FROM task_messages WHERE job_id='db69fb9d-5d27-4fc2-9553-a722e2a5acbc' AND id='86212341-6a43-4d9b-9d5e-c21b3ee61e36')
AND (SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running'))<100;
