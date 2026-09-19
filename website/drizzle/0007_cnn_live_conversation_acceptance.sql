-- Site-owner-authorized live conversation acceptance, only for the new CNN case.
-- Explicitly labeled automated feedback; normal leased worker polling/steering applies.
INSERT INTO task_messages (id,job_id,user_id,role,kind,body,attachments,status,created_at,updated_at)
SELECT '7e4a3568-fbc8-40de-8f01-53040228a9df',id,user_id,'user','chat','Automated acceptance check (ordinary chat; no extra deck change requested): briefly explain how this lesson distinguishes its 16 training examples from the 8 held-out examples and why 6 correct held-out predictions do not establish general image-recognition accuracy.','[]','pending',CAST(strftime('%s','now') AS INTEGER) * 1000,CAST(strftime('%s','now') AS INTEGER) * 1000
FROM jobs WHERE id='db69fb9d-5d27-4fc2-9553-a722e2a5acbc' AND status='running' AND user_id=(SELECT user_id FROM jobs WHERE id='2d8c4072-7aee-4f55-8fb0-8f074de4f8cb' AND title='介绍cnn')
AND (SELECT COUNT(*) FROM task_messages WHERE job_id='db69fb9d-5d27-4fc2-9553-a722e2a5acbc')<1000
ON CONFLICT(job_id,id) DO NOTHING;
--> statement-breakpoint
INSERT INTO task_messages (id,job_id,user_id,role,kind,body,attachments,status,created_at,updated_at)
SELECT '4f70ec99-e21c-408e-96f5-a7795aa2eb3a',id,user_id,'user','revision','Automated acceptance feedback during creation: on the training-results slide and its interactive training lab, explicitly show the note "Measured loss can rise between epochs." Use the actually measured loss curve without smoothing away increases. Keep the held-out 6/8 result separate from training accuracy, and visibly label the small dataset as synthetic. Preserve the requested 20-slide scope and the original request.','[]','pending',CAST(strftime('%s','now') AS INTEGER) * 1000,CAST(strftime('%s','now') AS INTEGER) * 1000
FROM jobs WHERE id='db69fb9d-5d27-4fc2-9553-a722e2a5acbc' AND status='running' AND user_id=(SELECT user_id FROM jobs WHERE id='2d8c4072-7aee-4f55-8fb0-8f074de4f8cb' AND title='介绍cnn')
AND (SELECT COUNT(*) FROM task_messages WHERE job_id='db69fb9d-5d27-4fc2-9553-a722e2a5acbc')<1000
ON CONFLICT(job_id,id) DO NOTHING;
