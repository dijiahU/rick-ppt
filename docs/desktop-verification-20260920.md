# Desktop verification status

Status: **PowerPoint artifact playback remains unverified**. Browser/runtime,
native rendering and file-integrity results do not substitute for this check.

The original Computer Use helper failed during native-pipe startup. A reversible
update to the newer official helper bundled with ChatGPT restored accessibility
trees and screenshots. Both applications have the same bundle identity and
designated signature requirement; signatures verify. All 167 original inventory
entries are preserved in a private backup. No permissions or security settings
were changed, and the underlying startup cause is not established.

The official interface opened PowerPoint. Subscription offers were skipped;
no trial or purchase was started. Its local file chooser displayed the two-page
smoke deck's native preview, but Open remained disabled for both the original
temporary path and a byte-identical new desktop copy. This is not a successful
open in PowerPoint's document editor or slideshow. The matching local TLS server
returned HTTP 200 and used the final runtime fingerprint. The original PPTX is
unchanged, SHA-256
`d7c7772e3724d6e0d4596103f8a50bc62b3e249ed1782fe28c51394294984ba9`.

Subsequent file-dialog operations timed out or closed the helper pipe. Two actual
helper crash reports share `EXC_BREAKPOINT / SIGTRAP`, signal 5, with
`_dispatch_assert_queue_fail`, Swift isolation checks and a display-link callback
in the faulting stack. This establishes a helper-process failure; the precise
trigger and PowerPoint's disabled Open control remain unexplained. It is not
evidence that a subscription purchase is necessary. A later fresh official
connection again showed PowerPoint's startup window with the file dialog closed.

Private proof `proof/desktop-smoke-20260920-869_0vce` retains the attempted steps
and server identity; `release-backups/computer-use-official-update-af1zywp3`
retains both version inventories and the original signed application. Crash
reports remain local and unchanged. Repeated attempts on the crashing path have
stopped while independent website and teaching checks continue.

Pending direct checks remain load/interaction, slideshow focus, code editing,
drag/slider controls, save/reopen and Office setting persistence. Windows and
Office Web are also unverified. See the
[actual-host checklist](manual-powerpoint-verification.md).

Microsoft's [current platform support table](https://learn.microsoft.com/en-us/javascript/api/requirement-sets#powerpoint),
checked 2026-09-20, lists Content add-ins for PowerPoint on Mac. That documented
support does not establish successful playback of these artifacts, and the
automation failure above is not evidence that the extension point is unsupported.
