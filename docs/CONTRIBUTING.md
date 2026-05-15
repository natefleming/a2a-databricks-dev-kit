# CONTRIBUTING

How to extend the **dev kit itself** (the library + template). For extending **your
agent** (built on top of the kit), see [DEVELOPMENT.md](DEVELOPMENT.md).

## Project rules

1. **Never push directly to `main`.** All work goes through a `feature/<slug>` branch
   off `main`. Same convention dao-ai uses.
2. **`make unit` must pass before any push.** No exceptions.
3. **`make check && make format` must show no changes before any push.** Run these.
4. **Don't add features beyond what the request specifies.** Trim, don't accrete.

## Where to put new code

| You're adding... | Put it in... |
|---|---|
| A new auth scheme | `src/a2a_databricks/auth.py` + verifier_for() + tests |
| A new env-driven knob | `src/a2a_databricks/config.py` + `.env.example` + docs |
| A new A2A protocol endpoint | `src/a2a_databricks/server.py` + spec link in comment |
| A new LLM backend | `src/a2a_databricks/llm.py` + factory branch |
| A new tracing decorator | `src/a2a_databricks/tracing.py` |
| A reusable agent skill | Don't. Skills belong in user agents, not the kit. |

## Backward compat

The kit's public API is everything exported from `a2a_databricks/__init__.py`. Don't
change those signatures without a major-version bump.

The template at `template/{{.project_name}}/` is also user-facing. If you change the
generated file layout, document it in `CHANGELOG.md` and bump the minor version.

## Running the full check before pushing

```bash
make check && make format && make unit
```

CI gates on these.

## Releasing a new version

1. Bump `version` in `pyproject.toml` and `src/a2a_databricks/__init__.py`.
2. Update `CHANGELOG.md` with the user-facing changes.
3. Commit, push, open a PR.
4. After merge, tag the release: `git tag v0.x.y && git push --tags`.

## Common contribution paths

- **Add an mTLS auth verifier.** Subclass `AuthVerifier`, add to `verifier_for`. Update
  the Agent Card to advertise `securitySchemes.mtls`.
- **Add a Model Serving deploy target.** Currently the kit is Apps-only. Adding Model
  Serving means writing a separate `src/serving/` entrypoint exposing only `/invocations`
  and bridging A2A semantics over it.
- **Add MCP integration.** A2A agents can call MCP servers internally. Add a thin
  wrapper in `src/a2a_databricks/mcp.py` that takes an MCP server URL and exposes its
  tools to the agent.

## Don't add

- A pre-commit config. Nate doesn't use them.
- `setup.py` / `setup.cfg`. We're on hatchling + pyproject.
- Pinned requirements with `==`. Use compatible ranges.
- A `print(...)` statement for logs. Use `loguru` or stdlib `logging`.
