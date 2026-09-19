# Inspect a delivered interactive lesson without executing it

`inspect-case-artifacts.py` compares the separately delivered PPTX with the
presentation inside its ZIP, inspects native OOXML and scenes, and creates a new
proof directory for an independent reviewer. It never starts the copied runtime,
imports bundle Python, evaluates scene expressions, or runs teaching/plugin code.
Use the trusted checkout's plugin Python environment:

```sh
pptx-agent/.venv/bin/python runner/inspect-case-artifacts.py \
  --pptx /absolute/path/delivered.pptx \
  --zip /absolute/path/delivered-interactive.zip \
  --expected-pages 20 \
  --evidence-root /absolute/path/frozen/workspace/interactive \
  --proof /absolute/path/new-independent-proof
```

Use `--expected-pages 18` for the YOLO brief. The proof directory must not already
exist, its parent must exist, and it must be outside the source evidence directory.
Existing files are never overwritten. All input files and ancestors must be free
of symlinks. The two delivered files are hashed again after inspection to detect
changes during the run.

The optional `--evidence-root` is the exact frozen `interactive` directory with
`tests/SCENE.json` and `renders/GENERATION/{report.json,*.png}`. A portable bundle
is not required to contain these host-side receipts. Omitting them makes the
evidence result incomplete; it does **not** make an otherwise valid ZIP corrupt.
Formal CNN/YOLO acceptance should provide the host-frozen directory alongside the
downloaded artifacts.

The report separates three mechanical results:

- `structureChecksPassed`: exact PPTX byte equality; bounded, portable ZIP paths;
  complete checksum inventory; all distributed hashes; expected page count;
  trusted native package structural validation; Content Add-in identities,
  bounds, fallbacks and scene hashes; formally valid scene JSON and nonempty
  test plans with supported observation/assertion types.
- `caseDeclarationsComplete`: editable native title/context candidates on each
  slide, declared code pack and writable CodeEditor, code worker distribution,
  timelines, learner controls and numeric assertions. These are declarations and
  native text-shape facts, not proof that the teaching behavior is correct.
- `evidenceConsistencyPassed`: test names/counts match each exact scene; receipt
  runtime fingerprint matches the runtime distributed in this ZIP; required
  initial, per-test and reset PNGs have matching SHA-256, dimensions and valid
  bounded pixel decoding. Each receipt matches a `report.json` under the supplied
  `renders` directory. Its author-controlled `directory` field is never followed,
  so previously generated evidence can also be relocated safely.

`inspection.json` contains all native text, shape positions, scene-to-slide
mappings, complete test actions/assertions, exact expected numeric values,
languages, editor bindings, line highlights, timelines and learner controls.
Literal editor source is copied to passive `.txt` files. `REVIEW.md` links a sample
of initial/intermediate/reset captures; all capture hashes are inventoried even
when not sampled. Native fallback PNGs and copied scene JSON are also retained.
Receipt success booleans are recorded under `authorClaimsNotTrusted`.

Exit codes:

| Code | Meaning |
| --- | --- |
| `0` | Structure, declarations and evidence links are ready for manual review. |
| `2` | Input or artifact structure failed. A created proof retains the failure report. |
| `3` | Structure is intact, but case declarations or separate evidence are incomplete. |

**Exit 0 is not a lesson acceptance pass.** A forged but internally consistent
receipt cannot authenticate execution. The inspector always leaves browser,
PowerPoint playback, content and visual review as `not-run`; mathematical values
are listed for independent comparison, not certified. Native title/context roles
are position/placeholder candidates. A footer can be a context candidate, and
group transforms or inherited placeholder positions may need manual inspection.
Review native editable meaning and legibility explicitly.

The next acceptance stage uses a trusted host to replay tests, operates Monaco
with real keyboard input and verifies changed outputs/reset, observes animation
intermediate states, and reviews all lesson content and native slide renders.
Desktop PowerPoint playback remains a separate host check.

Limits: 50,000 ZIP members, 2 GiB expanded data per archive, 512 MiB per member,
8 MiB JSON, 30 MiB / 20 million pixels per PNG, 10,000 receipt captures and 2 GiB
total capture evidence. Sampled PNG copies and distinct fallback copies each have
a 512 MiB limit. ZIP symlinks, devices, encryption, traversal, Unicode/case aliases,
duplicate paths, file/directory conflicts and unlisted files are rejected.

Run boundary tests:

```sh
pptx-agent/.venv/bin/python runner/test-inspect-case-artifacts.py -v
```

The tests construct an intentionally passive one-slide fixture. Its fake success
claims never become execution/content/visual approval. Tests also cover altered
PPTX bytes, checksum omissions/tampering, stale runtime hashes, changed captures,
relocated versus escaping evidence, symlinks, invalid plans and preserved proofs.
