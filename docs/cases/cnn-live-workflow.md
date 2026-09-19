# CNN live workflow checks

These are observations from the authorized new
[CNN task](https://rick-ppt.woodsy-crane-8759.chatgpt.site/jobs/db69fb9d-5d27-4fc2-9553-a722e2a5acbc).
They do not approve its unfinished teaching deck.

## Controlled interruption and continuation

After the first actual scene render passed three browser cases, the host retained
a 171-file checkpoint containing the authoring generator, scene, source programs,
research, native workspace and capture. The operator verified the task's active
author phase and the app-server child's parent, process group and working
directory, then sent SIGTERM only to that owned author process group. The queue
supervisor stayed running. This was a deliberate recovery test.

The runner recorded an interrupted author phase and a new checkpoint. Read-only
review confirmed the same website task had failed without a delivered artifact.
The authorized worker retry endpoint then requeued that exact task using its
observed failed-attempt timestamp. No new task or quota admission was created.

Observed continuation:

- The same task ID resumed in a new attempt directory; the old directory remains.
- The real app-server resumed the same author thread with a new turn ID.
- The completed research receipt was reused unchanged. There is still only one
  research phase; continuation began at authoring.
- Eight selected restored source/artifact files exactly matched their prior
  SHA-256 values. The same eight originals also remained unchanged.
- The plugin stayed `0.1.0+codex.20260919214127`, with runtime fingerprint
  `fd43ec226d321db43f884afa598bc9f1ae2d2f34e20cafbf24fbc1d00a7c79de`.

The selected files cover the outline, source notes, scene generator, first scene,
complete training source, independently audited reference, actual initial scene
capture and protected original PPTX. The journal additionally verifies every blob
while restoring the checkpoint. This proves initial continuation from saved work;
final artifact validation remains pending.

### Native rendering after recovery exposed a Mac path boundary

The resumed author could read and extend its files, but its first native render
was rejected before Docker started. The supervisor retained `/var/folders/...` as
the recovered task root while the native input and output paths resolved to
`/private/var/folders/...`. A lexical containment check treated these aliases of
the same directory as different roots. Fresh tasks already canonicalized this
path; the recovery call site did not.

The recovery supervisor now resolves the temporary parent before creating the new
attempt. A regression exercises the actual supervisor with a symlinked temporary
ancestor, real journal recovery and the real render broker. Scoped conversion is
accepted; outside-task input and output are still rejected. The eight recovery,
seven trajectory-artifact and six trajectory checks passed. A separate minimal
reproduction demonstrated zero converter calls with the old alias and one with
the canonical root. This is a host recovery fix, not a relaxation of containment.

The failed attempt and requests are retained. A synthetic recovery through the
corrected supervisor then passed actual isolated Docker/LibreOffice conversion:
the copied trusted blank produced a valid one-page PDF, both outside-task requests
were rejected before Docker, and original/restored input hashes stayed unchanged.
This verifies the broker fix, not the unfinished CNN slide visuals.

The operator drained the old supervisor, retained its interrupted checkpoint and
requeued the same CNN task after the replacement passed startup isolation checks.
Seven selected source/artifact hashes matched in the new restored directory and
the old directory. The saved input revision is now 3, so the workflow is checking
the restored outline/evidence against those edits before resuming the interrupted
author thread. The prior notes and completed research receipt remain retained;
the completed revision-3 revalidation then resumed the same interrupted author
thread with a new turn. All seven selected old files remain unchanged; five
versioned/artifact copies still match after continuation, while the current
outline and notes were deliberately revised. Final delivery remains pending.
The plugin/runtime bytes were unchanged by the supervisor correction.

## Conversation during resumed authoring

Website version 27 deployed successfully from source
`268cc7260f4089e3468a16d8b0d574c81247b0cd`. Its narrowly scoped additive migration
created explicitly labeled automated acceptance messages only for this running
CNN task under the original request's owner. The normal leased worker polling and
Codex steering path then delivered all three into the active resumed author turn:

| Message | Kind | Observed state |
| --- | --- | --- |
| `7e4a3568-fbc8-40de-8f01-53040228a9df` | Ordinary chat about training versus held-out evidence | Public answer observed; marked applied after the completed revision-3 content turn |
| `4f70ec99-e21c-408e-96f5-a7795aa2eb3a` | Keep actual loss increases and label the synthetic results | Acknowledged; final artifact application pending |
| `95f3e650-f1a7-4e0c-b0ca-d2e609ac464e` | Complete C04/C05/C06/C10 experiments and nondifferentiability explanations | Acknowledged; final artifact application pending |
| `47ad4991-89ca-4398-8bfd-c5e292ed07b3` | Correct scan highlights, manual-timeline continuation and actual source-line highlights | Acknowledged in website v28; final application pending |
| `132c625d-e876-4412-a98e-1b0229e3b570` | Repair remaining v005 formula-subscript clipping | Acknowledged after website v29; application pending |

The durable input revision advanced from 0 to 3; ordinary chat did not increment
it. The author publicly answered the ordinary chat, distinguishing the 16 training
examples from eight separate held-out examples and limiting the accuracy claim
to that synthetic sample. The completed content turn applied the answered chat;
all three revision messages remain acknowledged pending artifact application.
Acknowledgement is not an applied edit. Final scene/native content, review
receipts and applied message states must establish the requested corrections.

The v003 scan/backward animation checks subsequently passed 258 assertions with
19 captures, including actual clock continuation and rendered source highlights.
Those checks still found clipped formulas. The v005 visual revision fixed the
scan formula and the first native page's overlapping text, but actual screenshots
still showed clipped summation subscripts in pages 15 and 16. A descendant-glyph
check found about 4.52 px beyond the formula region; an outer KaTeX-box test alone
would incorrectly pass. Website v29, source
`37ef401849d5a11d3cde56b7f146657e766d5e92`, adds a labeled request to reposition and
enlarge those formula regions, preserving the verified mathematics and animation.
Its six synthetic migration checks verify scope, idempotence and unchanged jobs.
This is another pending correction, not final visual approval.

The fourth input was admitted by website v28 from source
`4e1d2c7fd55841747a72a71ee21a3dc8258e0cec`. Independent draft checks found that
all four convolution output cells shared a row-only highlight predicate, and
Step/Scrub changed the displayed playhead without seeking the timeline. Actual
engine replay showed `1000 ms → Play + 16 ms → 16 ms`, instead of `1016 ms`.
The feedback asks for corrected row-and-column highlights, a visible moving
input patch, timeline continuity and operation-specific source highlights.

Version 28 also includes a narrow [RSC dependency patch](../website-dependency-review.md).
All 31 isolated website checks, TypeScript, production build and the real local
desktop/mobile conversation/upload/reconnect/resume check passed. This local UI
test used synthetic fixtures and does not change the production-browser limitation.

Production message admission here used an owner-authorized data migration,
not browser form clicks. The production browser connection is unavailable: the
installed Edge automation extension is disabled. Upload/UI behavior has separate
local route/browser and live isolated-phase evidence; this exercise does not
claim production form or file-upload interaction.

## Actual delivery retrieval

Version 27 also adds optional, separate read-only retrieval of the current ZIP
paired to the current PPTX. Both ETags and an opaque delivery-version identifier
must match, and the client rechecks metadata after download. The route never
claims queue work or initializes database tables. Fifteen client checks, isolated
real authorization/route checks, the actual site's TypeScript check and production
build passed. The upgraded read-only CLI was installed with its previous files
backed up; its credential file was unchanged and was not copied.

An actual production `fetch --bundle` during this unfinished task correctly
reported `not_completed`. Downloaded final PPTX/ZIP bytes and their matching
inspection remain pending.
