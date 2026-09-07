# Bentley MCP Harness

Operating contract for AI agents driving MicroStation, STAAD.Pro, and PLAXIS
through local MCP servers.

Document version: 2.1. Verification date: 2026-09-07.

## Evidence labels

- **verified** means observed on the named application build and date. It does
  not transfer to another build.
- **source** means stated by the linked vendor or project documentation on
  2026-09-07, but not independently verified on every supported build.
- **convention** means chosen by this harness.
- **unverified** names the evidence required to close the gap.
- **enforced** names adapter code that checks the rule.
- **operator discipline** means the adapter cannot guarantee the rule.

Every factual or behavioral claim below carries one of these labels. A label on
a table row applies to the whole row.

## 1. Non-negotiable rules

| Rule | Classification |
|---|---|
| Work only on a disposable project copy. | **convention, operator discipline** |
| Call status before any other application operation. | **convention, operator discipline** |
| Verify every mutation with a read-back. An empty error list is not proof. | **convention, operator discipline** |
| Never store or echo passwords, bearer tokens, or licence identifiers in prompts, logs, configuration, commit history, or chat. | **convention, enforced by `core.common.validate_safe_profile` for site profiles; operator discipline elsewhere** |
| Never enable automatic approval for a mutating tool. | **convention, enforced by `core.common.validate_safe_profile` for site profiles; operator discipline in clients** |
| Every cross-application handoff is an explicit file with a manifest. | **convention, operator discipline** |
| Stop on the first unexpected result. Do not retry a mutation with altered arguments without approval. | **convention, operator discipline** |
| Pin every server and record the exact version before the first call. | **convention, enforced by module descriptors and preflight stage 6** |
| All engineering outputs require review by a qualified engineer. | **convention, operator discipline** |

## 2. Verified baseline

**verified 2026-09-07, MicroStation 26.00.01.65, STAAD.Pro 26.0.0.340,
PLAXIS 2D 2023.2.1.1079, adapter 0.1.0**

| Application | Server | Observed result |
|---|---|---|
| MicroStation 2026.1 build 26.00.01.65 | Bentley MicroStation MCP, Copilot package 26.01.178 | MCP initialized with 25 tools. `microstation_get_file_info` returned one active 3D model from a disposable test DGN. |
| STAAD.Pro 2026 version 26.0.0.340 | OpenSTAAD MCP | Connected as `staadPro1`. A read returned 4 nodes and 3 beams from the bundled steel portal-frame sample. |
| PLAXIS 2D 2023.2.1.1079 | `plaxis-mcp` 0.3.5, `legacy-38-2023` profile | MCP initialized with 34 Input tools. `connect`, `connection_status`, `project_info`, `list_materials`, and `model_state` returned from a disposable test project. |
| GitHub Copilot app 1.0.83-5 | `%USERPROFILE%\.copilot\mcp-config.json` | The three local servers worked in one session. |

**verified 2026-09-07, MicroStation 26.00.01.65:** the live
`tools/list` result contained these 25 names. The cached inventory contained the
23 `microstation_` names; the bridge supplied the final two names.

```text
microstation_capture_viewport
microstation_execute_query
microstation_find_documentation
microstation_get_file_info
microstation_get_schema
microstation_get_selection
microstation_get_workflow_prompt
microstation_lookup_python_api
microstation_lookup_python_pitfalls
microstation_lookup_python_recipe
microstation_lookup_python_snippet
microstation_lookup_python_tests
microstation_manage_display_set
microstation_manage_file_index
microstation_manage_project
microstation_prepare_python
microstation_run_keyin
microstation_run_python
microstation_set_selection
microstation_verify_python_code
microstation_view_redo
microstation_view_state_apply
microstation_view_undo
mstnBridgeReconnect
mstnBridgeStatus
```

**scope of the verified 2026-09-07 claim, MicroStation build 26.00.01.65 and
Copilot package 26.01.178:** this inventory applies only to those builds.
**unverified on another build;
closure:** run `tools/list` and compare it with
`%LOCALAPPDATA%\Bentley\McpBridge\Config\microstation-tools.json`.

## 3. Version record

**convention, enforced by `core.preflight._version_record_complete`:** complete
this record before the first MCP tool call.

```text
date                :
operator            :
machine             :
os build            :
MicroStation build  :
STAAD.Pro version   :
PLAXIS version      :
openstaad-mcp tag   :
plaxis-mcp version  :
AI client + version :
model identifier    :
temperature         :
allowed directory   :
PLAXIS 2D Input     : 10000
PLAXIS 2D Output    : 10001
PLAXIS 3D Input     : 10002
PLAXIS 3D Output    : 10003
```

**convention, enforced by preflight exit 11:** a blank value or a value
containing `TODO` stops the run.

