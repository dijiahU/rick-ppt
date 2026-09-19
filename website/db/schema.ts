import { sqliteTable, text, integer, index, uniqueIndex } from 'drizzle-orm/sqlite-core';
export const jobs = sqliteTable('jobs', {
  id: text('id').primaryKey(), userId: text('user_id').notNull(),
  requestKey: text('request_key').notNull(), title: text('title').notNull(),
  brief: text('brief').notNull(), pages: integer('pages').notNull(), style: text('style').notNull(),
  status: text('status').notNull().default('queued'), createdAt: integer('created_at').notNull(),
  updatedAt: integer('updated_at').notNull(), lease: text('lease'),
  summary: text('summary'), resultKey: text('result_key'), threadId: text('thread_id'),
  progress: text('progress'),
  language: text('language'),
  attachments: text('attachments'),
}, (t) => [uniqueIndex('jobs_user_request').on(t.userId, t.requestKey), index('jobs_user').on(t.userId), index('jobs_status_created').on(t.status,t.createdAt)]);
export const worker = sqliteTable('worker', { id: text('id').primaryKey(), heartbeat: integer('heartbeat').notNull() });
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
