# Test a different model API with the PPT workflow

An explicit host-only model profile selects the model used for research,
authoring, repair and independent reviews. Omitting the profile preserves the
existing Codex backend. This does not change the user account or global Codex
configuration. Phase records include the selected provider/model identity.

## Supported protocols

`wire_api: "responses"` connects Codex directly to a compatible streaming
Responses endpoint. The provider must implement the tool and image behavior the
selected task requires.

`wire_api: "chat_completions"` starts a temporary, authenticated loopback adapter
for each phase. Codex speaks Responses to that adapter; the host translates full
conversation history and calls the provider's `/chat/completions` endpoint. The
provider API key stays in host memory. Codex receives only the temporary local
adapter token, which cannot authenticate to the upstream provider. Existing
restrictions on the model's shell tools remain in effect.

The Chat Completions path currently implements:

- Text messages, image URLs, function calls/results and parallel calls.
- Images returned by tools are carried as a following user multimodal message,
  explicitly labeled as untrusted tool data rather than a new user request.
  Original tool responses retain their call IDs, text and image-position
  placeholders. All results in a parallel call batch arrive before the image
  envelope; image URL/data and detail are preserved exactly. Original user
  images are unchanged. Incomplete or mismatched image-tool history is rejected.
- Exactly one leading system message combining request instructions and all
  system/developer messages. Blocks retain their original order and text, with
  explicit role labels and system-over-developer precedence. Ordinary
  user/assistant/tool history stays in its original order.
- Namespaced tools mapped to unique Chat function names and restored on return.
- Custom tools wrapped as a JSON function with one string field, `input`.
- Usage accounting, output text and tool events, refusals and incomplete output.
- A host-owned model check so a request cannot silently change the profile model.

This is a bounded adapter, not a universal model compatibility layer:

- Upstream requests are **non-streaming**. Responses SSE events are synthesized
  after the complete upstream reply arrives; there is no live upstream token
  streaming or first-token latency improvement.
- Reasoning is opt-in through the host profile's existing `reasoning_effort`
  field. When absent, the adapter sends `enable_thinking: false`. When present,
  it sends `enable_thinking: true` and forwards that exact `reasoning_effort`.
  Provider/model support and the effect on output quality require separate
  verification. Prior Responses reasoning items and upstream reasoning content
  are still not forwarded or exposed; private reasoning continuity is not
  reproduced. Changing reasoning effort changes the task's bound identity, so
  use a new comparison task instead of changing an active task's profile.
- Built-in hosted tools such as web search and image generation are unsupported
  on this path. Keep both disabled. Custom grammar definitions become tool
  descriptions; their grammar is not enforced by the Chat endpoint.
- Images are translated to Chat image URL parts. **This does not establish that
  the selected model can see images.** A real image task and visual review need
  separate verification. File IDs, audio, Responses conversation references and
  `previous_response_id` are unsupported; callers send full history.
- The Chat compatibility path cannot preserve separate protocol-level system
  and developer roles or the original timing of interleaved instruction blocks;
  their ordering and priority are described in the combined leading message.
  Higher-priority instructions are never demoted to user messages.
- Anthropic Messages and other protocols are not supported. Unknown tools/input
  types fail explicitly rather than silently dropping a requested capability.
- Current upstream limits are 180 seconds per HTTP request, a 16 MiB response
  limit and at most 16,384 generated tokens per call (8,192 by default). Long
  generations may fail or return incomplete output; a passing tool smoke does
  not prove full PPT compatibility.

## Configure privately

From the repository root, create a local profile. The API key prompt is hidden:

```sh
pptx-agent/.venv/bin/python runner/configure-model.py \
  --base-url https://YOUR_PROVIDER/v1 --model YOUR_MODEL_ID \
  --protocol responses
```

For the SiliconFlow Chat Completions test selected on 2026-09-20:

```sh
pptx-agent/.venv/bin/python runner/configure-model.py \
  --base-url https://api.siliconflow.cn/v1 \
  --model deepseek-ai/DeepSeek-V4-Flash \
  --protocol chat_completions \
  --out runner/siliconflow-flash.local.json
```

Use the exact model ID available to the account; this selection is V4 Flash,
not an assertion that V4.1 Flash is available. The configuration command creates
a mode-0600 file and refuses to replace an existing profile. Use another
`.local.json` path to retain multiple providers. These files are ignored by Git.
Alternatively, use the example profile and supply the key through its configured
environment variable. Do not put keys in task briefs, commands or source control.

## Validate before processing tasks

Run a model-specific tool smoke without claiming a website task:

```sh
pptx-agent/.venv/bin/python runner/runner.py \
  --model-profile runner/siliconflow-flash.local.json --model-smoke
```

It checks actual model tool execution, file writing and absence of the provider
key from model tool environments. A private proof is written to a fresh temporary
workspace. Failure exits nonzero without printing raw upstream error bodies.
`--codex-smoke` also selects this smoke when a model profile is provided.

The real SiliconFlow V4 Flash tool smoke passed on 2026-09-20. This establishes
basic model/tool protocol compatibility only. The subsequent real image-input
probe returned HTTP 400: `The model is not a VLM (Vision Language Model). Please
use text-only prompts.` This selected endpoint is therefore **text-only**. It
cannot perform the requested image-replication task or image-based independent
visual review by itself. Completing that comparison requires an explicitly
selected vision-capable model or an explicitly agreed hybrid workflow; do not
silently substitute one or claim image compatibility. The original queued task
was not changed by these probes.

