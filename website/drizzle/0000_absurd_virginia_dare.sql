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
	`thread_id` text
);
--> statement-breakpoint
CREATE UNIQUE INDEX `jobs_user_request` ON `jobs` (`user_id`,`request_key`);--> statement-breakpoint
CREATE INDEX `jobs_user` ON `jobs` (`user_id`);--> statement-breakpoint
CREATE INDEX `jobs_status_created` ON `jobs` (`status`,`created_at`);--> statement-breakpoint
CREATE TABLE `worker` (
	`id` text PRIMARY KEY NOT NULL,
	`heartbeat` integer NOT NULL
);