## 4. Determinism controls

| Control | Classification |
|---|---|
| Pin the model identifier and record the client temperature or nearest equivalent. | **convention, operator discipline** |
| Keep the prompt and enabled tool set unchanged between repeat runs. | **convention, operator discipline** |
| Start repeat runs from separate fresh copies, never the previous output. | **convention, operator discipline** |
| Treat repeatability as evidence, not proof. The read-back remains authoritative. | **convention, operator discipline** |

## 5. Server profiles

### 5.1 MicroStation MCP

| Item | Evidence and value |
|---|---|
| Availability | **source 2026-09-07, Bentley MicroStation MCP documentation:** early access for restricted users. |
| Verified build | **verified 2026-09-07, build 26.00.01.65:** live bridge and file-info read passed. |
| Install | **source 2026-09-07, Bentley installer build 26.01.178:** install Bentley Copilot for MicroStation and its MCP component with elevation. |
| Start | **verified 2026-09-07, build 26.00.01.65:** load Copilot and run `copilot mcpstart`. |
| Verify | **verified 2026-09-07, build 26.00.01.65:** `mstnBridgeStatus`; use `mstnBridgeReconnect` only when disconnected. |
| Cache | **verified 2026-09-07, build 26.00.01.65:** `%LOCALAPPDATA%\Bentley\McpBridge\Config\microstation-tools.json`. |
| Log | **verified 2026-09-07, build 26.00.01.65:** `%LOCALAPPDATA%\Bentley\Logs\mstn-copilot-mcpb.log`. |
| Client-neutral launcher | **verified 2026-09-07, build 26.00.01.65:** `bundle.mcp.js` worked with GitHub Copilot. **unverified elsewhere; closure:** register the generated target file and record `microstation_get_file_info`. |

**source 2026-09-07, Bentley MicroStation MCP documentation:** the embedded
Python sandbox blocks filesystem, network, and process modules. A MicroStation
key-in can still invoke normal application file operations.

**convention, enforced by the MicroStation descriptor:** Read tier excludes
`microstation_run_keyin`, `microstation_run_python`, mixed-action management
tools, and view or selection mutations.

### 5.2 OpenSTAAD MCP

| Item | Evidence and value |
|---|---|
| Project | **source 2026-09-07, `BentleySystems/openstaad-mcp` v1.2.0:** MIT-licensed OpenSTAAD COM bridge for Windows. |
| Transport | **source 2026-09-07, v1.2.0:** stdio by default; loopback HTTP is optional and requires an explicit token in this harness. |
| Tools | **verified 2026-09-07, STAAD.Pro 26.0.0.340:** `discover_api`, `read_skills`, `list_instances`, `execute_code`, and `get_status`. |
| Multi-instance identity | **verified 2026-09-07, STAAD.Pro 26.0.0.340:** aliases use the `staadPro1` form and `list_instances` is authoritative. |
| Sandbox | **source 2026-09-07, v1.2.0 repository guidance:** AST validation, path validation, protected-directory blocking, and UNC blocking are present; further sandbox hardening remains planned. |
| Long scripts | **source 2026-09-07, v1.2.0 repository guidance:** a timeout may block later runs. Keep scripts short and call `get_status` before continuing. |

**convention, enforced by preflight stages 4 and 6:** a running STAAD process
without an open `.std` file fails, and any server version mismatch warning
stops the run.

### 5.3 PLAXIS-MCP

| Item | Evidence and value |
|---|---|
| Project | **source 2026-09-07, `yixuanzhong/PLAXIS-MCP` v0.3.5:** MIT-licensed independent project, not supported by Bentley or Seequent. |
| Transport | **source 2026-09-07, v0.3.5:** Windows-local stdio with a role-pinned worker. |
| Host runtime | **source 2026-09-07, v0.3.5:** CPython 3.13; do not install `plxscripting` in the host environment. |
| Profiles | **verified 2026-09-07, PLAXIS 2D 2023.2.1.1079 and v0.3.5:** `setup` produced role profiles under `%LOCALAPPDATA%\Caros\PLAXIS-MCP\profiles`; the Input credential remained in Windows Credential Manager. |
| Input tools | **verified 2026-09-07, PLAXIS 2D 2023.2.1.1079 and v0.3.5:** 34 tools exposed. |
| Output tools | **source 2026-09-07, v0.3.5:** 11 tools documented. **unverified on this machine; closure:** start PLAXIS Output on 10001 and record `connection_status`, `project_info`, and `list_result_types`. |
| Endpoint overrides | **source 2026-09-07, v0.3.5:** `serve` fails closed when a `PLAXIS_*` endpoint environment variable is present. |

