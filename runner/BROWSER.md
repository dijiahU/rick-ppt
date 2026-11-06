# Local worker browser connection (experimental)

The desktop chat and an independent worker do not automatically share browser
authorization. The connection diagnostic reuses the installed official Edge
extension through its supported browser client. It does not read or copy browser
cookies/profile databases or change website permissions. Normal author/reviewer
processes do not receive direct browser access.

Check installed components without a model call:

```sh
python runner/browser_runtime.py
```

Run one bounded local Codex connection check, with a new output directory:

```sh
python runner/browser_runtime.py --probe-connection /private/tmp/rick-browser-check --model gpt-6-astra --effort high
```

This only connects and lists session-owned tabs. The receipt intentionally keeps
website access and login inheritance `not_tested`; a completed model turn is not
proof of authenticated search. The model's connection report is labeled as such.

The exact installed browser/chrome packages and bundled Node dependencies get
read access in a dedicated temporary task. On macOS the exact system OpenSSL
configuration path is readable so Node can initialize. Only this dedicated
process explicitly opts in to the Node MCP; ordinary workers still disable all
inherited MCP servers, and filesystem/network isolation is unchanged.

For website access, review **ChatGPT desktop → Settings → Browser → Agent
permissions → Website permissions**. Rick's 26.825.32147 UI exposes the per-site
controls there; its Computer Use panel does not show an Edge Manage button.
Other UI versions may expose **Computer Use → Manage** beside the browser.
Review the exact site's Browse permission using the available UI.
Use the site's persistent permission if unattended access is intended. A missing
popup in a standalone worker is not approval. A policy rejection must stop the
attempt; do not retry through another transport or browser surface. See the
[official browser extension documentation](https://learn.chatgpt.com/docs/chrome-extension).
The alternative settings entry is documented in the
[official Settings reference](https://learn.chatgpt.com/docs/reference/settings).

Observed on 2026-11-03: connection succeeded after the component configuration
fix, but site navigation was initially rejected after about 30 seconds without
a visible prompt. After Rick configured the Xiaohongshu website permission in
the Browser panel, a new independent worker completed navigation, screenshot
capture and DOM inspection in 146 seconds. The requested search results were
visible with no login barrier. This is a specific-site access test, not evidence
that every site, browser state or future session is authorized.

The subsequent full research-tool test did not complete: one attempt exceeded
the four-minute cap while inspecting a work; another encountered browser
unavailability. A later connection probe succeeded, but navigation then returned
`net::ERR_INTERNET_DISCONNECTED`. A subsequent attempt reached the work and
captured it, but the screenshot contained JPEG bytes under a `.png` name and
the initial PNG-only importer rejected it. The importer now verifies the actual
PNG/JPEG format and preserves the bytes with the matching suffix and MIME type.
The final live tool call completed in 208 seconds and returned one actual JPEG
in an `inputImage` block, with matching saved bytes/hash. The local production
settings are enabled; the worker remains off on battery under the existing
AC-only policy. This checks the research tool, not a whole website PPT job or
long-term unattended reliability.

## Optional production tool

The host-only `browser_research` setting enables `pptx_browser_sources` in
research/author/repair phases. Set it in the private settings actually selected
by the production launcher (not in a task file):

```json
{"browser_research":{"enabled":true,"browser":"edge","site":"https://www.xiaohongshu.com","model":"gpt-6-astra"}}
```

To opt in to the separately authorized Pinterest and X routes, use `sites`:

```json
{"browser_research":{"enabled":true,"browser":"edge","sites":["https://www.xiaohongshu.com","https://www.pinterest.com","https://x.com"],"model":"gpt-6-astra"}}
```

The legacy single `site` setting still works. The author can select only an
enabled site; omitting it retains the first configured site. This is a fixed
allowlist, not permission to browse arbitrary domains. Pinterest redirected to
`https://jp.pinterest.com` on this Mac, so that exact regional origin needed its
own operator approval. Both www and jp Pinterest public Pin/search paths are
supported; other regional origins remain unverified and excluded.

After those approvals, live Edge tests on 2026-11-03 completed X's visible-UI
search and screenshot in 243 seconds and Pinterest's in 285 seconds. Both were
search-result previews, not full-work or video inspections. The production helper
uses the search URLs observed in those tests, avoiding the repeated homepage,
search-field and submit actions. Public reference captures should exclude
the signed-in user's account and private controls; otherwise the helper returns text
evidence only. A subsequent Pinterest production-tool call opened a Pin and
returned actual JPEG input in 203 seconds, but its tight crop was mostly blank.
That proves transport, not a usable visual reference. The helper now prefers a
broad content region, inspects emitted pixels and may correct an invalid capture
once within the same time limit. If no useful view is obtained, it must retain
the limitation and return no source screenshot. This is an instruction to the
helper, not an automatic aesthetic score from image dimensions or file hashes.
A follow-up uncropped viewport test of that same Pin showed the main report
image normally, separately from related thumbnails. It does not prove whether
the earlier bad framing arose from layout movement or screenshot coordinates.
The local production settings now include all three sites; normal AC-only
worker startup still applies. No complete PPT quality experiment was run here.

Absent/disabled settings preserve prior behavior. Customer-funded and DSH tasks
never use this operator account. The helper uses a separate, bounded local Codex
context with the exact component grants above. It reserves access per job/batch, retains
same-context results, stops on policy denial, and returns source evidence and
the selected reference screenshot via the existing tool-result image channel
(one correction is permitted; the importer accepts up to three named captures). File
hashes and successful transport writes are logged separately from model claims
about inspection or design quality. Public source URLs omit signed query tokens.
The requested query/purpose cannot select another browser or credential. The
optional site argument is restricted to the host's enabled list. Failure on one
site does not authorize switching to another site to bypass that restriction;
independent research on another explicitly enabled site remains possible.
Known disconnect, network and missing-runtime tool failures stop the current
request immediately and return a stable reason code. Error text can arrive in the
MCP result even when its error field is null. A request timeout, DNS/proxy/network
failure or permission/login rejection suppresses repeated attempts on that site
in the same phase; other explicitly enabled sites remain independently available.
Only an actually unavailable shared browser or missing runtime disables the whole
helper. Receipts include the affected site and failure scope; a request timeout
alone is not evidence of a global outage.
The bounded first pass can return useful search-result pixels, clearly labeled
as previews, without opening a full work. Public creator attribution may remain;
it is not private account state and does not justify another crop. The helper
reserves its final 45 seconds for returning evidence instead of further browsing.
These instructions keep the four-minute cap and do not turn an unfinished call
or a saved-but-unreturned image into successful visual delivery.
Ordinary correctable
JavaScript errors do not. No automatic reconnect or permission bypass is used.

Research scope/read-only intent is an instruction to the helper; the official
browser permissions remain the access boundary, not a new hard read-only proxy.
The operator must keep the authorized desktop browser/extension available.
No native PPT editing, layout rules, review thresholds, global font rules or
automatic bookmarks change. This feature does not itself prove better designs.

## Bounded parallel searches

The same tool accepts `requests: [{site, query, purpose}, ...]` for up to three
distinct queries on enabled sites (including different queries on one site).
Each entry has its own local Codex session, temporary
capture directory and newly created tab. They overlap inside one browser lease;
other jobs receive `busy`. The legacy single-query form remains supported.
All entries are validated before any model starts. Each keeps its four-minute
bound and independent failure/capture status; one site timeout does not cancel
the others. Task stop/deadline still cancels the batch through the owner thread.
Usage and actual image-delivery receipts remain per site, with a shared 6 MiB
image response budget. Saved images omitted from that budget are not logged as
visually delivered.

Helpers operate only their own tab using tab-scoped APIs, close it after capture
and do not mark research tabs to survive a turn. Automatic browser turn cleanup
remains the fallback on interruption. This uses isolated tabs, not a new-window
API, and never closes or enumerates unrelated user tabs. Live overlap and cleanup
must be verified before claiming a speedup or reliable isolation.

General discovery prefers explicit `site: "https://www.google.com"` when the
operator enables that origin. This opens Google's own search URL, never the
browser's default address-bar engine. On this Mac the actual search redirects to
`https://www.google.com.hk`; both exact origins are supported and each requires
browser Browse permission. Other regional/consent/account origins are not added
implicitly. Google result links can identify external
public sources without granting browser navigation to those domains. Search
previews are not original-source verification; use permitted source tools for
follow-up reading. Google permission/login/captcha barriers remain barriers.
The separate `pptx_search_sources` batch delegates independent public-web questions
to hosted search helpers; its upstream engine is not selectable and its receipts
must not claim Google. Public-web discovery is not limited to the browser allowlist.
