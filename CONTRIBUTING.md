# Contributing

## Ground rules

- Add an application only through `modules/<id>/module.yaml`.
- Add a client only through `targets/<id>/target.yaml` and a writer contained
  in that target directory.
- A new module or target must not require a core change. If it does, correct
  the abstraction before adding it.
- Do not invent tool names. Record the source or live `tools/list` evidence.
- Add tests for every new failure code, tier rule, and emitted dialect.
- Keep credentials, `machine.json`, generated client configs, and logs out of
  the repository.

Target ids are discovered at runtime. A target folder is available when both
`target.yaml` and `writer.py` are present. Do not register its id in `core`.

## Module descriptor

```yaml
id: application-role
display: Application Role
version: 1.0.0
server:
  package: package-name
  pinned: "exact-version"
  launch:
    command: "${machine.executables.command}"
    args: [serve]
  transport: stdio
requires:
  application: Application
  application_id: registry-discovery-id
  process_names: [Application.exe]
  verified_version: "exact-verified-build"
  version_record_key: Application version
  model_check: window_title
network:
  uses_port: false
preflight:
  - tool: status
    expect: {connected: true}
tiers:
  read: [status, list_items]
  guided: [+create_item]
  full: ["*"]
never_auto_approve: [create_item, delete_item, execute_code]
compat:
  tested_clients: [copilot-cli]
  verified_clients: []
```

`verified_version` and `verified_clients` require a dated run record. A new
application build clears client verification.

## Worked module

```yaml
id: example-reader
display: Example Reader
version: 1.0.0
server:
  package: example-mcp
  pinned: "2.4.1"
  launch: {command: "${machine.executables.example}", args: [serve]}
  transport: stdio
requires:
  application: Example
  application_id: example
  process_names: [Example.exe]
  verified_version: "7.2.0"
  version_record_key: Example version
  model_check: window_title
network: {uses_port: false}
preflight:
  - tool: status
    expect: {connected: true}
tiers:
  read: [status, list_items]
  guided: []
  full: ["*"]
never_auto_approve: [execute_code]
compat:
  tested_clients: []
  verified_clients: []
```

Add a fixture to `tests/`, run the 14 baseline tests plus the new tests, build
and install the wheel, and record any new verification in `HANDOVER.md`.

## Target descriptor

Add `targets/<id>/target.yaml`:

```yaml
id: client-id
format: json
root_key: mcpServers
requires_type: true
type_value: local
supports_inputs: false
supports_tool_allowlist: true
verified: false
```

Keep dialect rendering in the target directory. Do not put client-specific
branches in `core`.
