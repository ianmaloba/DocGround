# DocGround

DocGround is a model-agnostic wrapper for documentation-grounded code generation.
This is the real project repository; the proof-of-concept baseline is
[Draft-DocGround](https://github.com/ianmaloba/Draft-DocGround).

The dissertation experiment repository is
[UEL-CN-7000-Experiments](https://github.com/ianmaloba/UEL-CN-7000-Experiments).
It installs and evaluates DocGround but owns benchmark tasks, model runs, results,
plots, screenshots, and dissertation interpretation.

## Product workflow

1. Accept the user's original task and selected model/provider.
2. Retrieve verified documentation relevant to named or implied libraries.
3. Produce a specific suggested prompt rewrite, for example changing a vague
   request into explicit library functions, data flow, and expected output.
4. Show the original and suggested prompts together. The user may edit/approve the
   rewrite, choose the original prompt, or cancel before any model call.
5. Generate code only after the user selects a prompt and model.
6. Run syntax, API/package hallucination, security, and optional functional checks.
7. Present code, findings, provenance, and reproducible metadata.
8. Require explicit approval before export, commit, push, or any downstream action.

The model must never silently receive a rewritten prompt. The selected prompt,
revision history, documentation snapshot, model, and checks must be recorded.

## Current scope

The first implementation will preserve the verified draft behaviours while adding
prompt revision and approval as first-class concepts. DeepSeek is the first live
provider. GLM, OpenAI, Anthropic, xAI, MiniMax, and Mistral are provider slots and
will be added behind the same adapter contract as credentials and access become
available. No API key is stored in Git.

## Research boundary

DocGround is the reusable mitigation and verification wrapper. The dissertation
repository owns the controlled evaluation: in-distribution and shifted tasks,
repeated model runs, security/hallucination/correctness metrics, statistical
analysis, plots, screenshots, and interpretation notes. Neither repository will
claim that a single smoke test proves the dissertation hypothesis.

## Development

```bash
python3 -m venv venv
./venv/bin/pip install -e '.[dev]'
./venv/bin/python -m pytest -q
```

Live tests are opt-in and must never run in ordinary CI. See `docs/PLAN.md` for the
implementation stages and acceptance criteria.
