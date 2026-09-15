# Security Rules

- Never commit `.env`, API keys, bearer tokens, or provider response headers.
- Never print full credentials, prompts containing secrets, or raw provider errors
  without redaction.
- Treat generated code as untrusted. Correctness execution is not a security sandbox.
- Require explicit user approval before export, commit, push, or external side effect.
- Keep model credentials server-side if an interface or SaaS deployment is built.
- Record key identifiers and provider names only when they cannot reveal a secret.
