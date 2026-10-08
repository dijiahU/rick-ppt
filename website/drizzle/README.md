# Website schema snapshot

The current deployed source uses the entries in `meta/_journal.json`, beginning
with `0000_absurd_mongoose.sql`. This initial migration describes a fresh database
with jobs, administrators, drafts, conversation, recovery and version tables.

Earlier SQL files and metadata remain as historical development/acceptance records.
They are not entries in the current migration journal. Use the journal for the
current fresh schema; upgrades of an existing database require a scoped schema
comparison rather than replaying the historical acceptance scripts.
