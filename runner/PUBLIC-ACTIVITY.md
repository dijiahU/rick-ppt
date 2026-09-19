# Public progress contract

See PROGRESS.md for the task-visible native workflow. The host publishes only explicit public notes, a validated substantive outline, page PNGs and independent review states. It never publishes raw assistant reasoning, source notes, local paths, commands, credentials or host thread IDs.

outline.py validates stable page IDs, bounded public titles/summaries and presentation order. Reporter clears a preview when its corresponding page content or global style changes. New previews must carry the current content version. The website keeps the outline visible before images exist and each page summary alongside its eventual preview.

Public notes use an append-only bounded journal. Transport failure is retryable and independent of authoring validity. Only allowlisted tool activity is exposed. Final preview bytes come from the frozen reviewed artifact, replacing intermediate drafts.

The content reviewer reads the actual audience surface before the brief or sources; visual review reads full-size pages and the sequence. Status reports distinguish pending, reviewing, required corrections, reviewed and partly unverified. Without a real target player, motion playback remains unverified even if static render and native timing pass.

The existing user/administrator/review authorization checks, quota and download ownership remain unchanged. Old progress records without an outline remain readable. No database migration is required.