**source 2026-09-07, v0.3.5:** Input-only tools are `list_objects`,
`model_state`, `set_property`, `call_method`, `new_project`, `open_project`,
`close_project`, `recover_project`, `save_project`, `create_phase`,
`set_current_phase`, `set_phase_property`, `activate`, `deactivate`,
`calculate`, `view_results`, `set_mode`, `generate_mesh`, `create_point`,
`create_line`, `create_polygon`, `create_borehole`, `create_soillayer`,
`create_material`, `assign_material`, and `create_structural_element`.

**source 2026-09-07, v0.3.5:** both roles expose `connect`, `disconnect`,
`connection_status`, `list_members`, `inspect`, `project_info`, `list_phases`,
and `list_materials`. Output also exposes `list_result_types`, `get_results`,
and `get_single_result`.

### 5.4 Port discipline

**convention, enforced by module descriptors and preflight stage 5**

| Application | Role | Port |
|---|---|---:|
| PLAXIS 2D | Input | 10000 |
| PLAXIS 2D | Output | 10001 |
| PLAXIS 3D | Input | 10002 |
| PLAXIS 3D | Output | 10003 |
| Reserved | Future or second install | 10004 to 10009 |

1. **convention, operator discipline:** set the port in the PLAXIS Configure
   remote scripting server dialog. The application owns the port.
2. **source 2026-09-07, plaxis-mcp v0.3.5:** never redirect an endpoint with a
   `PLAXIS_*` environment variable.
3. **convention, operator discipline:** run `plaxis-mcp setup` after every port
   change so the generated profile follows the application.
4. **convention, enforced by `core.preflight.classify_port`:** identify every
   listening PID before authentication. Multiple owners produce
   `PORT_COLLISION`; the wrong owner produces `PORT_IDENTITY_MISMATCH`.
5. **convention, operator discipline:** keep passwords in Windows Credential
   Manager. Rotate any password exposed in an image or transcript.
6. **unverified for duplicate product generations; closure:** prove separate
   installation binding and profile selection before supporting two 2D or two
   3D installations on one machine.

### 5.5 Optional hosts and other Bentley products

**unverified; closure:** no ProjectWise, OpenRoads, OpenBuildings, SYNCHRO,
OpenBridge, iTwin Platform, TigrimOS, PLS-CADD, TOWER, PLS-POLE, or Evo module
is included. Add one module descriptor only after vendor connection details and
a read-only live probe are recorded.

## 6. Adapter enforcement map

| Rule | Enforcement |
|---|---|
| Machine inventory is current and belongs to this host and account. | **enforced by preflight stage 1, exit 10** |
| Version record is complete. | **enforced by preflight stage 2, exit 11** |
| Required process is running. | **enforced by preflight stage 3, exit 12** |
| Model or project is open. | **enforced by preflight stage 4, exit 13** |
| Port has one expected application owner. | **enforced by preflight stage 5, exit 14** |
| Recorded application and server pins match descriptors; OpenSTAAD warning scan passes. | **enforced by preflight stage 6, exit 15** |
| Allowed directory is local, writable, not UNC, not a profile root, project share, network drive, or sync root. | **enforced by preflight stage 7, exit 16** |
| Module read probes exist and match declared expectations. | **enforced by preflight stage 8, exit 17** |
| A configured local provider reports a build, expected alias, and forced tool call. | **enforced by optional preflight stage 9, exit 18** |
| Generated configs contain pins; site profiles contain no automatic approval keys or likely plaintext secrets. | **enforced for site-profile values by `core.emit` and `core.common.validate_safe_profile`; module descriptors remain contributor review** |
| Open file is a disposable copy rather than a live project. | **operator discipline; closure for automation would require an approved project-root policy** |
| Every mutation receives per-call approval and read-back. | **operator discipline in the client and agent procedure** |
| Engineering output is correct. | **operator discipline; qualified engineer review required** |

## 7. Session procedure

1. **convention, enforced:** run `resolve` and inspect `machine.json`.
2. **convention, enforced:** complete the version record and run preflight.
3. **convention, operator discipline:** confirm the open files are disposable.
4. **convention, operator discipline:** state the target, intended tool, file
   effect, and read-back before every mutation.
5. **convention, operator discipline:** make one logical change per call.
6. **convention, operator discipline:** read back the affected fields and append
   the result to the run log.
7. **convention, operator discipline:** stop on divergence, warnings that
   cannot be classified, credential prompts, or failed read-back.

## 8. Cross-application handoff

**convention, operator discipline:** MCP servers share no model state. Every
handoff is a file plus a manifest.

```text
artefact            :
source_application  :
source_file         :
target_application  :
format              :
units               :
coordinate_system   :
origin_offset       :
element_count       :
produced_by         :
produced_at         :
checksum            :
```

**convention, operator discipline:** units, coordinate system, origin, and
element count must match at the receiving application. A mismatch stops the
chain. Missing sections, materials, loads, or soil properties are questions,
not defaults.