Offline adapter checks do not contact the provider or read private profiles:

```sh
python3 runner/test-model-backend.py
python3 runner/test-chat-protocol.py
python3 runner/test-chat-proxy.py
```

They cover profile validation, key isolation, model identity and recovery fences;
message/tool translation and synthetic SSE; loopback authentication, route/body
limits, ephemeral-token isolation and sanitized transport failures.

## Run a comparison

Create a **new task** for the same brief. Drain the existing queue worker before
starting the alternative worker; the worker lock prevents simultaneous
supervisors. Queue selection is unchanged: `--once` selects the next queued task,
not a task by model. Do not run it against unrelated queued work.

```sh
pptx-agent/.venv/bin/python runner/runner.py \
  --model-profile runner/siliconflow-flash.local.json --once
```

A task binds its host-side state to that provider/model/capability profile.
Reopening it with another identity is rejected to preserve causal recovery and
review reuse. Key rotation is allowed. Legacy tasks without a binding may resume
only with the default backend. Omit `--model-profile` to select the default for a
new task or one already belonging to it.

## Acceptance checklist

- [x] Explicit private profile setup and default-backend preservation.
- [x] Same model profile throughout research, authoring, review and repair.
- [x] Model metadata and recovery identity fence.
- [x] Bounded Chat Completions adapter and offline protocol/proxy tests.
- [x] User-selected SiliconFlow V4 Flash and real tool smoke.
- [x] Actual image-input probe: rejected with HTTP 400; selected model is text-only.
- [x] User selected a newer vision-capable model: Qwen/Qwen3.8-27B.
- [ ] New PPT task completed, rendered and independently reviewed for comparison.

## Qwen3.8 comparison (2026-09-20)

Rick selected `Qwen/Qwen3.8-27B` after the V4 Flash vision rejection. The account
model list contains this exact ID. A direct image request returned HTTP 200 and
correctly identified a red square at upper left and a blue circle at lower right.
The real Codex tool smoke also passed (calculation, file write, key isolation).

The tool smoke specifies digits only in its output file. The initial wording
allowed the model to write `17 * 19 = 323`, which correctly computed the result
but did not satisfy the existing digits-only assertion; the prompt was clarified
and rerun without weakening the assertion.

An actual vision-tool round trip exposed a separate compatibility failure:
image bytes inside Chat `role: tool` messages were accepted with HTTP 200 but
produced unrelated visual descriptions. A matched-image A/B probe showed the
same bytes correctly recognized when delivered in a following multimodal user
message. An HTTP 200 alone is therefore not a vision acceptance criterion.

After the tool-image normalization fix, the real Codex `view_image` → Qwen3.8
→ shell file-write round trip correctly reported the red square at upper left
and blue circle at lower right. Protocol, proxy and backend tests total 43
passing checks, with another 20 app-server and 11 content-workflow checks passing.
The requested website job `62a7e360-810c-4275-8123-1bc74ffb0945` was then started
with the Qwen3.8 private profile; complete PPT acceptance remains pending.

The first Qwen full task completed research and reached authoring, then stopped
on upstream HTTP 429 after approximately 494,000 prompt tokens reported by the
app-server. This is a rate-limit failure, not a completed presentation. The
Chat adapter now retries **HTTP 429 only**, at most three upstream attempts per
request, waiting 30 seconds and then 60 seconds. Other HTTP and transport errors
are not retried by this adapter. These limits apply to each adapter request;
the Codex client may also have its own retry policy. Successful and failed phase
records include allowlisted API status/attempt/delay/token metadata; provider
response bodies, prompt text and credentials are excluded. Recovery still uses
the existing task checkpoint and model identity rather than replacing the task.


## DeepSeek official comparison (2026-09-20)

The tested API model ID is `deepseek-flash` at `https://api.deepseek.com`,
using native `responses` and `reasoning_effort: "high"`. This is a separate
provider/model selection from SiliconFlow's `deepseek-ai/DeepSeek-V4-Flash`.
No key or private model profile is committed.

Live probes passed: actual reference-image reading; a Responses function call;
and AppServer image-tool, shell calculation, file-writing and key-isolation
checks. The model produced a one-slide 3:2 native editable reference redraw,
then corrected concrete omissions using independent review feedback.
The v2 export contains 342 shapes, 53 connectors and 23 CT pictures; equations
are editable text/shapes, not rasterized formulas or equation-editor objects.
Two independent final reviews found no required content correction or clear
obstructive overlap. Strict one-to-one visual fidelity **did not pass**:
typography, spacing, gradients, chart silhouettes and geometry still differ.
PowerPoint interactive editing/font substitution was not manually tested.

The initial automated run stopped during content-evidence review because the
provider returned prose plus a JSON code fence despite structured-output
instructions. `structured_output.parse_structured_output()` now accepts a bare
object or one unambiguous explicit JSON fence, without repairing report content.
Duplicate keys, invalid constants and ambiguous extra payloads are rejected;
`validate_report()` remains authoritative. The actual saved failure response
was recovered and validated; 43 parser/workflow/review-session tests passed.
The complete automatic review chain was **not rerun from start to finish** after
this fix. The final candidate instead received a focused DeepSeek repair and
two independent reviews orchestrated outside that failed run. Do not label this
a clean unattended end-to-end pass.

Candidate v2 SHA-256:
`25750cd74fe658a16ccf1e9f8370c14dc5d8d8c98f91e3d29eaf4b026063d6f0`.
