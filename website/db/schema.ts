import { sqliteTable, text, integer, index, uniqueIndex, primaryKey } from 'drizzle-orm/sqlite-core';
export const jobs = sqliteTable('jobs', {
  id: text('id').primaryKey(), userId: text('user_id').notNull(),
  requestKey: text('request_key').notNull(), title: text('title').notNull(),
  brief: text('brief').notNull(), pages: integer('pages').notNull(), style: text('style').notNull(),
  status: text('status').notNull().default('queued'), createdAt: integer('created_at').notNull(),
  updatedAt: integer('updated_at').notNull(), lease: text('lease'),
  summary: text('summary'), resultKey: text('result_key'), threadId: text('thread_id'),
  progress: text('progress'),
  language: text('language'),
  executionBackend: text('execution_backend', {enum:['api','codex']}),
  attachments: text('attachments'),
}, (t) => [uniqueIndex('jobs_user_request').on(t.userId, t.requestKey), index('jobs_user').on(t.userId), index('jobs_status_created').on(t.status,t.createdAt)]);
export const worker = sqliteTable('worker', { id: text('id').primaryKey(), heartbeat: integer('heartbeat').notNull(), executionBackends:text('execution_backends') });
export const siteAdmins = sqliteTable('site_admins', {
  email: text('email').primaryKey(),
  userId: text('user_id'),
  displayName: text('display_name'),
  createdAt: integer('created_at').notNull(),
  createdBy: text('created_by').notNull(),
}, (t) => [uniqueIndex('site_admins_user_id').on(t.userId)]);
export const taskMessages = sqliteTable('task_messages', {
  seq: integer('seq').primaryKey({autoIncrement:true}), id:text('id').notNull(),
  jobId:text('job_id').notNull(), userId:text('user_id').notNull(),
  role:text('role').notNull(), kind:text('kind').notNull(), body:text('body').notNull(),
  attachments:text('attachments').notNull().default('[]'), status:text('status').notNull().default('pending'),
  revision:integer('revision'), createdAt:integer('created_at').notNull(), updatedAt:integer('updated_at').notNull(),
},t=>[uniqueIndex('task_messages_job_id').on(t.jobId,t.id),index('task_messages_job_seq').on(t.jobId,t.seq)]);
export const taskRecovery = sqliteTable('task_recovery', {
  jobId:text('job_id').primaryKey(), checkpoint:text('checkpoint').notNull(),
  revision:integer('revision').notNull().default(0), lastMessageSeq:integer('last_message_seq').notNull().default(0),
  resumable:integer('resumable').notNull().default(0), updatedAt:integer('updated_at').notNull(),
});
export const taskVersions = sqliteTable('task_versions', {
  id:text('id').primaryKey(),jobId:text('job_id').notNull(),resultKey:text('result_key'),
  bundleKey:text('bundle_key'),revision:integer('revision').notNull().default(0),createdAt:integer('created_at').notNull(),
},t=>[index('task_versions_job_created').on(t.jobId,t.createdAt)]);
export const taskDrafts = sqliteTable('task_drafts', {
  jobId:text('job_id').primaryKey(),objectKey:text('object_key').notNull(),sha256:text('sha256').notNull(),
  bytes:integer('bytes').notNull(),pages:integer('pages').notNull(),revision:integer('revision').notNull(),
  exportedAt:integer('exported_at').notNull(),savedAt:integer('saved_at').notNull(),
});

// Receipts are private operational data; public task serializers never select them.
export const taskUsage = sqliteTable('task_usage', {
 jobId:text('job_id').notNull(),eventId:text('event_id').notNull(),version:integer('version').notNull(),
 source:text('source').notNull(),model:text('model').notNull(),provider:text('provider').notNull(),stage:text('stage').notNull(),usageStatus:text('usage_status').notNull(),
 inputTokens:integer('input_tokens'),outputTokens:integer('output_tokens'),cachedInputTokens:integer('cached_input_tokens'),cacheWriteTokens:integer('cache_write_tokens'),reasoningTokens:integer('reasoning_tokens'),totalTokens:integer('total_tokens'),costMicrousd:integer('cost_microusd'),
 payload:text('payload').notNull(),createdAt:integer('created_at').notNull(),updatedAt:integer('updated_at').notNull(),
},t=>[primaryKey({columns:[t.jobId,t.eventId]}),index('task_usage_job_created').on(t.jobId,t.createdAt,t.eventId)]);

export const modelAccounts = sqliteTable('model_accounts', {
 id:text('id').primaryKey(),userId:text('user_id').notNull(),provider:text('provider').notNull(),label:text('label').notNull(),
 keyHint:text('key_hint').notNull(),secret:text('secret').notNull(),models:text('models').notNull(),createdAt:integer('created_at').notNull(),revokedAt:integer('revoked_at'),
},t=>[index('model_accounts_user').on(t.userId,t.revokedAt)]);
export const taskFunding = sqliteTable('task_funding', {
 jobId:text('job_id').primaryKey(),userId:text('user_id').notNull(),credentialId:text('credential_id').notNull(),provider:text('provider').notNull(),model:text('model').notNull(),version:integer('version').notNull().default(1),createdAt:integer('created_at').notNull(),
});
