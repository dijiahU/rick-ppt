# Customer model accounts (API first)

Users can connect an API account in the brief form, then select that account and
an approved model for a new task. Model fees are billed directly by the provider;
existing site trial admission rules still apply. The connection check lists models
and does not verify remaining credit or incur an inference charge. Token receipts
remain administrator-only. There is no service-fee wallet in this release.

## Trust and execution

- Fixed official origins in `website/lib/model-providers.ts` and
  `runner/customer_models.py`; no customer-provided base URLs, headers or proxies.
- D1 stores AES-GCM ciphertext with a random 96-bit nonce and AAD binding to the
  credential ID, site user and provider. Configure `BYOK_ENCRYPTION_KEY` as a Sites
  secret: 32 random bytes in hex, server-only. Preserve it across deployments;
  rotation requires decrypt/re-encrypt migration. Losing it loses stored keys.
- Public account responses contain masked metadata only. No browser persistence.
- Admission and immutable `task_funding` binding use one D1 transaction. A retry
  cannot change credential, provider, model or execution route. Legacy workers
  cannot claim these tasks. New workers advertise `funding_version:1` at claim.
- The worker retrieves a credential from the dedicated model-profile endpoint,
  authenticated with its internal token and the current running task lease.
  Ownership and provider/model are checked again. Keys are never included in
  task briefs, queue responses, model-visible files, checkpoints or source.
- A host-private receipt pins the account reference across recovery. The runner
  builds a task-scoped profile; the operator's global profile is unchanged.
  Invalid/unavailable customer credentials fail closed, without operator fallback.
- Native Responses customer requests force `store:false`, request encrypted
  reasoning state and require explicit input history. Persistent conversation IDs
  are rejected rather than silently dropped. This is not a zero-retention promise
  for any provider's internal monitoring logs.
- Customer-funded auxiliary search/image-generation calls are blocked before any
  default AppServer starts, including asynchronous material prefetch. This first
  release supports uploaded materials and public media URLs, with hosted search
  and generation explicitly unavailable. Their user-funded routes remain future
  work; do not describe this mode as feature-equivalent to the full service.
- Replace key keeps the same user/provider/account reference and permits resume
  after a key expires; changing provider requires a new task.
- Disconnecting erases the saved ciphertext and pauses queued/running tasks.
  Requests already sent can still be billed. Disconnected task identities cannot
  be rebound to another account. Revoking a key at the provider is immediate at
  the provider; an in-memory request cannot be recalled by the website.

## Current provider scope and verification (2026-10-25)

OpenAI: GPT-6 Astra, GPT-6.1 Sol, GPT-6 Luna. DeepSeek: deepseek-flash.
SiliconFlow: DeepSeek-V4.1-Flash, GLM-5.3-Flash, Kimi-K2.6, Qwen3.6-35B-A3B.
All selected models have image input; account access still depends on the user's
provider. OpenAI catalog IDs were checked against official model documentation.
Real customer-profile tool-use smoke passed for DeepSeek Flash (Responses) and
SiliconFlow GLM-5.3-Flash (Chat). Both wrote the expected file, kept the provider key
out of shell environment and continued across multiple requests. No OpenAI key
was available for a live OpenAI test in this change. This does not establish full
PPT design quality or full-length checkpoint recovery on every model.

Run `node website/scripts/test-model-accounts.mjs` from a checkout with website
dependencies, and `python runner/test-customer-models.py` with runner dependencies.
Website tests execute real handlers against transactional disposable SQLite.

## Subscription quota and private distribution

API billing is distinct from ChatGPT subscription usage. Official ChatGPT plan
OAuth supports eligible apps, but the current open-source/local integration docs
require paid/remotely hosted apps to register interest. Website identity sign-in
does not authorize inference. No subscription tokens are accepted by this API-key
feature. See https://developers.openai.com/siwc/token-sharing-open-source .

This change does not make the already-public Skill secret. A future private
edition still needs its own release pipeline, public-output projection/checks,
preview/PPTX inspection and service-order ledger before being sold as such. Existing
public output and editing remain available; do not claim comprehensive private
Skill exfiltration prevention.
