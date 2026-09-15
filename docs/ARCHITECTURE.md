# Architecture

## Core layers

- `grounding`: doc snapshots, retrieval, and prompt revision proposals.
- `approval`: versioned prompt choices and explicit user decisions.
- `adapters`: provider-neutral model generation with injected clients for tests.
- `verification`: syntax, package/API hallucination, security, and optional correctness.
- `runs`: provenance records and safe result export.
- `interface`: later UI/API for interactive testing.

## Repository boundary

This repository is the reusable mitigation product. The separate dissertation repo
consumes it as an installed package and owns experimental control and analysis.
