# Model slots: which model answers where

Every model-backed call in the worker goes through one slot table. A deck can be made by
one model and reviewed by another, each slot can be a different vendor, and a slot can be
reached over an OpenAI-compatible API or through an installed CLI. Omitting the table keeps
today's behaviour exactly (Codex authors; the local Claude CLI reviews when configured).

## Slots

| slot | what it answers | adapters that make sense |
|---|---|---|
| `author` | the whole authoring session: plan, sketch, pages, repairs, exports | `codex_cli` (default), `codex_cli` + `provider` to change the model behind it |
| `research_helper` | reserved: the research phase runs inside the author session and inherits its model | — |
| `content_review` | the independent content pass | `codex_cli`, `claude_cli`, `openai_api`, `cli` |
| `visual_review` | the independent visual pass (page renders as images) | `codex_cli`, `claude_cli`, `openai_api` (vision model), `cli` |
| `critique` | the in-author design critique and asset checks | `codex_cli`, `claude_cli`, `openai_api`, `cli` |
| `advisor` | the borrowing advisor (`migrate`: decision, principle, near/middle/far) | `codex_cli`, `claude_cli`, `openai_api`, `cli` |
| `image_generation` | generated illustrations | `host` (the author session's built-in generation) |

`codex_cli` means "the author backend answers here". A slot that names any other adapter is an
outside model; if it cannot run (no CLI, no key, no network) the worker logs it and falls back
to the author backend, exactly as the Claude review fallback has always worked.

## Settings

Private, `runner/settings.local.json` (mode 0600, never in a task folder):

```json
"model_slots": {
  "author":         {"adapter": "codex_cli", "provider": {"id": "deepseek", "base_url": "https://api.deepseek.com/v1",
                                                            "wire": "chat_completions", "key_env": "DEEPSEEK_API_KEY"},
                     "model": "deepseek-flash"},
  "content_review": {"adapter": "openai_api", "preset": "deepseek", "model": "deepseek-flash", "key_file": "keys/content_review.key"},
  "visual_review":  {"adapter": "claude_cli", "model": "opus"},
  "critique":       {"adapter": "openai_api", "preset": "qwen", "model": "qwen-vl-max"},
  "advisor":        {"adapter": "claude_cli", "model": "opus"}
}
```

Presets (`preset`) fill in `base_url`, `wire` and the conventional `key_env`:
`openai`, `deepseek`, `qwen` (DashScope compatible mode), `gemini` (its OpenAI-compatible
endpoint), `siliconflow`, `moonshot`. An explicit `base_url`/`wire`/`key_env` overrides a preset.

An API key reaches the worker in one of three ways: an environment variable named by `key_env`
(default `PPTX_MODEL_API_KEY`), a private key file (`key_file`, must be mode 0600), or `api_key`
inline in the settings. It is read in the worker process and never written into a task folder or
a model's tool environment.

## Authoring with another model

The author slot stays the Codex session — it owns the files, tools, rendering and exports — but
`provider` points that session at another OpenAI-compatible endpoint and `model` names the model
there. That is the route for "DeepSeek/Qwen/Gemini authors a deck with this system": the harness,
skills, native checks and reviews are unchanged. A model profile selected per task on the website
(`execution_backend: api`) still wins over the slot.

Verified compatibility limits of the chat-completions bridge (streaming, images, tools,
reasoning) are in `docs/model-api-switching.md`; those apply to any chat-completions provider.

## Commands

```
python runner/configure-models.py --show
python runner/configure-models.py --preset content_review deepseek deepseek-flash
python runner/configure-models.py --key content_review          # hidden prompt -> keys/content_review.key
python runner/configure-models.py --cli visual_review 'gemini --model {model} --prompt {prompt} {images}'
python runner/configure-models.py --set advisor '{"adapter":"claude_cli","model":"opus"}'
python runner/configure-models.py --test content_review         # one real call
python runner/configure-models.py --clear visual_review
```

`--show` prints each slot's route and whether it can run here, never a key.

## Tests to run before a comparison

1. `--test <slot>` for every outside slot: it prints the adapter and model that answered.
2. One small create task (5–8 pages) with the author model under test and `visual_review` on a
   different model, then the same brief with the author slot back on Codex, so the decks can be
   compared page by page.
3. A visual pass on a deck whose images matter: a vision model that cannot see images returns a
   schema-valid report with nothing in it. Compare its findings with the renders.
