# Test a different model API with the PPT workflow

Implemented: an explicit host-only model profile overrides the Codex app-server
provider for research, authoring, repair and independent reviews. Existing default
behavior is unchanged when no profile is supplied. The user account and global
Codex configuration are not modified. All stages record the selected model/API
identity next to existing elapsed-time and token-use observations.

## Compatibility boundary

The initial backend uses Codex's Responses API provider protocol. The provider
must implement streaming Responses plus the tool-call and image-input behavior
required by this workflow. A Chat Completions endpoint or an Anthropic Messages
endpoint is not a drop-in replacement. No universal compatibility is claimed.
Web search and image generation default to disabled for external APIs; enable
only if the provider supports the corresponding tools. A text-only model cannot
replace visual review. A tool smoke is not a full PPT/visual compatibility test.

Official reference inspected 2026-09-20:
https://learn.chatgpt.com/docs/config-file/config-reference
(`model_providers.<id>.wire_api` supports `responses`; env_key selects credentials.)

## Configure privately

From the repository root, create a new local profile (the key prompt is hidden):

```sh
pptx-agent/.venv/bin/python runner/configure-model.py --base-url https://YOUR_PROVIDER/v1 --model YOUR_MODEL_ID
```

This creates `runner/model-profile.local.json` with mode 0600 and refuses to
replace an existing profile. To retain several providers, use `--out` with another
`.local.json` name. The profile is ignored by Git. Alternatively copy
`runner/model-profile.example.json` to a private `.local.json` path and provide
the key using the configured environment variable. Never paste keys into a task,
commit them, or add them to model prompts.

Run the model-specific tool smoke without claiming a website task:

```sh
pptx-agent/.venv/bin/python runner/runner.py --model-profile runner/model-profile.local.json --model-smoke
```

It tests an actual model tool call, file writing, and that tool environments do
not contain the provider key. It writes a private proof to a fresh temporary
workspace. A failed smoke exits nonzero without printing raw provider errors.
The existing `--codex-smoke` also uses this smoke when a model profile is selected.
No external API smoke was performed during implementation: provider and key are
not yet supplied.

## Run a comparison

Create a NEW task for the same brief. Stop/drain the existing queue worker before
starting the alternative worker; the existing worker lock prevents simultaneous
supervisors. Queue processing itself is unchanged: `--once` selects the next
queued task, not a task by model. Do not start this against unrelated queued work.

```sh
pptx-agent/.venv/bin/python runner/runner.py --model-profile runner/model-profile.local.json --once
```

The task binds its host-side state to that provider/model/capability profile.
Reopening it with another model is rejected, preserving causal recovery and
review reuse. Key rotation is allowed. Legacy tasks without a binding can resume
under the default only. For the default model, omit `--model-profile` and use a
new task (or resume a task that already belongs to the default backend).

The API key enters only the model-service process, not CLI arguments, exported
configuration, tool environments, slide artifacts or normal phase events. The
existing tool network/filesystem restrictions remain in effect. Tests cover
profile validation, key isolation, URL/protocol errors, task identity and resume
fences; protocol tests cover the existing app-server lifecycle.

## Acceptance checklist

- [x] Explicit profile and private local key setup.
- [x] Same profile throughout research/author/review/repair.
- [x] Model metadata, default preservation and recovery fence.
- [x] Host tests: 11 provider + 20 app-server tests pass.
- [ ] User supplies provider Base URL and model ID; configures key locally.
- [ ] Real provider smoke and image/tool compatibility checks.
- [ ] New PPT task, rendering and independent reviews for comparison.
