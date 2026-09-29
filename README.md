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

The initial implementation supports explicit provider selection for DeepSeek,
GLM, xAI, and Mistral through a shared chat-completions adapter. It does not call
OpenAI, Anthropic, or MiniMax. Live calls have no automatic retries. No API key is
stored in Git. The bundled documentation snapshot is a small, partial, manually
transcribed baseline, not a complete or continuously updated source of truth;
missing API entries are therefore labelled unverified rather than hallucinated.
The adapters accept text models served through chat completions. Provider-specific
routes such as xAI multi-agent Responses are outside this adapter's current scope.
Truncated or filtered completions fail generation without an automatic retry.

## Research boundary

DocGround is the reusable mitigation and verification wrapper. The dissertation
repository owns the controlled evaluation: in-distribution and shifted tasks,
repeated model runs, security/hallucination/correctness metrics, statistical
analysis, plots, screenshots, and interpretation notes. Neither repository will
claim that a single smoke test proves the dissertation hypothesis.

## Development

Python 3.11 or newer is required. Install a wheel downloaded from the private
[GitHub releases](https://github.com/ianmaloba/DocGround/releases):

```bash
python -m pip install ./docground-0.2.1-py3-none-any.whl
docground ground "Read a CSV file with pandas and group amounts by region"
```

The documentation snapshot is included in the wheel. Grounding a prompt, checking
saved code, and running the offline test suite do not use model API credits. Only
`docground generate` sends a generation request after prompt approval. Package
existence checks may query PyPI; correctness checks require a local Docker image.

For local development:

```bash
python3 -m venv venv
./venv/bin/pip install -e '.[dev]'
./venv/bin/python -m pytest -q
```

Build both package formats and validate their metadata with:

```bash
./venv/bin/python -m build
./venv/bin/python -m twine check --strict dist/*
```

CI tests the installed wheel on Python 3.11 and 3.14. Tests block unmocked HTTP
requests. To include local Docker integration tests, first make
`python:3.11-slim` available and run:

```bash
DOCGROUND_RUN_DOCKER_TESTS=1 ./venv/bin/python -m pytest -q
```

Docker evaluation uses a non-root user and no network. Tests cover successful
execution, assertion failure, timeout, and container cleanup.

`docground ground` displays a proposed grounded prompt without calling a model.
`docground check` runs offline/static checks plus a PyPI existence lookup for
unlisted imports. `docground generate` displays the original and suggested
prompts, waits for an explicit prompt choice before calling the selected model,
then requires a second approval before writing a provenance record. Generated
code is not executed on the host. Optional correctness tests run only in a local
Docker sandbox with networking disabled; Docker/image failures are reported as
unavailable, not as code failures.

Provider calls cost money and are never made by the test suite. See `docs/PLAN.md`
for the broader implementation stages and acceptance criteria.

The dissertation pilot recorded DocGround 0.2.0 grounding proposals, prompt hashes,
and the documentation snapshot. Version 0.2.1 preserves those grounding inputs and
adds verification, redaction, packaging, and adapter completion checks. Existing
pilot observations retain their original version and request settings. Replaying
saved responses can validate application behavior without another model request;
it does not establish that a different endpoint or decoding setting yields the
same generated answer.
