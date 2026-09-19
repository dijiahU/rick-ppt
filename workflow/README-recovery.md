# Durable task recovery

`journal.py` is a Python 3.11 standard-library host component for the PPTX worker.
It does not launch Codex, claim a queue job, charge quota, modify delivered files,
or replay commands from a trajectory. Keep its storage outside the task sandbox.
The worker must own the website lease **and** hold the journal context for the
whole attempt. The filesystem lock is additional protection, not a substitute for
the server's lease check.

## API and integration boundaries

```python
from journal import Journal

with Journal(host_records / "journals", task["id"],
             plugin_version=installed_version, run_id=trajectory.run_id) as j:
    # Keep author files and durable phase/review results below job. A separate
    # reviewer may see a limited copy, but its receipt returns to job/receipts/.
    if not j.can_reuse("research", job):
        j.begin_phase("research", job)
        # Record the trusted app-server receipts immediately, not at phase end.
        j.bind_session(thread_id, turn_id)
        # Host validates outline/research outputs before recording completion.
        j.complete_phase("research", job,
                         artifacts=["outline.json", "research.json"],
                         next_phase="author")
```

Public and private data are deliberately different:

- `state` is a private copy containing workspace paths, Codex thread/turn IDs,
  user text, attachment descriptors, artifact hashes and protocol receipts.
- `public_status()` returns only allowlisted identifiers, lifecycle state,
  revision/cursors and message delivery states. It omits user text, paths, thread
  and turn IDs, raw errors, credentials, prompts, and reasoning. Supply actual
  host credentials through `secrets=(...)` solely for redacting any accidental
  occurrence in an allowed identifier. Never put credentials in message text or
  journal metadata.
- `artifacts(job, relative_paths)` hashes only regular files opened through
  directory descriptors without following symlinks. Successful hashing is a byte
  receipt, **not** semantic validation. The caller runs native/runtime/content
  checks before `complete_phase()` or `mark_applied()`.

`begin_phase(name, job, thread_id=None)` records the current revision and stage.
`bind_session(thread_id, turn_id=None)` stores trusted protocol receipts.
`checkpoint(job, reason="stable_snapshot")` captures verified file bytes. Use it
at stable boundaries and periodically while producing content; a file actively
changing during capture causes rejection, leaving the preceding checkpoint
usable. `interrupt(reason="worker_interrupted")` records an orderly interruption.
A hard kill needs no final callback: recovery sees the previously committed
running phase and resumes from the last durable checkpoint.

`complete_phase(name, job, artifacts=[...], next_phase=..., revision=...)` commits
a stage only when its revision is current, all requested corrections are applied,
and artifact bytes still match the new checkpoint. By default it uses the revision
from phase start; an explicit current revision is necessary when live steering
changed the input. `can_reuse(name, job)` requires both the current revision/plugin
version and every required artifact hash/size to match. All stages are
conservatively invalidated by an input-changing message; phase-specific selective
invalidation can be added later without weakening this guarantee. Intermediate
research/author boundaries may explicitly set `require_applied=False`: this
certifies current phase artifacts while preserving a delivered correction as
`acknowledged` until final review. It still rejects accepted, delivering or
uncertain corrections. Final delivery uses the strict default and never presents
mere acknowledgement as a completed edit.

## Inbox and live delivery

Map the website's user messages to the journal as follows:

```python
message = j.accept_message(
    row["id"], row["body"], cursor=row["seq"],
    changes_input=row["kind"] == "revision", attachments=[
        # Download and verify the bounded owner-authorized attachment into job.
        {"id": attachment["id"], "path": local_relative_path,
         "sha256": attachment["sha256"], "bytes": attachment["size"],
         "name": attachment["name"]},
    ],
)
for message in j.pending_messages():
    # Commit BEFORE writing the RPC. Include this stable message ID in the
    # protocol input marker so a resumed thread can prove it accepted the input.
    j.begin_delivery(message["id"], rpc_request_id, thread_id, active_turn_id)
    receipt = transport.steer_or_start(...)
    j.acknowledge_message(message["id"], request_id=rpc_request_id,
                          turn_id=receipt.turn_id)
    # Only now POST the idempotent website ack. Retry a failed website ack; do
    # not resend the model instruction.

# After revised artifacts have passed the host's validation:
j.mark_applied([message_id], job, artifacts=["output/presentation.pptx",
                                           "output/validation.json"])
# POST website applied acknowledgement using the validated revision.
```

Attachments must be downloaded and hash-verified by the worker before delivery;
`accept_message()` validates their scoped descriptor, not bytes which may not
have arrived yet. The descriptor accepts only `id`, relative `path`, `sha256`,
`bytes`, and optional `name`/`media_type`. No arbitrary remote metadata is stored.
The journal revision is a local monotonic revision number. The portal's global
message sequence may contain gaps: retain `message_cursor` for polling and use
the portal's revision sequence separately when acknowledging its API.