## 9. Failure catalogue

| Exact observed symptom | Cause | Adapter detection and required action | Evidence |
|---|---|---|---|
| `No STAAD.Pro instances found` | STAAD.Pro was running without a model registered for OpenSTAAD. | **preflight stage 4, `MODEL_NOT_OPEN`:** open the intended `.std` file, then rerun. | **verified 2026-09-07, STAAD.Pro 26.0.0.340, OpenSTAAD MCP** |
| `AUTHENTICATION_FAILED` and `The PLAXIS scripting server rejected the stored password for this endpoint.` | PLAXIS 2D and 3D both claimed port 10000; the client reached the wrong secured endpoint. | **preflight stage 5, `PORT_COLLISION` or `PORT_IDENTITY_MISMATCH`:** apply the port map, regenerate profiles, then reconnect. Do not rotate the credential first. | **verified 2026-09-07, PLAXIS 2D 2023.2.1.1079, PLAXIS 3D 2025.1.3.5, plaxis-mcp 0.3.5** |
| `machine.json belongs to host '<recorded>', not '<current>'` | A copied machine record or a hardcoded profile path does not belong to the active host or account. Live discovery also handled a dotted account name without string concatenation. | **preflight stage 1, `MACHINE_FOREIGN`, plus `core.resolve`:** regenerate machine state under the active account and emit absolute paths from it. | **verified 2026-09-07, Windows 11 build 26200, adapter 0.1.0; account value redacted for publication** |
| `VERSION_RECORD_INCOMPLETE` | A required record field is blank or contains `TODO`. | **preflight stage 2:** complete the field; do not infer it. | **verified 2026-09-07, adapter 0.1.0 test suite** |
| `SERVER_VERSION_MISMATCH_WARNING` | OpenSTAAD reported a compatibility warning. | **preflight stage 6:** stop and align versions. | **source 2026-09-07, OpenSTAAD MCP v1.2.0; unverified live mismatch path, closure: run the negative mismatch test on a disposable installation pair** |
| `PLAXIS_*` override refusal | Endpoint environment injection was attempted. | Remove the variable and regenerate the role profile. | **source 2026-09-07, plaxis-mcp v0.3.5** |

## 10. Data handling and approvals

| Rule | Classification |
|---|---|
| Keep all application servers local. No tunnel, gateway, WSL, Docker, or remote transport is part of this pack. | **convention, enforced by shipped descriptors; operator discipline outside them** |
| Local server traffic does not make cloud model prompts local. Obtain approval before project data reaches a cloud provider. | **convention, operator discipline** |
| Redact client names, coordinates, and identifiers unless approved. | **convention, operator discipline** |
| Keep Default Approvals in VS Code and per-call prompts in other clients. | **convention, operator discipline** |
| Never auto-approve `execute_code`, `microstation_run_keyin`, `microstation_run_python`, `call_method`, file operations, or calculations. | **convention, enforced in emitted profile validation; operator discipline in client UI** |

## 11. Run log

**convention, operator discipline:** append one row per tool call.

```text
timestamp | server | tool | intent | args_summary | result | verified_by | pass_fail
```

**convention, operator discipline:** close with the version record, files
touched, files created, manifests, unresolved warnings, and engineer reviewer.

## 12. Limits

- **unverified; closure:** no clean second-machine verification exists. Run
  `resolve`, emit, wheel install, and all eight preflight stages on a clean
  Windows machine and retain its sanitized run record.
- **unverified; closure:** PLAXIS Output has not been verified. Start Output on
  port 10001 and record `connection_status`, `project_info`, and
  `list_result_types`.
- **unverified; closure:** there is no stable provenance for the pinned
  OpenSTAAD executable used in the live validation override. Install the
  v1.2.0 release or signed `.mcpb`, record its provenance, and rerun preflight.
- **unverified; closure:** no local llama.cpp model chain has completed on the
  operator machine. Start `llama-server` with `--jinja`, pass stage 9, then run
  a Read-tier MicroStation and STAAD.Pro chain through a detected client.
- **source 2026-09-07, Bentley MicroStation documentation:** MicroStation MCP
  is early access. The 25-tool inventory is verified only for build
  26.00.01.65.
- **source 2026-09-07, OpenSTAAD v1.2.0:** code runs through a guarded Python
  sandbox and further hardening remains planned.
- **source 2026-09-07, plaxis-mcp v0.3.5:** PLAXIS-MCP is independent and has
  no Bentley or Seequent support.
- **unverified; closure:** agent-driven and multi-instance licence entitlement
  is unresolved. Obtain written guidance from Bentley commercial.
- **convention, operator discipline:** no component validates engineering
  correctness. A qualified engineer reviews every analysis output.
