# LLM Phase 5 — Enterprise Orchestrator

This layer adds provider failover, circuit breakers, bounded input/output, short-lived deduplication cache, response guarding, secret redaction, and an allowlist-based tool policy.

## Safety boundary
The model never receives direct authority to execute critical operations. Read-only tools are allowlisted; consequential tools require explicit human approval. Unknown tools are denied.

## Provider chain
`AI__LLM_PROVIDER=openai,anthropic,deterministic`

Providers are attempted in configured order. Provider outages open a circuit after the configured failure threshold. A short cache prevents duplicate identical requests during incident bursts.

## Important limitation
The OpenAI and Anthropic adapters are real HTTP integrations, but external provider calls are not executed in the repository test suite. Tests use deterministic fake providers. Production validation still requires credentials, network access, provider quotas, and a controlled integration test.