The states are `accepted → delivering → acknowledged → applied`. The host commits
`delivering` before sending, so a lost response cannot silently make a delivered
message pending again. After a restart, `delivering` becomes `uncertain`.

`reconcile_message(id, outcome=..., evidence=...)` is the transport integration
hook. Supported outcomes:

- `accepted`: a matching stable message marker or trusted protocol receipt proves
  the thread received it; acknowledge without resending.
- `not_received`: a definitive protocol rejection or equally strong evidence
  proves non-acceptance; the message may be sent again.
- `unknown`: preserve `uncertain`; do not blindly resend, discard, or mark applied.

Merely failing to find a message in an incomplete event page is **not** proof of
absence. A transport race with turn completion must be reconciled before choosing
`turn/steer` or `turn/start`. Ordinary chat can use `changes_input=False` and can be
marked applied without artifact paths once its answer is complete. A message
that requests a change must use `changes_input=True`, even if the UI initially
classified it as chat; the caller should classify it before accepting it.

## Recovery

```python
with Journal(host_records / "journals", task_id) as j:
    plan = j.recover(new_attempt_directory,
                     plugin_version=installed_version,
                     recovery_id=website_resume_request_id)
    # Verify/repair restored native and interactive workspaces first.
    # Resume plan["preferred_thread_id"] if present and available. Tell Codex
    # that files were restored to a sampled checkpoint and need inspection.
    # If the thread cannot be resumed, create a fresh thread with the brief,
    # verified current files, stage receipts, and accepted/applied message ledger.
    # Do not feed archived shell commands back to a shell.
    # Continue with plan["next_phase"], checking can_reuse() for completed stages.
```

Recovery verifies every content-addressed blob and the snapshot's manifest hash
before creating the destination. The destination must not exist. Originals,
earlier attempts and immutable events remain intact. A repeated recovery request
ID raises `AlreadyRecovered`; a simultaneous owner raises `JournalBusy`.
Recovery retains the lock after returning so another worker cannot enter during
validation/resumption. It never infers that a completed phase's thread should be
reused for a fresh reviewer.

The plan explicitly reports `snapshot_atomic=False` and
`validation_required=True`: stable individual bytes do not imply a transactional
whole-workspace snapshot. If the checkpoint predates an already applied edit,
the missing artifact receipt moves that message back to `acknowledged` and places
its ID in `requires_reapplication_message_ids`. The resumed model must inspect
and reconstruct the lost edit from durable context; its instruction is not
silently sent a second time. The applied cursor is recomputed accordingly.

Plugin versions must match by default. An explicit
`allow_plugin_upgrade=True` creates a fresh-context recovery, increments the input
revision, and prevents old stage receipts from being reused. The host is still
responsible for validating any native/scene schema migration. Version metadata
accepts safe release labels and Codex cachebusters such as
`0.1.0+codex.20260919212441` (maximum 120 ASCII characters); it is never a path or
an identifier. Task, run, thread and checkpoint ID restrictions are unchanged.
The runner exercises the installed manifest version through journal creation,
checkpoint, reopen and recovery before claiming a task. An empty `events/`
directory left by failed initialization is retained and can initialize normally;
committed histories and orphan projections must still verify. Historical
trajectory v2 snapshots can first be restored with the existing
`trajectory_replay.py restore` into a new directory and inspected; then initialize
a journal and checkpoint that verified workspace. The trajectory's replay tool
does not itself resume a phase or a model.

## Storage and failure behavior

Each task has a private directory containing `.lock`, immutable
`events/00000000000000000001.json` records, an atomic `state.json` projection,
immutable snapshot manifests, and content-addressed `blobs/`. An event is
published atomically and fsynced before updating the projection. A kill between
those operations is recovered from the committed hash chain. Incomplete hidden
temporary files are ignored and retained; committed corruption is rejected.
There is no archive cleanup or retention deletion in this module.

Default limits: 128 MiB per file, 1 GiB per checkpoint, 25,000 files/directories,
32 MiB per record, 64 KiB per message, 5,000 messages and 100,000 events. Use the
`Limits` dataclass to set stricter deployment limits. `.git`, `.venv`,
`node_modules`, `__pycache__`, and `font-cache` directories are excluded and
reported. All other symlinks/non-regular files, traversal, path collisions and
unstable file bytes are rejected. Recovery verifies hashes again while copying
and never restores elevated permission bits. The implementation targets the
macOS/Linux host runner (`fcntl` locking); it is not a Windows worker port.

## Verification

```sh
python3.11 -m unittest discover -s workflow -p 'test_journal.py' -v
```

40 tests cover an actual `SIGKILL` and restart, process exit between event and
projection commit, phase reuse, stale revisions, ambiguous message delivery,
deduplication, idempotent recovery, hash corruption, symlinks, path traversal,
bounds, lock exclusion, originals, public redaction, and recovery of lost edits.
These are engine tests; queue/API integration and a real Codex interruption are
separate smoke gates.
