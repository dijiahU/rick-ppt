# CNN frozen-candidate evidence

Status: the exported candidate passed the checks below. The first independent
review round has finished and requested corrections; the normal author repair
phase is running. Final review and delivery retrieval remain pending.

The 20-page v009 candidate SHA-256 is
`1eeb578add645ca7fc208f432e8231e47d4eab7f5a57d1b60f0e8a8920c5d518`.
Its 20 attached scenes were independently rerun by the host: **194 tests and
679 assertions passed**, bound to the actual source scenes and the immutable
runtime `8635c55584176218c6eadbc829d8796531bc99887469f24f6fc2345130222d37`.
Native validation and renders completed before the audience review began.

Private `cnn-v009-frozen-coverage-01` correlates the C01–C13 teaching criteria,
host receipts, source archive and source-line map. Every scene editor matches its
corresponding delivered-source candidate. The 25-member source archive SHA is
`4df56630ba9f48dd8870ee9d5c4b3d3fe36bc0c58ec9d1d3a3609d6ccf1d32c5`.
The separate final source-line map SHA is
`c7f4ef6bad64659093bbc1ba22e6ad34e12c1f1e8ee041f8badeb979fcc4e7c5`:
multiply/collect/store map to lines 28/29/30, and upstream/bias/kernel/input
gradient operations map to 41/42/46/48. The map binds the exact convolution
source hash; it is retained separately and is not claimed to be inside that ZIP.

An additional real-browser check closes four specific gaps with **95 effective
passing checks** and nine inspected images:

- An actual Monaco infinite-loop edit was run and stopped. The browser worker
  closed before Reset or another run; original code then reproduced
  `[[7,9],[13,15]]` in the visible diagram.
- Keyboard Step and End preserved the corresponding patch, output cell and
  source statement at 1280×720 and 800×600 with the browser reduced-motion
  preference enabled. This authored scene explicitly sets reduced motion false;
  automatic Play still animates. Only the understandable manual path is verified.
- Adding 1000 to all three logits through actual source editing preserved finite
  softmax probabilities and cross-entropy within `4.80e-14`; displayed values
  followed the returned worker result and Reset restored the original program.
- The real backward program and keyboard endpoint showed patch 4 of 4 and `db=4`.

Proof: `proof/cnn-final-g05-g06-20260920T011043Z/review.json`, SHA
`07e49eb2e7d1416d28bf0e855edd1792e450a8118ad13cd42d8db439fcb2f08e`.
The first harness attempt is retained as 81/83: its 200 ms worker-close wait was
too short, and its keyboard focus targeted a wrapper. A corrected harness
observed closure after 2.018 seconds and focused the actual Step button; no scene
or runtime was changed. Its 63/63 result replaces only those affected checks,
without counting repeated assertions as new coverage.

Reuse of this evidence requires exact scene, source, asset and runtime hashes
in the eventually delivered pair. Browser captures and native rendering do not
verify PowerPoint desktop playback.

## First review round and restored website previews

The three independent passes completed on 2026-09-20. The required corrections
are an accurately positioned epoch axis on page 17, visible numerical inputs
and pending-versus-computed input state on pages 8/9/12/13/14, and selected-feature
weights and class-score contributions on page 11. Content revision completed;
the original author thread began applying the changes at 02:19 UTC. Earlier
automated and manual checks do not override these audience findings.

The consolidated review receipt SHA-256 is
`e14d6795fe7d249d59de73b6177de13050ea6a65765b55630d4b0eb4cdb88ee4`.
The first-pass transient error was a context-compaction transport failure;
the original reviewer continued through HTTP fallback and produced a complete
report. It was not an observed hook failure.

The recovered public preview records retained absolute paths into the previous
attempt. The current reporter correctly refused those out-of-scope paths, which
left the website preview list empty. Future executions publish the validated
frozen pages before review (`8a58301`). For this already running attempt, the
host appended new receipts for eight unchanged pages through the ordinary public
journal. Every image matched both its restored file and frozen reviewer image;
the outline page version also matched. The worker published all eight image
hashes, confirmed by read-only website retrieval at 02:26 UTC. Pages whose
outline changed await fresh author renders. Existing records were retained;
no worker restart, direct API mutation or final-review approval was involved.

Private proof: `proof/cnn-preview-resync-o2bnjnlg`. A recovered preview is a
visible work-in-progress page, not acceptance of the corrected final deck.
