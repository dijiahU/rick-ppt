# Manual PowerPoint verification

Current status: **not desktop-verified**. Browser evidence and native static
renders are retained separately. Do not mark this checklist complete from them.
Run on a copy of the delivered PPTX and preserve the source and previous exports.

## Setup and evidence

- [ ] Record OS, PowerPoint build, add-in/runtime version and PPTX/bundle SHA-256.
- [ ] Run `interactive doctor`; install/trust the local development certificate.
- [ ] Start the bundle with its platform helper and check its HTTPS health URL.
- [ ] Sideload the XML ContentApp manifest using the target Office procedure.
- [ ] Open the native presentation and record any repair or security prompt.
- [ ] Confirm editable native title/formula/context and readable static fallback.

Microsoft setup references:
[Mac sideloading](https://learn.microsoft.com/en-us/office/dev/add-ins/testing/sideload-an-office-add-in-on-mac),
[Windows sideloading](https://learn.microsoft.com/en-us/office/dev/add-ins/testing/create-a-network-shared-folder-catalog-for-task-pane-and-content-add-ins),
[Content Add-ins](https://learn.microsoft.com/en-us/office/dev/add-ins/design/content-add-ins).

## Actual interaction

- [ ] Load every Content region and confirm its deck, scene and instance identity.
- [ ] Click a control and verify the expected numeric result.
- [ ] Drag a shape; verify the position after resize/zoom and nested transforms.
- [ ] Change a slider and verify linked state, labels and diagram geometry.
- [ ] Use keyboard focus, activation and a declared key interaction.
- [ ] Edit and run code; check stdout/result, error handling, stop and reset.
- [ ] Play, pause, seek and reset a meaningful animation step.
- [ ] Play local media and verify controls/cues where used.
- [ ] Exercise every optional pack used by this deck, not only its loading screen.
- [ ] Confirm separate regions and duplicated scenes do not share unintended state.
- [ ] Repeat the important operations in actual slide-show mode.

## Persistence and failure cases

- [ ] Save a fresh copy; close PowerPoint completely and reopen it.
- [ ] Verify settings identity and declared saved state after reopening.
- [ ] Confirm new state does not replace the lesson's explicit Reset defaults.
- [ ] Confirm the native fallback remains readable when the runtime is stopped.
- [ ] Restart the runtime and confirm the scene reconnects correctly.
- [ ] Confirm a mismatched or corrupt scene hash reports an error.
- [ ] Export PDF and inspect every native page and fallback independently.
- [ ] Stop using the bundle helper; verify unrelated applications remain running.

Record each item as passed, failed or not tested with evidence and target build.
Mac results do not certify Windows or Office Web. Never overwrite the original
deck just to test settings persistence.
