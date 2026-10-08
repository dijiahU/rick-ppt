CREATE TABLE `jobs` (
	`id` text PRIMARY KEY NOT NULL,
	`user_id` text NOT NULL,
	`request_key` text NOT NULL,
	`title` text NOT NULL,
	`brief` text NOT NULL,
	`pages` integer NOT NULL,
	`style` text NOT NULL,
	`status` text DEFAULT 'queued' NOT NULL,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL,
	`lease` text,
	`summary` text,
	`result_key` text,
	`thread_id` text,
	`progress` text,
	`language` text,
	`attachments` text
);
--> statement-breakpoint
CREATE UNIQUE INDEX `jobs_user_request` ON `jobs` (`user_id`,`request_key`);--> statement-breakpoint
CREATE INDEX `jobs_user` ON `jobs` (`user_id`);--> statement-breakpoint
CREATE INDEX `jobs_status_created` ON `jobs` (`status`,`created_at`);--> statement-breakpoint
CREATE TABLE `site_admins` (
	`email` text PRIMARY KEY NOT NULL,
	`user_id` text,
	`display_name` text,
	`created_at` integer NOT NULL,
	`created_by` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `site_admins_user_id` ON `site_admins` (`user_id`);--> statement-breakpoint
CREATE TABLE `task_drafts` (
	`job_id` text PRIMARY KEY NOT NULL,
	`object_key` text NOT NULL,
	`sha256` text NOT NULL,
	`bytes` integer NOT NULL,
	`pages` integer NOT NULL,
	`revision` integer NOT NULL,
	`exported_at` integer NOT NULL,
	`saved_at` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `task_messages` (
	`seq` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`id` text NOT NULL,
	`job_id` text NOT NULL,
	`user_id` text NOT NULL,
	`role` text NOT NULL,
	`kind` text NOT NULL,
	`body` text NOT NULL,
	`attachments` text DEFAULT '[]' NOT NULL,
	`status` text DEFAULT 'pending' NOT NULL,
	`revision` integer,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `task_messages_job_id` ON `task_messages` (`job_id`,`id`);--> statement-breakpoint
CREATE INDEX `task_messages_job_seq` ON `task_messages` (`job_id`,`seq`);--> statement-breakpoint
CREATE TABLE `task_recovery` (
	`job_id` text PRIMARY KEY NOT NULL,
	`checkpoint` text NOT NULL,
	`revision` integer DEFAULT 0 NOT NULL,
	`last_message_seq` integer DEFAULT 0 NOT NULL,
	`resumable` integer DEFAULT 0 NOT NULL,
	`updated_at` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `task_versions` (
	`id` text PRIMARY KEY NOT NULL,
	`job_id` text NOT NULL,
	`result_key` text,
	`bundle_key` text,
	`revision` integer DEFAULT 0 NOT NULL,
	`created_at` integer NOT NULL
);
--> statement-breakpoint
CREATE INDEX `task_versions_job_created` ON `task_versions` (`job_id`,`created_at`);--> statement-breakpoint
CREATE TABLE `worker` (
	`id` text PRIMARY KEY NOT NULL,
	`heartbeat` integer NOT NULL
);
