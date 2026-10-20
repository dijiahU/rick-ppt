# Chat attachment recovery fix — 2026-10-19

The website and runner attachment parser already accepted ten files per message,
but `workflow/journal.py:Journal.accept_message` still rejected more than three.
A valid seven-attachment revision therefore failed after its files were downloaded
and verified, before the message could be journaled. Retries repeated that failure.

The journal now has an explicit `Limits.message_attachments` default of ten.
Over-limit and empty-message errors are distinct. Descriptor, checksum, path,
size, deduplication and cursor checks remain intact. This does not alter website
quota, attachment ownership, task backend, or the 20 MiB per-file / 200 MiB
aggregate input limits.

Validation: 54 journal tests and 40 conversation integration tests pass, including
ten-file acceptance, durable reopen, idempotent delivery, eleven-file rejection
without state mutation and an explicit lower configured limit.

The background worker was reloaded before the authorized conditional retry.
The same task ID was requeued, preserving its input and quota charge. Its recovered
workspace retains six native pages and its earlier research. The real pending
seven-attachment message was subsequently accepted by the journal. A modification
request can legitimately update planning before continuing existing pages; recovery
does not imply that the old draft already incorporates the new material.
