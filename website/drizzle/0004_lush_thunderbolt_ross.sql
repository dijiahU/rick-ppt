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
CREATE INDEX `task_versions_job_created` ON `task_versions` (`job_id`,`created_at`);