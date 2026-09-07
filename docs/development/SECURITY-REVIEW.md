# Security review

Review date: 2026-09-07.

## Specialist findings

| Severity | Finding | Resolution |
|---|---|---|
| High | Local-provider host allowed remote endpoint selection and TOML injection. | Fixed. Provider emission accepts loopback hosts only, validates aliases against a conservative character set, and does not interpolate uncontrolled TOML characters. |
| High | Predictable temporary files and reparse points could redirect config writes. | Fixed. Writes use random exclusive temporary files, approved output roots, reparse-point checks, and a second parent check before replacement. Uninstall applies the same path constraints. |

## Dependency audit

`pip-audit` result for the resolved direct runtime dependency:

| Dependency | Tested version | Finding |
|---|---:|---|
| PyYAML | 6.0.3 | No known vulnerabilities |

The runtime dependency surface remains Python standard library plus PyYAML.
`pyproject.toml` pins PyYAML to `>=6.0,<7`. Python support is
`>=3.13,<3.14`; live tests used Python 3.13.15.

## Bandit triage

Final Bandit result: 9 findings, consisting of one B105 false positive, three
B404 subprocess-import notices, four B603 shell-free subprocess notices, and
one B310 loopback URL-opening notice. No high-severity finding remains.

| Test | Location | Decision |
|---|---|---|
| B105 | `core/emit/writer_api.py` | False positive. The value is the boolean `password: true` in a client prompt descriptor, not a credential. |
| B404/B603 | `core/preflight/checks.py`, `core/preflight/mcp_client.py`, `core/resolve/resolver.py` | Accepted. Process creation is the adapter's purpose. Arguments are passed as arrays with `shell=False`; PowerShell and Python launchers resolve to absolute paths. MCP commands come from operator-reviewed module/site configuration. |
| B310 | `providers/llamacpp/writer.py` | Accepted with control. URLs are assembled internally after strict loopback-host validation and integer port parsing. No profile-controlled scheme is accepted. |

Assertion findings were fixed by explicit pipe-state errors. Partial executable
path findings were fixed by resolving `powershell.exe`, `py`, and `uv`
before invocation.

## Threat-surface answers

- **Config write path:** target, module, and provider ids reject path traversal.
  Output files must resolve under the profile directory, user profile, Local
  AppData, workspace root, or allowed directory.
- **Process spawn:** Python uses argument arrays and never `shell=True`. Launch
  configuration remains operator-controlled and must be reviewed before use.
- **Credentials:** the adapter does not read PLAXIS passwords. Profile
  validation rejects likely plaintext secret fields. PLAXIS credentials remain
  in Windows Credential Manager.
- **Generated header:** uninstall accepts only declared target config paths
  inside approved roots and verifies the source-profile metadata before
  deleting or editing.
- **Preservation:** existing reparse points are rejected. Temporary files use
  exclusive random names and are rechecked before atomic replacement.

## Repository settings after push

Enable Dependabot alerts and security updates, secret scanning with push
protection, CodeQL default setup, and GitHub private vulnerability reporting.
