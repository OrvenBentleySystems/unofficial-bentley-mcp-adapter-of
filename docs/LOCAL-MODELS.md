# Local models with llama.cpp

`llama-server` is a **provider**. It serves model weights through an
OpenAI-compatible HTTP API. It is not an MCP client and never speaks MCP. Cline,
Kilo Code, Continue, or Codex remains the client that speaks MCP to the Bentley
servers.

## Tool calling requires the model template

Pass `--jinja` explicitly. Current llama.cpp builds enable Jinja by default,
but the explicit flag makes the tool-calling requirement visible and stable.
Without the model's trained tool template, calls may be malformed even when
ordinary chat works.

With tool-capable templates, llama.cpp may add or merge system instructions
needed for tool-call formatting. Generic template handling can alter system
message placement and interfere with some fine-tunes. Preflight stage 9 forces
one tool call instead of assuming template compatibility.

## Reference launch

```text
llama-server --model <path-to-gguf> --alias <model-id> --n-gpu-layers 999 --ctx-size <n> --port 8080 --jinja
```

`--ctx-size` determines whether the MCP tool catalogue fits. The adapter does
not install llama.cpp, choose weights, or recommend a model.

## Emit provider guidance

After completing `profiles/site.yaml` and running `resolve`:

```powershell
bentley-adapter emit --provider llamacpp --port 8080 --alias <model-id>
```

The command always writes a launch record in the allowed directory. It emits
only supported outputs for detected client locations:

- Codex: an adapter-owned custom-provider TOML fragment using
  `wire_api = "responses"`.
- Cline: UI instructions only. Cline's provider state is internal and is not
  modified.
- Kilo Code: a generated OpenAI-compatible provider fragment when Kilo is
  detected.
- Continue: a standalone model block under `.continue/models` when Continue is
  detected.

No API key value is written. Local placeholder text is used where a client UI
requires a value.

## Client wiring

### Cline

Use **OpenAI Compatible**, not the Ollama provider.

- Base URL: `http://localhost:8080/v1`
- API key: any local placeholder
- Model ID: the value passed to `--alias`

The llama.cpp Ollama-compatible stream can fail in Cline with:

```text
Did not receive done or success response in stream
```

The project-maintained workaround is the OpenAI Compatible provider.

### Kilo Code

Use an OpenAI-compatible custom provider with
`@ai-sdk/openai-compatible`, `options.baseURL` set to
`http://127.0.0.1:8080/v1`, and a model id matching `--alias`. Set
`tool_call: true` and explicit context/output limits for custom models.

### Continue

Use `provider: openai`, `apiBase: http://127.0.0.1:8080/v1`, a model id
matching `--alias`, and `capabilities: [tool_use]`. The adapter writes a
complete standalone YAML block, not a partial list item.

### Codex

The built-in `--oss` selectors are limited to built-in local-provider choices.
The direct endpoint override is experimental. The adapter therefore writes a
custom user-level provider fragment with `base_url` and
`wire_api = "responses"`. Codex compatibility remains unverified until the
Codex executable and llama-server are both present for a live call.

## Tool budget

```powershell
bentley-adapter budget --tier read --client cline
```

The command reports declared tool count and an approximate schema-token cost.
When the client cannot enforce an allowlist, `exposed_tool_count` reports the
larger catalogue the model will actually receive.
The current full catalogue is 75 tools: 25 MicroStation, 5 OpenSTAAD, 34
PLAXIS Input, and 11 PLAXIS Output. Local provider deployments default to Read
tier. Provider emission refuses Full tier.

Client documentation warns that local models can loop, call tools incorrectly,
and produce invalid syntax. A practical starting point is 24 GB VRAM or 32 GB
unified memory. That is a hardware guideline, not a guarantee.

## Preflight stage 9

Add this only when llama-server is configured:

```yaml
local_provider:
  id: llamacpp
  host: 127.0.0.1
  port: 8080
  alias: <model-id>
```

Stage 9 checks:

1. `GET /props` returns `build_info`.
2. `GET /v1/models` lists the configured alias.
3. `POST /v1/chat/completions` returns a forced tool call.

`LOCAL_MODEL_UNREACHABLE` means the loopback server did not answer.
`LOCAL_MODEL_ALIAS_MISSING` means `/v1/models` did not expose the configured
alias. `LOCAL_MODEL_NO_TOOL_CALL` means chat answered without a valid forced
tool call and names `--jinja` as the first check. Without `local_provider`, the
established cloud-provider preflight remains eight stages.

## Current verification

No `llama-server` executable or process was detected on the operator machine
on 2026-09-07. Provider emission, budget guards, and stage 9 are covered by
deterministic tests with a loopback mock server. No local model chain is
claimed as verified. To close this item, run `llama-server` on the operator
machine with `--jinja`, pass stage 9, and complete a Read-tier MicroStation and
STAAD.Pro chain without a cloud call.
