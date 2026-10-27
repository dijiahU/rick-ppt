# Private usage ledger

Task execution records API usage immediately from the upstream receipt, including
reported usage on rejected/incomplete responses. Transport failures without usage
remain unavailable, never zero. Local Codex turns (including retained tool and
material-prefetch contexts) form a separate non-API series. Reasoning tokens are
part of output; cached input is part of input, not an additional total.

Private receipts live in `<state_directory>/<job-id>/usage/` outside the model
workspace, prompts, checkpoints and delivered PPTX. Atomic host files survive a
failed upload and are resent when that task resumes. API response IDs deduplicate
replays; turn IDs identify cumulative local snapshots. The website persists these
in `task_usage`, across attempts. `/api/worker/:id/usage` requires worker auth and
the current job lease; `/api/admin/jobs/:id/usage` requires administrator auth.
The admin task detail shows the ledger. Public job/progress APIs do not select it.
No quota, payment, credit balance or charging behavior changes.

## Contract rates

Set host-only `usage_pricing_file` in worker settings, or environment variable
`PPTX_USAGE_PRICING_FILE`, to an absolute JSON path. Start from
`usage-pricing.example.json`. Rates must match the actual API provider host
(including a port if present), returned model ID and service tier exactly. Use
your supplier's contracted rate, not an assumed public list price. Example entry
shape (the `RATE` placeholders must be replaced with real decimal strings):

```
{"provider":"your-api-host.example","model":"exact-model-id",
 "serviceTier":"default","inputUsdPerMillion":"RATE",
 "cachedInputUsdPerMillion":"RATE","cacheWriteUsdPerMillion":"RATE",
 "outputUsdPerMillion":"RATE"}
```

Give every price update a new `version`. Each new receipt freezes the matched
rates and calculated micro-USD amount; a later rate change does not reprice
historical receipts. Unknown rates remain unpriced. This is model-token cost
calculation, not a supplier invoice: image/search/tool charges, TTL-dependent
cache rates, context-length-dependent tiers, discounts and taxes are not inferred.
Do not configure a flat rate for a contract with additional conditions. No
per-request supplier-reported monetary charge is claimed where none is provided.

Local Codex usage is useful for comparison, but is never recorded as a real API
expense. Hosted search/image generation through a local context does not expose
a separate API cost receipt and is not silently priced as one.
