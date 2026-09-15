# DocGround Build Plan

## Mission

Build a reusable, model-agnostic system that improves code-generation reliability
under distribution shift by making verified API context explicit, allowing the user
to review the prompt before generation, and checking the generated result before it
leaves the tool.

## Prompt lifecycle

`original` -> `retrieved` -> `suggested_rewrite` -> `awaiting_approval` ->
`approved_original | approved_rewrite | user_edited` -> `generated` ->
`verified` -> `approved_for_export`

Every transition must be represented in a structured record. A generated result
cannot be exported or pushed without an explicit approval transition.

## Stages

### 1. Preserve the draft contract

Port the draft's doc store, retriever, adapters, hallucination, security,
correctness, gate, and CLI behaviours with focused tests before redesigning them.

Acceptance: the draft's offline tests pass unchanged or with an explained fixture
migration.

### 2. Prompt revision engine

Add a deterministic revision proposal model containing the original task, retrieved
libraries, verified signatures, concrete missing details, assumptions, and suggested
rewrite. The first revision engine may be rule-based; model-assisted rewriting must
be optional and reviewable.

Acceptance: vague prompts receive specific, traceable suggestions; already-specific
prompts are not needlessly rewritten; no unsupported API is introduced.

### 3. Approval and provenance

Implement approve-rewrite, edit, use-original, cancel, and approve-for-export
operations. Persist prompt versions, documentation snapshot, provider/model,
request metadata, verification findings, and user decisions in a serialisable run
record.

Acceptance: no model call occurs before prompt selection; no export/push occurs before
final approval; secrets never enter records or logs.

### 4. Provider and verification hardening

Keep provider adapters interchangeable. Add timeout/retry policy, key validation
without logging values, structured errors, package/API provenance, Bandit/CodeQL
integration points, and a clearly bounded correctness sandbox.

Acceptance: offline tests cover all providers through injected clients; live tests are
explicitly opt-in; security findings and hallucination checks are reproducible.

### 5. Interface

Build a testing-first interface after the core contracts stabilise. It should expose
original/suggested/edited prompts, model selection, generation status, findings,
comparison, artefact export, and approval actions. SaaS concerns are future scope;
keys must remain server-side and tenant isolation must be designed before deployment.

## Non-goals for this repository

The dissertation benchmark harness, bulk model runs, statistical analysis, plots,
screenshots, and dissertation prose belong in `UEL-CN-7000-Experiments`.
